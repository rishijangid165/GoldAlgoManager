#!/usr/bin/env python3
"""Forward paper-trade tracker for the playbook v3 setups (XAUUSD only).

Detects v3 setup signals on completed 1h bars and logs hypothetical trades to
journal/paper_trades.csv. Nothing here can trade: it never calls order_send,
never touches positions, and only reads data.

Setups (rules imported from research/deep-study-2026-11-14, not rewritten):
  ny_lon_brk_d4h   NY 08:00-12:00 ET first 1h close beyond the London range, daily+4H MA trend
  fomc_cont        FOMC day, 15:00 ET open in the direction of the 14:00 bar close vs 13:00 close
  donch20_long     completed session daily closes above the prior 20-day high -> long at 18:00 ET open
  asia_brk_trend   Asia-range first 1h close-break (03:00-13:00 ET) with daily+4H MA trend ("clean" Asia break)

Each setup is its own paper book (one trade at a time per setup), with the
research engine's management: 0.5% risk on $100k, TP1 at 1.5R closes half and
moves the stop to breakeven, TP2 at 3R, conservative same-bar stop-first, 2%
daily loss stop. Costs: broker spread model (max(bar spread, 2026 M1 median for
that ET hour)) + $0.10 slippage per fill. R is after costs.

Data: live MT5 broker H1 via the read-only Wine script C:\\winpy\\live_snapshot_ro.py
(preferred), merged with data/broker/XAUUSD_H1.csv history. Fallback when MT5 is
unreachable: yfinance GC=F 1h shifted to spot by the live Swissquote basis
(clearly labelled in the data_source column). Forming bars are never used.

Idempotent: re-running on the same data rewrites the same rows. CLOSED rows are
frozen once logged; OPEN rows are updated in place; new trades are appended.
Trades entered before LIVE_START_UTC are labelled mode=backfill.

Usage
-----
  python scripts/paper_tracker.py                 # pull live MT5, update journal, print summary
  python scripts/paper_tracker.py --no-mt5        # skip MT5 (fallback data)
  python scripts/paper_tracker.py --json          # machine-readable summary on stdout
Outputs: journal/paper_trades.csv, journal/paper_summary.json
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.backtest import config as C  # noqa: E402
from research.backtest import engine as E  # noqa: E402

DEEP = ROOT / "research" / "deep-study-2026-11-14"
JOURNAL = ROOT / "journal"
TRADES_CSV = JOURNAL / "paper_trades.csv"
SUMMARY_JSON = JOURNAL / "paper_summary.json"
BROKER_DIR = ROOT / "data" / "broker"
WINE = "/home/box/wine/wine-11.21-staging-amd64-wow64/bin/wine"
WINEPREFIX = "/home/box/.wine-mt5"
WIN_BROKER = Path(WINEPREFIX) / "drive_c" / "winpy" / "broker"
ET = "America/New_York"
IST = "Asia/Kolkata"
SERVER_MINUS_ET_HOURS = 7  # MetaQuotes-Demo server clock = ET+7 all year

BACKFILL_START_ET = pd.Timestamp("2026-10-16 00:00", tz=ET)  # 4 weeks before the 13 Nov close
LIVE_START_UTC = pd.Timestamp("2026-11-14 00:00", tz="UTC")  # tracker created; later entries are forward/live
# History start for the feature build: enough for the 200-session SMA warmup, and it must be a
# date on US daylight time (EDT). research.backtest.data.resample_4h anchors its 4H bins to the
# first day's midnight, so starting on an EDT day reproduces the exact 4H bins the 2009-2026
# HistData and broker studies used (both series start on EDT days). An EST start shifts the 4H
# bins by one hour and changes the 4H trend flag on some days.
HISTORY_FROM_ET = pd.Timestamp("2024-10-01", tz=ET)

SETUPS = {
    "ny_lon_brk_d4h": "NY London-range break (D+4H)",
    "fomc_cont": "FOMC continuation (+60 min)",
    "donch20_long": "Donchian-20 long (18:00 ET)",
    "asia_brk_trend": "Asia breakout (clean, D+4H)",
}
# 2026 M1 median spread ($) by ET hour, used if data/broker/XAUUSD_M1.csv is absent.
SPREAD_PROFILE_FALLBACK = {0: 0.2, 1: 0.19, 2: 0.16, 3: 0.16, 4: 0.16, 5: 0.15, 6: 0.17, 7: 0.16, 8: 0.13,
                           9: 0.13, 10: 0.13, 11: 0.13, 12: 0.14, 13: 0.13, 14: 0.13, 15: 0.15, 16: 0.15,
                           17: 0.15, 18: 0.3, 19: 0.3, 20: 0.2, 21: 0.18, 22: 0.18, 23: 0.2}
COLUMNS = ["trade_id", "mode", "setup", "setup_label", "direction", "entry_time_utc", "entry_time_ist",
           "entry", "sl", "tp1_1p5r", "tp2_3r", "risk_per_oz", "status", "exit_time_utc", "exit_time_ist",
           "exit_reason", "tp1_hit", "result", "r", "mark_r", "data_source", "first_logged_utc", "updated_utc"]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _server_csv_to_frame(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    naive = pd.to_datetime(raw["time"], unit="s") - pd.Timedelta(hours=SERVER_MINUS_ET_HOURS)
    idx = pd.DatetimeIndex(naive).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
    df = pd.DataFrame({"Open": raw["open"].to_numpy(), "High": raw["high"].to_numpy(), "Low": raw["low"].to_numpy(),
                       "Close": raw["close"].to_numpy(), "Volume": raw["tick_volume"].to_numpy(),
                       "spread_bar_usd": (raw["spread"] * 0.01).to_numpy()}, index=idx)
    df = df[df.index.notna()]
    df.index.name = "Datetime"
    return df[~df.index.duplicated(keep="last")].sort_index()


def _cached_broker_h1() -> pd.DataFrame | None:
    p = BROKER_DIR / "XAUUSD_H1.csv"
    if not p.exists():
        return None
    raw = pd.read_csv(p)
    idx = pd.to_datetime(raw["time_utc"], utc=True).dt.tz_convert(ET)
    df = pd.DataFrame({"Open": raw["open"].to_numpy(), "High": raw["high"].to_numpy(), "Low": raw["low"].to_numpy(),
                       "Close": raw["close"].to_numpy(), "Volume": raw["tick_volume"].to_numpy(),
                       "spread_bar_usd": raw["spread_usd"].to_numpy()}, index=pd.DatetimeIndex(idx, name="Datetime"))
    return df[~df.index.duplicated(keep="last")].sort_index()


def pull_mt5_snapshot(timeout: int = 120) -> dict | None:
    """Run the read-only Wine snapshot (H1 bars, account, positions, deals)."""
    win_script = Path(WINEPREFIX) / "drive_c" / "winpy" / "live_snapshot_ro.py"
    repo_script = ROOT / "scripts" / "mt5_wine" / "live_snapshot_ro.py"
    if repo_script.exists() and (not win_script.exists() or win_script.read_bytes() != repo_script.read_bytes()):
        win_script.write_bytes(repo_script.read_bytes())
    env = dict(os.environ, WINEPREFIX=WINEPREFIX, WINEDEBUG="-all", DISPLAY=os.environ.get("DISPLAY", ":3"))
    try:
        subprocess.run([WINE, r"C:\winpy\python.exe", r"C:\winpy\live_snapshot_ro.py", "8000"],
                       env=env, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    snap_p = WIN_BROKER / "live_snapshot.json"
    if not snap_p.exists():
        return None
    snap = json.loads(snap_p.read_text())
    pulled = pd.Timestamp(snap.get("pulled_at_utc"))
    if not snap.get("init") or (pd.Timestamp.now(tz="UTC") - pulled) > pd.Timedelta(minutes=10):
        return None
    return snap


def swissquote_mid() -> float | None:
    url = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        for plat in data:
            for prof in plat.get("spreadProfilePrices", []):
                if prof.get("spreadProfile") in ("prime", "standard", "elite") or True:
                    return 0.5 * (float(prof["bid"]) + float(prof["ask"]))
    except Exception:
        return None
    return None


def fallback_bars() -> tuple[pd.DataFrame | None, str]:
    """GC=F 1h shifted to spot by the live Swissquote basis; else cached broker history."""
    try:
        import yfinance as yf
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            g = yf.download("GC=F", period="730d", interval="1h", progress=False, auto_adjust=False)
        if isinstance(g.columns, pd.MultiIndex):
            g.columns = g.columns.get_level_values(0)
        mid = swissquote_mid()
        if g is not None and len(g) and mid:
            basis = float(g["Close"].iloc[-1]) - mid
            g = g[["Open", "High", "Low", "Close", "Volume"]].copy()
            for c in ("Open", "High", "Low", "Close"):
                g[c] = g[c] - basis
            g.index = pd.DatetimeIndex(g.index).tz_convert(ET)
            g.index.name = "Datetime"
            g["spread_bar_usd"] = 0.0
            return g, f"gcf_1h_minus_swissquote_basis({basis:+.2f})"
    except Exception:
        pass
    cached = _cached_broker_h1()
    return cached, "cached_broker_h1_STALE"


def load_bars(use_mt5: bool) -> tuple[pd.DataFrame, str, dict | None]:
    snap = pull_mt5_snapshot() if use_mt5 else None
    hist = _cached_broker_h1()
    if snap and (WIN_BROKER / "live_H1.csv").exists():
        live = _server_csv_to_frame(WIN_BROKER / "live_H1.csv")
        bars = pd.concat([hist, live]) if hist is not None else live
        bars = bars[~bars.index.duplicated(keep="last")].sort_index()
        src = "mt5_broker_live"
    else:
        bars, src = fallback_bars()
        if bars is None:
            raise SystemExit("no data source available (MT5, GC=F+Swissquote, cached broker)")
    bars = bars[bars.index >= HISTORY_FROM_ET]
    # Never use a forming bar: keep bars whose close (open + 1h) is in the past.
    now = pd.Timestamp.now(tz="UTC")
    bars = bars[(bars.index.tz_convert("UTC") + pd.Timedelta(hours=1)) <= now]
    return bars, src, snap


def spread_profile() -> dict:
    p = BROKER_DIR / "XAUUSD_M1.csv"
    if p.exists():
        m1 = pd.read_csv(p, usecols=["time_utc", "spread_usd"])
        h = pd.to_datetime(m1["time_utc"], utc=True).dt.tz_convert(ET).dt.hour
        prof = m1.groupby(h)["spread_usd"].median().to_dict()
        return {**SPREAD_PROFILE_FALLBACK, **prof}
    return SPREAD_PROFILE_FALLBACK


# ---------------------------------------------------------------------------
# Signals + paper books
# ---------------------------------------------------------------------------

class SpreadEngine(E.Engine):
    def _set(self, row):
        s = row.get("spread_usd")
        if s is not None and np.isfinite(s):
            C.SPREAD = float(s)

    def _try_enter(self, sig, row, t, equity):
        self._set(row)
        return super()._try_enter(sig, row, t, equity)

    def _manage(self, pos, row, t, equity, entry_bar=False):
        self._set(row)
        return super()._manage(pos, row, t, equity, entry_bar=entry_bar)


def build_frame(bars: pd.DataFrame, ds, p2) -> pd.DataFrame:
    prof = spread_profile()
    hour_typ = pd.Series(bars.index.hour, index=bars.index).map(prof).fillna(0.16)
    bars = bars.copy()
    bars["spread_usd"] = np.maximum(bars["spread_bar_usd"].fillna(0).to_numpy(), hour_typ.to_numpy())
    daily = ds.session_daily(bars[["Open", "High", "Low", "Close", "Volume"]])
    with contextlib.redirect_stdout(io.StringIO()):
        df = ds.build_exec_from_series(daily, bars, bars, "1h")
    df["spread_usd"] = bars["spread_usd"].reindex(df.index).to_numpy()
    df = df[df["d_sma200"].notna()].copy()
    cal = p2._load_news()
    df = p2.add_london_range(df)
    df = p2.add_donchian(df, daily)
    df = p2.add_news_flags(df, cal)
    return df


def run_books(df: pd.DataFrame, p2, rt) -> tuple[dict, dict]:
    p2.Engine = SpreadEngine
    win = df[df.index >= BACKFILL_START_ET]
    win_ad = win.copy()
    win_ad["nfp_blackout"] = win_ad["news_blackout"].astype(bool)
    asia_params = next(p for p in rt.A_VARIANTS if p["name"] == "A_trend_ma")
    books = {}
    with contextlib.redirect_stdout(io.StringIO()):
        C.SPREAD = 0.25
        books["ny_lon_brk_d4h"] = SpreadEngine(win_ad, lambda r: p2.sig_ny_lon_break(r, "d4h"), nfp_filter=True,
                                               setup_name="ny_lon_brk_d4h").run()[0]
        C.SPREAD = 0.25
        books["fomc_cont"] = SpreadEngine(win, lambda r: p2.sig_news(r, "FOMC", "cont"), nfp_filter=False,
                                          setup_name="fomc_cont").run()[0]
        C.SPREAD = 0.25
        books["donch20_long"] = p2.run_open_entry(win, lambda r: p2.sig_donchian_at_open(r, "long"), "donch20_long")[0]
        C.SPREAD = 0.25
        books["asia_brk_trend"] = SpreadEngine(win, lambda r: rt.breakout_signal(r, asia_params),
                                               setup_name="asia_brk_trend").run()[0]
    C.SPREAD = 0.25
    # Signals on the last completed bar that would enter at the next open (only if that book is flat).
    last = win.iloc[-1]
    last_ad = win_ad.iloc[-1]
    pending = {}
    fns = {"ny_lon_brk_d4h": (lambda: p2.sig_ny_lon_break(last_ad, "d4h")),
           "fomc_cont": (lambda: p2.sig_news(last, "FOMC", "cont")),
           "asia_brk_trend": (lambda: rt.breakout_signal(last, asia_params))}
    for k, fn in fns.items():
        open_now = any(t.exit_reason == "eod_flat" for t in books[k])
        if open_now:
            continue
        sig = fn()
        if sig is not None:
            pending[k] = {"direction": "BUY" if sig.direction == 1 else "SELL", "sl": round(float(sig.sl), 2),
                          "signal_bar_et": str(win.index[-1]), "enter_at": "next 1h open"}
    return books, pending


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

def _fmt(ts, tz) -> str:
    if ts is None or (isinstance(ts, float) and np.isnan(ts)) or pd.isna(ts):
        return ""
    return pd.Timestamp(ts).tz_convert(tz).strftime("%Y-%m-%d %H:%M" + (" IST" if tz == IST else "Z"))


def trades_to_rows(books: dict, last_bar: pd.Timestamp, src: str, now_utc: str) -> list[dict]:
    rows = []
    for setup, trades in books.items():
        for t in trades:
            is_open = t.exit_reason == "eod_flat" and pd.Timestamp(t.exit_time) >= last_bar
            et_utc = pd.Timestamp(t.entry_time).tz_convert("UTC")
            risk = abs(t.entry - t.sl_initial)
            r = round(float(t.r_multiple), 3)
            if is_open:
                result, status = "OPEN", "OPEN"
            else:
                status = "CLOSED"
                result = "WIN" if r > 0.05 else ("LOSS" if r < -0.05 else "BE")
            rows.append({
                "trade_id": f"{setup}|{et_utc.strftime('%Y-%m-%dT%H:%MZ')}|{'BUY' if t.direction == 1 else 'SELL'}",
                "mode": "backfill" if et_utc < LIVE_START_UTC else "live",
                "setup": setup, "setup_label": SETUPS[setup],
                "direction": "BUY" if t.direction == 1 else "SELL",
                "entry_time_utc": _fmt(t.entry_time, "UTC"), "entry_time_ist": _fmt(t.entry_time, IST),
                "entry": round(t.entry, 2), "sl": round(t.sl_initial, 2),
                "tp1_1p5r": round(t.tp1, 2), "tp2_3r": round(t.tp2, 2), "risk_per_oz": round(risk, 2),
                "status": status,
                "exit_time_utc": "" if is_open else _fmt(t.exit_time, "UTC"),
                "exit_time_ist": "" if is_open else _fmt(t.exit_time, IST),
                "exit_reason": "" if is_open else t.exit_reason,
                "tp1_hit": bool(t.tp1_done),
                "result": result,
                "r": "" if is_open else r,
                "mark_r": r if is_open else "",
                "data_source": src, "first_logged_utc": now_utc, "updated_utc": now_utc,
            })
    return rows


def merge(existing: pd.DataFrame | None, fresh: list[dict]) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    new_rows, closed_now = [], []
    old = {} if existing is None or existing.empty else {r["trade_id"]: r for r in existing.to_dict("records")}
    out = dict(old)
    for row in fresh:
        tid = row["trade_id"]
        prev = old.get(tid)
        if prev is None:
            out[tid] = row
            new_rows.append(row)
            if row["status"] == "CLOSED":
                closed_now.append(row)
            continue
        if prev.get("status") == "CLOSED":
            continue  # frozen
        row = dict(row)
        row["first_logged_utc"] = prev.get("first_logged_utc") or row["first_logged_utc"]
        row["data_source"] = prev.get("data_source") or row["data_source"]
        if row["status"] == "CLOSED":
            closed_now.append(row)
        elif all(str(prev.get(k)) == str(row.get(k)) for k in ("mark_r", "tp1_hit")):
            row["updated_utc"] = prev.get("updated_utc") or row["updated_utc"]
        out[tid] = row
    df = pd.DataFrame(list(out.values()))
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)
    df = df.reindex(columns=COLUMNS).sort_values(["entry_time_utc", "setup"]).reset_index(drop=True)
    return df, new_rows, closed_now


def summarize(df: pd.DataFrame) -> dict:
    out = {"per_setup": {}, "equity_curve_r": [], "equity_curve_usd": []}
    closed = df[df["status"] == "CLOSED"].copy()
    closed["r"] = pd.to_numeric(closed["r"], errors="coerce")
    closed = closed.sort_values("exit_time_utc")
    for setup, label in SETUPS.items():
        part = df[df["setup"] == setup]
        c = closed[closed["setup"] == setup]
        rec = {"label": label}
        for mode in ("all", "backfill", "live"):
            cc = c if mode == "all" else c[c["mode"] == mode]
            pp = part if mode == "all" else part[part["mode"] == mode]
            n = int(len(cc))
            wins = int((cc["r"] > 0.05).sum())
            gross_win = float(cc.loc[cc["r"] > 0, "r"].sum())
            gross_loss = float(-cc.loc[cc["r"] < 0, "r"].sum())
            rec[mode] = {"closed": n, "open": int((pp["status"] == "OPEN").sum()), "wins": wins,
                         "win_rate_pct": round(100 * wins / n, 1) if n else None,
                         "avg_r": round(float(cc["r"].mean()), 3) if n else None,
                         "total_r": round(float(cc["r"].sum()), 3) if n else 0.0,
                         "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None}
        out["per_setup"][setup] = rec
    cum, eq = 0.0, 100000.0
    for _, r in closed.iterrows():
        cum += float(r["r"])
        eq *= 1 + 0.005 * float(r["r"])
        out["equity_curve_r"].append({"t": r["exit_time_ist"], "setup": r["setup"], "mode": r["mode"],
                                      "cum_r": round(cum, 3)})
        out["equity_curve_usd"].append({"t": r["exit_time_ist"], "equity": round(eq, 2)})
    n = len(closed)
    wins = int((closed["r"] > 0.05).sum())
    out["total"] = {"closed": n, "open": int((df["status"] == "OPEN").sum()), "wins": wins,
                    "win_rate_pct": round(100 * wins / n, 1) if n else None,
                    "avg_r": round(float(closed["r"].mean()), 3) if n else None,
                    "total_r": round(float(closed["r"].sum()), 3) if n else 0.0,
                    "backfill_closed": int((closed["mode"] == "backfill").sum()),
                    "live_closed": int((closed["mode"] == "live").sum())}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-mt5", action="store_true", help="skip the MT5 pull and use the fallback data")
    ap.add_argument("--json", action="store_true", help="print the summary JSON")
    args = ap.parse_args()

    ds = _load("deep_dataset", DEEP / "dataset.py")
    p2 = _load("phase2_setups", DEEP / "phase2_setups.py")
    rt = _load("retest_setups", DEEP / "retest_setups.py")

    bars, src, snap = load_bars(not args.no_mt5)
    df = build_frame(bars, ds, p2)
    books, pending = run_books(df, p2, rt)
    now_utc = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%MZ")
    fresh = trades_to_rows(books, df.index[-1], src, now_utc)

    JOURNAL.mkdir(parents=True, exist_ok=True)
    existing = pd.read_csv(TRADES_CSV, dtype=str, keep_default_na=False) if TRADES_CSV.exists() else None
    table, new_rows, closed_now = merge(existing, fresh)
    table.to_csv(TRADES_CSV, index=False)

    summ = summarize(table)
    summ.update({
        "generated_utc": now_utc,
        "generated_ist": pd.Timestamp.now(tz=IST).strftime("%Y-%m-%d %H:%M IST"),
        "data_source": src,
        "last_completed_bar_ist": _fmt(df.index[-1], IST),
        "backfill_start_ist": _fmt(BACKFILL_START_ET, IST),
        "live_start_ist": _fmt(LIVE_START_UTC, IST),
        "pending_signals": pending,
        "new_rows_this_run": [r["trade_id"] for r in new_rows],
        "closed_this_run": [r["trade_id"] for r in closed_now if r.get("mode") == "live"],
        "note": "Paper only. Each setup is its own one-trade book, so books can overlap (live trading allows one trade total). "
                "Rows with mode=backfill were reconstructed from broker history on 2026-11-14, not logged in real time.",
    })
    if snap and snap.get("account"):
        summ["mt5_account"] = {**snap["account"], "pulled_at_utc": snap.get("pulled_at_utc")}
    SUMMARY_JSON.write_text(json.dumps(summ, indent=2) + "\n")

    if args.json:
        print(json.dumps(summ, indent=2))
    else:
        t = summ["total"]
        print(f"paper_tracker src={src} last_bar={summ['last_completed_bar_ist']} closed={t['closed']} open={t['open']} "
              f"winrate={t['win_rate_pct']} avgR={t['avg_r']} totalR={t['total_r']} (backfill {t['backfill_closed']}, live {t['live_closed']})")
        for k, v in summ["per_setup"].items():
            a = v["all"]
            print(f"  {k:15s} closed={a['closed']} open={a['open']} win%={a['win_rate_pct']} avgR={a['avg_r']} totR={a['total_r']}")
        for k, v in pending.items():
            print(f"  SIGNAL {k} {v['direction']} SL {v['sl']} -> {v['enter_at']} (bar {v['signal_bar_et']})")
        live_new = [r for r in new_rows if r["mode"] == "live"]
        for r in live_new:
            print(f"  NEW {r['trade_id']} {r['status']} entry {r['entry']} SL {r['sl']} TP1 {r['tp1_1p5r']}")
        for r in closed_now:
            if r["mode"] == "live":
                print(f"  CLOSED {r['trade_id']} {r['result']} {r['r']}R ({r['exit_reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

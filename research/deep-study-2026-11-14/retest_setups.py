#!/usr/bin/env python3
"""Walk-forward re-test of the A/B setups and of retrace entries.

All variants below were registered *before* looking at P&L. We report every
one, including losers. Costs are the existing model ($0.25 spread + $0.10
slippage per fill). Primary series is HistData spot XAUUSD 1h, 2009-03 to
2026-11-06. Walk-forward OOS years are 2012-2026; 2009-2011 are warmup only.

A full-sample number is not a playbook change unless the OOS years agree.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.backtest import config as C
from research.backtest.engine import (
    Engine,
    Signal,
    buy_fill,
    exit_fill,
    run_engine,
    sell_fill,
    size_lots,
)
from research.backtest.metrics import summarize, trades_frame
from research.backtest.setups import _atr, _finite, _next_level, _sl_valid, sweep as sweep_eval

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
RESULTS = STUDY / "results"
PROC = ROOT / "data" / "processed"
OOS_START = pd.Timestamp("2012-01-01", tz="America/New_York")


def _cache_path() -> Path:
    PROC.mkdir(parents=True, exist_ok=True)
    return PROC / "XAUUSD_1h_exec.pkl"


def load_exec(force: bool = False) -> pd.DataFrame:
    path = _cache_path()
    if path.exists() and not force:
        df = pickle.loads(path.read_bytes())
        print(f"loaded exec cache {path} rows={len(df)}")
        return df
    # Import by path: the folder name contains a dash.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "deep_dataset", STUDY / "dataset.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("building XAUUSD 1h feature frame (no look-ahead)...")
    df = mod.build_xauusd_exec("1h")
    # Warmup: need a 200-day SMA.
    df = df[df["d_sma200"].notna()].copy()
    path.write_bytes(pickle.dumps(df, protocol=4))
    print(f"wrote {path} rows={len(df)} {df.index.min()} -> {df.index.max()}")
    return df


# ---------------------------------------------------------------------------
# Pre-registered A-setup variants
# ---------------------------------------------------------------------------

A_VARIANTS = [
    # baseline: current playbook mechanical A-setup (no hard MA gate)
    dict(name="A_base", max_sl_atr=3.0, sl_mode="far", entry="next_open",
         trend="none", london_only=False, no_chase=0.5),
    dict(name="A_cap_2x", max_sl_atr=2.0, sl_mode="far", entry="next_open",
         trend="none", london_only=False, no_chase=0.5),
    dict(name="A_cap_2_5x", max_sl_atr=2.5, sl_mode="far", entry="next_open",
         trend="none", london_only=False, no_chase=0.5),
    dict(name="A_cap_4x", max_sl_atr=4.0, sl_mode="far", entry="next_open",
         trend="none", london_only=False, no_chase=0.5),
    dict(name="A_cap_none", max_sl_atr=99.0, sl_mode="far", entry="next_open",
         trend="none", london_only=False, no_chase=0.5),
    # today's question: stop at the Asia midpoint so a wide range can still trade
    dict(name="A_half_stop", max_sl_atr=3.0, sl_mode="mid", entry="next_open",
         trend="none", london_only=False, no_chase=0.5),
    dict(name="A_half_stop_nocap", max_sl_atr=99.0, sl_mode="mid", entry="next_open",
         trend="none", london_only=False, no_chase=0.5),
    # live playbook soft filters
    dict(name="A_4h_ma", max_sl_atr=3.0, sl_mode="far", entry="next_open",
         trend="h4_ma", london_only=False, no_chase=0.5),
    dict(name="A_trend_ma", max_sl_atr=3.0, sl_mode="far", entry="next_open",
         trend="d4h_ma", london_only=False, no_chase=0.5),
    dict(name="A_london", max_sl_atr=3.0, sl_mode="far", entry="next_open",
         trend="none", london_only=True, no_chase=0.5),
    dict(name="A_london_4h", max_sl_atr=3.0, sl_mode="far", entry="next_open",
         trend="h4_ma", london_only=True, no_chase=0.5),
    # retrace entries after the close-break, instead of next-open chase
    dict(name="A_retest_level", max_sl_atr=3.0, sl_mode="far", entry="retest_0",
         trend="none", london_only=False, no_chase=0.5),
    dict(name="A_retest_382", max_sl_atr=3.0, sl_mode="far", entry="retest_382",
         trend="none", london_only=False, no_chase=0.5),
    dict(name="A_retest_50", max_sl_atr=3.0, sl_mode="far", entry="retest_50",
         trend="none", london_only=False, no_chase=0.5),
    dict(name="A_retest_382_half", max_sl_atr=3.0, sl_mode="mid", entry="retest_382",
         trend="none", london_only=False, no_chase=0.5),
]

B_VARIANTS = [
    dict(name="B_unfiltered", trend="none", ny_only=False),
    dict(name="B_trend_ma", trend="d4h_ma", ny_only=False),
    dict(name="B_ny_trend", trend="d4h_ma", ny_only=True),
]


def _trend_ok(row: pd.Series, direction: int, trend: str) -> bool:
    if trend in ("none", None):
        return True
    if trend == "d4h_ma":
        key = "trend_up_ma" if direction == 1 else "trend_down_ma"
        return bool(row.get(key, False))
    if trend == "h4_ma":
        key = "h4_trend_up_ma" if direction == 1 else "h4_trend_down_ma"
        return bool(row.get(key, False))
    if trend == "h4_struct":
        if direction == 1:
            return bool(row.get("h4_higher_lows", False)) and not bool(row.get("h4_lower_highs", False))
        return bool(row.get("h4_lower_highs", False))
    return True


def _stop_price(row: pd.Series, direction: int, sl_mode: str, atr: float, ahi: float, alo: float) -> float:
    buf = C.SL_BUFFER_ATR * atr
    mid = 0.5 * (ahi + alo)
    if sl_mode == "mid":
        return (mid - buf) if direction == 1 else (mid + buf)
    # far side of the Asia range
    return (alo - buf) if direction == 1 else (ahi + buf)


def breakout_signal(row: pd.Series, params: dict) -> Signal | None:
    ts = row.name
    hour = ts.hour if hasattr(ts, "hour") else -1
    if hour < C.ASIA_END_HOUR or hour >= C.BREAKOUT_ENTRY_UNTIL_HOUR:
        return None
    if params.get("london_only") and hour >= C.LONDON_END_HOUR:
        return None
    if not _finite(row.get("asia_high")) or not _finite(row.get("asia_low")):
        return None
    ahi, alo = float(row["asia_high"]), float(row["asia_low"])
    rng = ahi - alo
    if rng < C.MIN_SL:
        return None
    atr = _atr(row)
    if not np.isfinite(atr) or atr <= 0:
        return None
    close = float(row["Close"])
    no_chase = float(params.get("no_chase", 0.5))

    def _maybe(direction: int, flag: bool, extended: bool) -> Signal | None:
        if not flag or extended:
            return None
        if not _trend_ok(row, direction, params.get("trend", "none")):
            return None
        sl = _stop_price(row, direction, params["sl_mode"], atr, ahi, alo)
        planned = close
        dist = abs(planned - sl)
        if dist < C.MIN_SL:
            return None
        if dist > float(params["max_sl_atr"]) * atr:
            return None
        if direction == 1 and sl >= planned:
            return None
        if direction == -1 and sl <= planned:
            return None
        return Signal(
            setup="breakout",
            direction=direction,
            sl=sl,
            reason=f"{params['name']}",
            next_level=_next_level(row, direction, planned),
        )

    if bool(row.get("asia_first_close_up", False)):
        sig = _maybe(1, True, (close - ahi) > no_chase * rng)
        if sig:
            return sig
    if bool(row.get("asia_first_close_down", False)):
        sig = _maybe(-1, True, (alo - close) > no_chase * rng)
        if sig:
            return sig
    return None


def sweep_signal(row: pd.Series, params: dict) -> Signal | None:
    sess = str(row.get("session", ""))
    if params.get("ny_only") and sess != "ny":
        return None
    trend = params.get("trend", "none")
    # Reuse the existing fade-sweep detector, then apply our trend / NY gate.
    # The factory uses _trend_ok with boolean flags; call unfiltered and re-check.
    sig = sweep_eval(row, trend_filter=False, strict=False)
    if sig is None:
        return None
    if not _trend_ok(row, sig.direction, trend):
        return None
    if params.get("ny_only") and sess != "ny":
        return None
    sig.reason = params["name"]
    return sig


# ---------------------------------------------------------------------------
# Retest-entry simulator (limit after the close-break, same costs / 1.5R-3R)
# ---------------------------------------------------------------------------

def _retrace_price(level: float, close: float, frac: float) -> float:
    # frac=0 -> broken level; 0.382 / 0.50 = fib retrace of close-to-level.
    return close + frac * (level - close)


def run_retest(df: pd.DataFrame, params: dict, start_equity: float = C.START_EQUITY):
    """Enter on a retrace toward the broken Asia level after a close-break.

    Limit is live until 13:00 ET the same session (or the next bar would be
    the late-NY cutoff). If the retrace never trades, there is no position.
    """
    entry_mode = params["entry"]
    frac = {"retest_0": 0.0, "retest_382": 0.382, "retest_50": 0.50}[entry_mode]
    n = len(df)
    idx = df.index
    equity = start_equity
    trades = []
    pos = None
    pending = None  # dict with Signal + limit + expiry index
    sess_start_eq = equity
    sess_realized = 0.0
    last_session = None
    eq_times, eq_vals = [], []
    engine = Engine(df, lambda r: None)  # only for _manage / _try_enter helpers

    for i in range(n):
        row = df.iloc[i]
        t = idx[i]
        sess = row["session_date"]
        if last_session is None or sess != last_session:
            sess_start_eq = equity
            sess_realized = 0.0
            last_session = sess
            pending = None  # limits do not carry over a new Asia range

        if pos is not None:
            engine._manage(pos, row, t, equity)
            if not pos.open:
                equity += pos.pnl
                sess_realized += pos.pnl
                trades.append(pos)
                pos = None

        # Try to fill a pending retrace limit on this bar (after managing).
        if pos is None and pending is not None:
            if i > pending["expire_i"] or str(row.get("session", "")) == "break":
                pending = None
            else:
                sig: Signal = pending["sig"]
                limit = pending["limit"]
                o, h, l = float(row["Open"]), float(row["High"]), float(row["Low"])
                touched = (l <= limit <= h) or (sig.direction == 1 and o <= limit) or (
                    sig.direction == -1 and o >= limit
                )
                # Gapped through the stop before the limit: cancel.
                mid_open = o
                fill_open = buy_fill(mid_open) if sig.direction == 1 else sell_fill(mid_open)
                gapped_sl = (sig.direction == 1 and fill_open <= sig.sl) or (
                    sig.direction == -1 and fill_open >= sig.sl
                )
                if gapped_sl:
                    pending = None
                elif touched:
                    # Fill at the better of the limit or the gapped open, plus costs.
                    mid = limit
                    if sig.direction == 1 and o < limit:
                        mid = o
                    if sig.direction == -1 and o > limit:
                        mid = o
                    # Build a one-row entry using a synthetic open = mid.
                    fake = row.copy()
                    fake["Open"] = mid
                    pos = engine._try_enter(sig, fake, t, equity)
                    pending = None
                    if pos is not None:
                        engine._manage(pos, row, t, equity, entry_bar=True)
                        if not pos.open:
                            equity += pos.pnl
                            sess_realized += pos.pnl
                            trades.append(pos)
                            pos = None

        mtm = equity
        if pos is not None:
            mtm += (pos.direction * (float(row["Close"]) - pos.entry) * pos.remaining * C.CONTRACT_OZ)
            if pos.tp1_done:
                mtm += pos.pnl
        eq_times.append(t)
        eq_vals.append(mtm)

        if pos is None and pending is None:
            sig = breakout_signal(row, {**params, "entry": "next_open"})
            if sig is not None:
                # Limit from this bar's close toward the broken level.
                ahi, alo = float(row["asia_high"]), float(row["asia_low"])
                level = ahi if sig.direction == 1 else alo
                limit = _retrace_price(level, float(row["Close"]), frac)
                # If the limit is on the wrong side of the stop or already
                # beyond the close (shouldn't happen), skip.
                if sig.direction == 1 and not (sig.sl < limit <= float(row["Close"]) + 1e-9):
                    continue
                if sig.direction == -1 and not (sig.sl > limit >= float(row["Close"]) - 1e-9):
                    continue
                # Expire at the last bar with hour < 13 of this session.
                expire_i = i
                for j in range(i + 1, min(n, i + 16)):
                    if df.iloc[j]["session_date"] != sess:
                        break
                    if idx[j].hour >= C.BREAKOUT_ENTRY_UNTIL_HOUR:
                        break
                    expire_i = j
                pending = {"sig": sig, "limit": limit, "expire_i": expire_i}

    if pos is not None:
        last = df.iloc[-1]
        px = exit_fill(pos.direction, float(last["Close"]))
        engine._close(pos, idx[-1], px, pos.remaining, "eod_flat")
        equity += pos.pnl
        trades.append(pos)

    eq = pd.DataFrame({"equity": eq_vals}, index=pd.DatetimeIndex(eq_times, name="Datetime"))
    return trades, eq


def run_next_open(df: pd.DataFrame, params: dict):
    def fn(row):
        return breakout_signal(row, params)

    return run_engine(df, fn, setup_name=params["name"])


def run_sweep_book(df: pd.DataFrame, params: dict):
    def fn(row):
        return sweep_signal(row, params)

    return run_engine(df, fn, setup_name=params["name"], trend_filter=params.get("trend") == "d4h_ma")


# ---------------------------------------------------------------------------
# Metrics + walk-forward
# ---------------------------------------------------------------------------

def _metrics_row(label: str, trades, equity) -> dict:
    s = summarize(trades, equity)
    s["variant"] = label
    s["n"] = int(s.get("n") or 0)
    return s


def oos_slices(trades: pd.DataFrame, equity: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    t["entry_time"] = pd.to_datetime(t["entry_time"])
    if t["entry_time"].dt.tz is None:
        t["entry_time"] = t["entry_time"].dt.tz_localize("America/New_York")
    t = t[t["entry_time"] >= OOS_START]
    t["year"] = t["entry_time"].dt.year
    rows = []
    # Pooled OOS (R-based; DD from a reset $100k stream of OOS trades is approximate)
    if len(t):
        # Rebuild a compact equity from OOS trade PnL for DD (trade-close equity only).
        eq = 100_000.0 + t.sort_values("entry_time")["pnl"].cumsum()
        eq_df = pd.DataFrame({"equity": eq.values}, index=pd.RangeIndex(len(eq)))
        sm = summarize(t, eq_df)
        sm["variant_slice"] = "OOS_2012_2026"
        sm["year"] = "2012-2026"
        rows.append(sm)
        for y, part in t.groupby("year"):
            eqy = 100_000.0 + part.sort_values("entry_time")["pnl"].cumsum()
            eq_df = pd.DataFrame({"equity": eqy.values}, index=pd.RangeIndex(len(eqy)))
            sm = summarize(part, eq_df)
            sm["variant_slice"] = f"OOS_{y}"
            sm["year"] = int(y)
            rows.append(sm)
    return pd.DataFrame(rows)


def _stability(oos_year_rows: pd.DataFrame) -> dict:
    yrs = oos_year_rows[oos_year_rows["year"].apply(lambda x: isinstance(x, (int, np.integer)))]
    if yrs.empty:
        return {}
    pos = int((yrs["avg_r"] > 0).sum())
    return {
        "oos_years": int(len(yrs)),
        "oos_years_positive": pos,
        "oos_year_share_positive": pos / len(yrs) if len(yrs) else np.nan,
        "oos_avg_r_mean": float(yrs["avg_r"].mean()),
        "oos_avg_r_std": float(yrs["avg_r"].std(ddof=1)) if len(yrs) > 1 else np.nan,
        "oos_min_year_avg_r": float(yrs["avg_r"].min()),
        "oos_min_year": int(yrs.loc[yrs["avg_r"].idxmin(), "year"]) if len(yrs) else None,
        "oos_trade_count": int(yrs["n"].sum()),
    }


def run_all(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    oos_rows = []
    trade_dir = RESULTS / "trades"
    trade_dir.mkdir(exist_ok=True)

    def _record(name: str, trades, equity, family: str):
        tf = trades_frame(trades)
        if not tf.empty:
            tf.to_csv(trade_dir / f"trades_{name}.csv", index=False)
        if equity is not None and len(equity):
            equity.to_csv(RESULTS / "trades" / f"equity_{name}.csv")
        full = summarize(trades, equity)
        full["variant"] = name
        full["family"] = family
        full["sample"] = "full_2009_2026"
        # In-sample (before OOS) vs OOS pooled
        if not tf.empty:
            et = pd.to_datetime(tf["entry_time"])
            if et.dt.tz is None:
                et = et.dt.tz_localize("America/New_York")
                tf = tf.copy()
                tf["entry_time"] = et
            is_ = tf[pd.to_datetime(tf["entry_time"]) < OOS_START]
            oos = tf[pd.to_datetime(tf["entry_time"]) >= OOS_START]
        else:
            is_ = tf
            oos = tf
        is_s = summarize(is_, None)
        is_s["variant"] = name
        is_s["family"] = family
        is_s["sample"] = "IS_2009_2011"
        oos_s = summarize(oos, None)
        oos_s["variant"] = name
        oos_s["family"] = family
        oos_s["sample"] = "OOS_2012_2026"
        stab = _stability(oos_slices(tf, equity))
        oos_s.update(stab)
        full.update({f"full_{k}": v for k, v in stab.items()})
        summary_rows.extend([full, is_s, oos_s])
        sl = oos_slices(tf, equity)
        if not sl.empty:
            sl["variant"] = name
            sl["family"] = family
            oos_rows.append(sl)
        print(
            f"{name:20s} full n={full.get('n')} avgR={full.get('avg_r')} PF={full.get('profit_factor')} "
            f"| OOS n={oos_s.get('n')} avgR={oos_s.get('avg_r')} PF={oos_s.get('profit_factor')} "
            f"pos_years={stab.get('oos_years_positive')}/{stab.get('oos_years')}"
        )

    for p in A_VARIANTS:
        print("running", p["name"], "...")
        if str(p["entry"]).startswith("retest"):
            trades, eq = run_retest(df, p)
        else:
            trades, eq = run_next_open(df, p)
        _record(p["name"], trades, eq, "A")

    for p in B_VARIANTS:
        print("running", p["name"], "...")
        trades, eq = run_sweep_book(df, p)
        _record(p["name"], trades, eq, "B")

    summary = pd.DataFrame(summary_rows)
    yearly = pd.concat(oos_rows, ignore_index=True) if oos_rows else pd.DataFrame()
    summary.to_csv(RESULTS / "wf_summary.csv", index=False)
    yearly.to_csv(RESULTS / "wf_oos_years.csv", index=False)
    return summary, yearly


# ---------------------------------------------------------------------------
# Path study: how often do retraces fill after a close-break? (not a book)
# ---------------------------------------------------------------------------

def retrace_fill_study(df: pd.DataFrame) -> pd.DataFrame:
    """For every valid first close-break, measure 0/38.2/50/61.8 fill rates.

    Horizon is the same session through 13:00 ET. Continuation = a new extreme
    in the breakout direction before a stop at the far side of the Asia range.
    """
    rows = []
    idx = df.index
    n = len(df)
    for i in range(n):
        row = df.iloc[i]
        ts = idx[i]
        if ts.hour < C.ASIA_END_HOUR or ts.hour >= C.BREAKOUT_ENTRY_UNTIL_HOUR:
            continue
        if not (bool(row.get("asia_first_close_up", False)) or bool(row.get("asia_first_close_down", False))):
            continue
        if not _finite(row.get("asia_high")):
            continue
        ahi, alo = float(row["asia_high"]), float(row["asia_low"])
        rng = ahi - alo
        if rng < C.MIN_SL:
            continue
        close = float(row["Close"])
        if bool(row.get("asia_first_close_up", False)):
            direction, level = 1, ahi
            if (close - ahi) > 0.5 * rng:
                continue
        else:
            direction, level = -1, alo
            if (alo - close) > 0.5 * rng:
                continue
        atr = _atr(row)
        if not np.isfinite(atr):
            continue
        sl = (alo - 0.15 * atr) if direction == 1 else (ahi + 0.15 * atr)
        sess = row["session_date"]
        fracs = (0.0, 0.382, 0.50, 0.618)
        filled = {f: False for f in fracs}
        fill_bar = {f: None for f in fracs}
        stopped_before = {f: False for f in fracs}
        # After a fill, track MFE in R (far-side stop distance from the limit).
        mfe = {f: 0.0 for f in fracs}
        mae = {f: 0.0 for f in fracs}
        hit_sl_after = {f: False for f in fracs}
        ext_1p5 = {f: False for f in fracs}
        for j in range(i + 1, min(n, i + 16)):
            r2 = df.iloc[j]
            if r2["session_date"] != sess or idx[j].hour >= C.BREAKOUT_ENTRY_UNTIL_HOUR:
                break
            h, l = float(r2["High"]), float(r2["Low"])
            for f in fracs:
                if stopped_before[f] or hit_sl_after[f]:
                    continue
                limit = _retrace_price(level, close, f)
                # Stop before fill?
                sl_touch = (direction == 1 and l <= sl) or (direction == -1 and h >= sl)
                if not filled[f] and sl_touch:
                    stopped_before[f] = True
                    continue
                if not filled[f] and (l <= limit <= h):
                    filled[f] = True
                    fill_bar[f] = idx[j]
                if filled[f]:
                    entry = limit
                    risk = abs(entry - sl)
                    if risk <= 0:
                        continue
                    fav = (h - entry) if direction == 1 else (entry - l)
                    adv = (entry - l) if direction == 1 else (h - entry)
                    mfe[f] = max(mfe[f], fav / risk)
                    mae[f] = max(mae[f], adv / risk)
                    if sl_touch:
                        hit_sl_after[f] = True
                    if mfe[f] >= 1.5:
                        ext_1p5[f] = True
        asia_atr = rng / atr if atr else np.nan
        for f in fracs:
            rows.append({
                "event_time": ts,
                "session_date": sess,
                "direction": "BUY" if direction == 1 else "SELL",
                "frac": f,
                "asia_range": rng,
                "asia_over_atr": asia_atr,
                "wide_3x": bool(asia_atr > 3.0) if np.isfinite(asia_atr) else False,
                "filled": filled[f],
                "stopped_before_fill": stopped_before[f],
                "mfe_r": mfe[f] if filled[f] else np.nan,
                "mae_r": mae[f] if filled[f] else np.nan,
                "hit_sl_after_fill": hit_sl_after[f] if filled[f] else False,
                "reached_1_5R": ext_1p5[f] if filled[f] else False,
                "hour_et": ts.hour,
                "year": ts.year,
            })
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "retrace_events.csv", index=False)
    return out


def retrace_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, part in [("all", events), ("OOS", events[events["year"] >= 2012]),
                        ("wide_3x_OOS", events[(events["year"] >= 2012) & (events["wide_3x"])])]:
        for f, g in part.groupby("frac"):
            n = len(g)
            filled = g[g["filled"]]
            rows.append({
                "slice": label,
                "frac": f,
                "events": n // max(1, events["frac"].nunique()) if False else len(g),
                "n": n,
                "fill_rate": float(g["filled"].mean()) if n else np.nan,
                "stopped_before_rate": float(g["stopped_before_fill"].mean()) if n else np.nan,
                "fill_then_1_5R_rate": float(filled["reached_1_5R"].mean()) if len(filled) else np.nan,
                "fill_then_sl_rate": float(filled["hit_sl_after_fill"].mean()) if len(filled) else np.nan,
                "mean_mfe_r_if_filled": float(filled["mfe_r"].mean()) if len(filled) else np.nan,
                "mean_mae_r_if_filled": float(filled["mae_r"].mean()) if len(filled) else np.nan,
            })
    tab = pd.DataFrame(rows)
    tab.to_csv(RESULTS / "retrace_fill_summary.csv", index=False)
    return tab


# ---------------------------------------------------------------------------
# Discretionary "rejection then retrace to zone" path study (today's type)
# ---------------------------------------------------------------------------

def rejection_retrace_study(df: pd.DataFrame) -> pd.DataFrame:
    """After a 1h rejection at 4H/daily supply (sell) or demand (buy).

    Event: London/NY rejection close in a swing zone (same shape as the
    playbook pullback detector), then price leaves the zone. We ask how
    often a 38.2% or 50% retrace of the subsequent push fills within 8
    hours, and what happens after the fill. Sells are also reported in a
    downtrend-only slice (today's setup).
    """
    from research.backtest.setups import _rejection, _tagged_zones

    rows = []
    idx = df.index
    n = len(df)
    for i in range(n - 2):
        row = df.iloc[i]
        if str(row.get("session", "")) not in ("london", "ny"):
            continue
        atr = _atr(row)
        if not np.isfinite(atr):
            continue
        for direction, side in ((-1, "supply"), (1, "demand")):
            if not _rejection(row, direction):
                continue
            zones = _tagged_zones(row, side)
            if not zones:
                continue
            extreme = float(row["High"]) if direction == -1 else float(row["Low"])
            close = float(row["Close"])
            sl = (extreme + 0.15 * atr) if direction == -1 else (extreme - 0.15 * atr)
            # Subsequent push: look forward until 8 hours or a new extreme the other way.
            push_ext = close
            push_end = None
            left = False
            for j in range(i + 1, min(n, i + 9)):
                r2 = df.iloc[j]
                h, l, c = float(r2["High"]), float(r2["Low"]), float(r2["Close"])
                if direction == -1:
                    if l < push_ext:
                        push_ext = l
                        push_end = j
                    if c < min(z[2] for z in zones):  # closed below zone floor
                        left = True
                else:
                    if h > push_ext:
                        push_ext = h
                        push_end = j
                    if c > max(z[3] for z in zones):
                        left = True
            if not left or push_end is None:
                continue
            move = abs(push_ext - extreme)
            if move < 0.5 * atr:
                continue
            for frac in (0.382, 0.50):
                # Retrace from the push extreme back toward the rejection.
                limit = push_ext + frac * (extreme - push_ext)
                filled = False
                mfe = mae = 0.0
                hit_sl = False
                reached = False
                for k in range(push_end + 1, min(n, push_end + 9)):
                    r3 = df.iloc[k]
                    h, l = float(r3["High"]), float(r3["Low"])
                    sl_touch = (direction == -1 and h >= sl) or (direction == 1 and l <= sl)
                    if not filled and sl_touch:
                        break
                    if not filled and (l <= limit <= h):
                        filled = True
                    if filled:
                        risk = abs(limit - sl)
                        if risk <= 0:
                            break
                        fav = (limit - l) if direction == -1 else (h - limit)
                        adv = (h - limit) if direction == -1 else (limit - l)
                        mfe = max(mfe, fav / risk)
                        mae = max(mae, adv / risk)
                        if sl_touch:
                            hit_sl = True
                            break
                        if mfe >= 1.5:
                            reached = True
                rows.append({
                    "event_time": idx[i],
                    "year": idx[i].year,
                    "direction": "SELL" if direction == -1 else "BUY",
                    "frac": frac,
                    "downtrend": bool(row.get("trend_down_ma", False)),
                    "uptrend": bool(row.get("trend_up_ma", False)),
                    "filled": filled,
                    "mfe_r": mfe if filled else np.nan,
                    "mae_r": mae if filled else np.nan,
                    "reached_1_5R": reached if filled else False,
                    "hit_sl": hit_sl if filled else False,
                })
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "rejection_retrace_events.csv", index=False)
    return out


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    df = load_exec()
    print("exec", len(df), df.index.min(), "->", df.index.max())
    summary, yearly = run_all(df)
    print("\n=== retrace fill study (close-break events) ===")
    ev = retrace_fill_study(df)
    tab = retrace_summary(ev)
    print(tab.to_string(index=False))
    print("\n=== rejection-retrace study ===")
    ev2 = rejection_retrace_study(df)
    if ev2.empty:
        print("no rejection events")
    else:
        rows = []
        for slice_name, part in [
            ("all_OOS", ev2[ev2["year"] >= 2012]),
            ("sells_downtrend_OOS", ev2[(ev2["year"] >= 2012) & (ev2["direction"] == "SELL") & (ev2["downtrend"])]),
            ("buys_uptrend_OOS", ev2[(ev2["year"] >= 2012) & (ev2["direction"] == "BUY") & (ev2["uptrend"])]),
        ]:
            for f, g in part.groupby("frac"):
                filled = g[g["filled"]]
                rows.append({
                    "slice": slice_name, "frac": f, "n": len(g),
                    "fill_rate": float(g["filled"].mean()) if len(g) else np.nan,
                    "fill_then_1_5R": float(filled["reached_1_5R"].mean()) if len(filled) else np.nan,
                    "fill_then_sl": float(filled["hit_sl"].mean()) if len(filled) else np.nan,
                    "mean_mfe_r": float(filled["mfe_r"].mean()) if len(filled) else np.nan,
                })
        tab2 = pd.DataFrame(rows)
        tab2.to_csv(RESULTS / "rejection_retrace_summary.csv", index=False)
        print(tab2.to_string(index=False))
    # Wide-range subset of A_base vs A_half_stop (from saved trades + event tags)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())

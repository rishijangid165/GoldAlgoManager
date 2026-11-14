#!/usr/bin/env python3
"""Broker-data retest of playbook v3 setups (2026-11-14).

Same pre-registered rules and adoption bar as
research/deep-study-2026-11-14/phase2_setups.py (signal functions are imported,
not rewritten). Only the price source and the cost model change:

* Prices: MetaQuotes-Demo MT5 XAUUSD H1 (2009-10-13 .. 2026-11-13), converted
  from server time (ET+7) to America/New_York. Daily = COMEX session daily built
  from those H1 bars, exactly as the HistData study did.
* Spread: per bar, max(MT5 bar spread, 2026 M1 median spread for that ET hour),
  plus the same $0.10 slippage per fill. A second run with the old fixed $0.25
  spread isolates the data effect from the cost effect.

No variants were added. Asia breakout is reported with the same three
pre-registered parameter sets as retest_setups.py (A_base, A_4h_ma, A_trend_ma).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from research.backtest import config as C  # noqa: E402
from research.backtest import engine as E  # noqa: E402

DEEP = ROOT / "research" / "deep-study-2026-11-14"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bd = _load("broker_data", HERE / "broker_data.py")
ds = _load("deep_dataset", DEEP / "dataset.py")
p2 = _load("phase2_setups", DEEP / "phase2_setups.py")
rt = _load("retest_setups", DEEP / "retest_setups.py")


class BrokerEngine(E.Engine):
    """Engine whose spread is taken from the bar being filled."""

    use_bar_spread = True

    def _set(self, row):
        if self.use_bar_spread:
            s = row.get("spread_usd")
            if s is not None and np.isfinite(s):
                C.SPREAD = float(s)

    def _try_enter(self, sig, row, t, equity):
        self._set(row)
        return super()._try_enter(sig, row, t, equity)

    def _manage(self, pos, row, t, equity, entry_bar=False):
        self._set(row)
        return super()._manage(pos, row, t, equity, entry_bar=entry_bar)


def _run_engine(df, fn, **kw):
    return BrokerEngine(df, fn, **kw).run()


p2.Engine = BrokerEngine
p2.run_engine = _run_engine
rt.run_engine = _run_engine

V3 = ["A_ny_lon_brk_d4h", "B_fomc_cont", "C_donch20_long", "A_base", "A_4h_ma", "A_trend_ma"]
LABEL = {
    "A_ny_lon_brk_d4h": "NY London-range break, D+4H",
    "B_fomc_cont": "FOMC continuation (+60 min)",
    "C_donch20_long": "Donchian-20 long @18:00 ET",
    "A_base": "Asia breakout (mechanical)",
    "A_4h_ma": "Asia breakout + 4H MA",
    "A_trend_ma": "Asia breakout + D+4H MA",
}


def build_frame() -> pd.DataFrame:
    h1 = bd.load_tf("H1")
    h1 = h1[h1.index.notna()].copy()
    h1["spread_usd"] = bd.spread_model(h1)
    daily = ds.session_daily(h1[["Open", "High", "Low", "Close", "Volume"]])
    df = ds.build_exec_from_series(daily, h1, h1, "1h")
    df["spread_usd"] = h1["spread_usd"].reindex(df.index).to_numpy()
    df["spread_bar_usd"] = h1["spread_bar_usd"].reindex(df.index).to_numpy()
    df = df[df["d_sma200"].notna()].copy()
    cal = p2._load_news()
    df = p2.add_london_range(df)
    df = p2.add_donchian(df, daily)
    df = p2.add_news_flags(df, cal)
    return df


def run_all(df: pd.DataFrame, tag: str, bar_spread: bool) -> pd.DataFrame:
    BrokerEngine.use_bar_spread = bar_spread
    out = HERE / "results" / tag
    out.mkdir(parents=True, exist_ok=True)
    p2.RESULTS = out
    df_ad = df.copy()
    df_ad["nfp_blackout"] = df_ad["news_blackout"].astype(bool)
    rows, yrs = [], []
    jobs = [
        ("A_ny_lon_brk_d4h", "A_ny", lambda: p2.run_engine(df_ad, lambda r: p2.sig_ny_lon_break(r, "d4h"), nfp_filter=True, setup_name="A_ny_lon_brk_d4h")),
        ("B_fomc_cont", "B_news", lambda: p2.run_engine(df, lambda r: p2.sig_news(r, "FOMC", "cont"), nfp_filter=False, setup_name="B_fomc_cont")),
        ("C_donch20_long", "C_trend", lambda: p2.run_open_entry(df, lambda r: p2.sig_donchian_at_open(r, "long"), "C_donch20_long")),
    ]
    for params in rt.A_VARIANTS:
        if params["name"] in ("A_base", "A_4h_ma", "A_trend_ma"):
            jobs.append((params["name"], "A_asia", lambda p=params: rt.run_next_open(df, p)))
    for name, fam, job in jobs:
        C.SPREAD = 0.25
        print("running", tag, name, flush=True)
        trades, eq = job()
        p2._record(name, fam, trades, eq, rows, yrs)
    summ = pd.DataFrame(rows)
    summ.to_csv(out / "wf_summary.csv", index=False)
    if yrs:
        pd.concat(yrs, ignore_index=True).to_csv(out / "wf_oos_years.csv", index=False)
    C.SPREAD = 0.25
    return summ


def old_summary() -> pd.DataFrame:
    a = pd.read_csv(DEEP / "results" / "phase2" / "wf_summary.csv")
    b = pd.read_csv(DEEP / "results" / "wf_summary.csv")
    return pd.concat([a, b], ignore_index=True)


def _trades_path_old(name: str) -> Path | None:
    for p in (DEEP / "results" / "phase2" / f"trades_{name}.csv",
              DEEP / "results" / "trades" / f"trades_{name}.csv"):
        if p.exists():
            return p
    return None


def overlap(name: str, tag: str) -> dict:
    """Old (HistData) trades that have a broker trade with the same entry hour and side."""
    old_p = _trades_path_old(name)
    new_p = HERE / "results" / tag / f"trades_{name}.csv"
    if old_p is None or not new_p.exists():
        return {}
    o = pd.read_csv(old_p)
    n = pd.read_csv(new_p)
    lo, hi = pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2026-11-06", tz="UTC")

    def keys(d):
        t = pd.to_datetime(d["entry_time"], utc=True)
        d = d[(t >= lo) & (t < hi)]
        return set(zip(pd.to_datetime(d["entry_time"], utc=True).dt.floor("h"), d["direction"]))

    ko, kn = keys(o), keys(n)
    common = ko & kn
    return {"old_n": len(ko), "broker_n": len(kn), "same_trades": len(common),
            "share_of_old": round(len(common) / len(ko), 3) if ko else None}


def main() -> int:
    print("building broker frame ...", flush=True)
    df = build_frame()
    print("rows", len(df), df.index.min(), "->", df.index.max())
    print("spread used: median", round(float(df["spread_usd"].median()), 3), "mean", round(float(df["spread_usd"].mean()), 3))
    s_live = run_all(df, "broker_spread", True)
    s_fixed = run_all(df, "fixed_025", False)
    old = old_summary()
    cols = ["n", "win_rate", "avg_r", "profit_factor", "max_dd_pct"]
    recs = []
    for name in V3:
        rec = {"variant": name, "label": LABEL[name]}
        for tag, s in (("old", old), ("broker", s_live), ("broker_fixed025", s_fixed)):
            for sample in ("OOS_2012_2026", "OOS_2012_2023", "OOS_2024_2026"):
                r = s[(s["variant"] == name) & (s["sample"] == sample)]
                if r.empty:
                    continue
                r = r.iloc[0]
                short = {"OOS_2012_2026": "oos", "OOS_2012_2023": "mid", "OOS_2024_2026": "rec"}[sample]
                for c in cols:
                    rec[f"{tag}_{short}_{c}"] = r.get(c)
                if sample == "OOS_2012_2026":
                    for c in ("oos_years_positive", "oos_years", "adopt", "adopt_reason"):
                        if c in r.index:
                            rec[f"{tag}_{c}"] = r.get(c)
        rec.update({f"overlap_{k}": v for k, v in overlap(name, "broker_spread").items()})
        recs.append(rec)
    comp = pd.DataFrame(recs)
    comp.to_csv(HERE / "results" / "comparison.csv", index=False)
    meta = {"frame_rows": int(len(df)), "frame_start": str(df.index.min()), "frame_end": str(df.index.max()),
            "spread_used_median": float(df["spread_usd"].median()), "spread_used_mean": float(df["spread_usd"].mean()),
            "spread_by_year_median": {int(k): v for k, v in df.groupby(df.index.year)["spread_usd"].median().round(3).items()}}
    (HERE / "results" / "frame_meta.json").write_text(json.dumps(meta, indent=2, default=str) + "\n")
    pd.set_option("display.width", 250)
    print(comp.T.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

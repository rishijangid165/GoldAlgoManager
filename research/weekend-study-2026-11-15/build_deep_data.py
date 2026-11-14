#!/usr/bin/env python3
"""Decode the terminal's full XAUUSD M1 history (.hcc) and write M1/M5/M15/H1 CSVs to data/broker/.

Why: the running terminal still serves only 100,000 bars per timeframe through
copy_rates_range (its chart caches were built under the old Max-bars setting and are only
rebuilt on restart, which we must not do). The M1 base files on disk hold the full broker
history (2004-06 .. 2026-11). They are copied to /tmp and read there; nothing in the terminal
folder is written. Output timestamps: time_utc and time_et (server = ET+7).
Higher timeframes are resampled from M1 on the server clock, exactly as MT5 builds them;
spread for a resampled bar = median of its M1 spreads (spread_pts), and the bar minimum
(spread_min_pts) as MT5 reports it.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import hcc_reader  # noqa: E402

SRC = Path("/home/box/.wine-mt5/drive_c/MT5/Bases/MetaQuotes-Demo/history/XAUUSD")
TMP = Path("/tmp/hcc")
OUT = ROOT / "data" / "broker"
ET = "America/New_York"


def server_index_to_et(t_server: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return (t_server - pd.Timedelta(hours=7)).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")


def main() -> int:
    TMP.mkdir(exist_ok=True)
    for f in sorted(SRC.glob("*.hcc")):
        shutil.copy2(f, TMP / f.name)
    a = hcc_reader.load_m1(str(TMP))
    t = pd.to_datetime(a["t"], unit="s")
    m1 = pd.DataFrame({"open": a["o"], "high": a["h"], "low": a["l"], "close": a["c"],
                       "tick_volume": a["tv"], "spread_pts": a["sp"]}, index=t)
    m1.index.name = "server_time"
    manifest = {"source": "MetaQuotes-Demo XAUUSD M1 base files (.hcc), decoded read-only; higher TFs resampled from M1",
                "api_note": "copy_rates_range still returns at most 100,000 bars per timeframe on the running terminal",
                "files": {}}
    OUT.mkdir(parents=True, exist_ok=True)
    for tf, rule in (("M1", None), ("M5", "5min"), ("M15", "15min"), ("H1", "1h")):
        if rule is None:
            bars = m1.copy()
            bars["spread_min_pts"] = bars["spread_pts"]
        else:
            g = m1.resample(rule, label="left", closed="left")
            bars = g.agg({"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"})
            bars["spread_pts"] = g["spread_pts"].median()
            bars["spread_min_pts"] = g["spread_pts"].min()
            bars = bars.dropna(subset=["open"])
        et = server_index_to_et(pd.DatetimeIndex(bars.index))
        keep = ~pd.isna(et)
        bars = bars[keep]
        et = et[keep]
        out = pd.DataFrame({
            "time_utc": et.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S"),
            "time_et": et.strftime("%Y-%m-%d %H:%M:%S%z"),
            "open": bars["open"].round(2).to_numpy(), "high": bars["high"].round(2).to_numpy(),
            "low": bars["low"].round(2).to_numpy(), "close": bars["close"].round(2).to_numpy(),
            "tick_volume": bars["tick_volume"].astype("int64").to_numpy(),
            "spread_pts": bars["spread_pts"].round(1).to_numpy(),
            "spread_min_pts": bars["spread_min_pts"].to_numpy(),
        })
        path = OUT / (f"XAUUSD_{tf}_full.csv.gz" if tf in ("M1", "M5") else f"XAUUSD_{tf}_full.csv")
        out.to_csv(path, index=False)
        manifest["files"][tf] = {"file": str(path.relative_to(ROOT)), "rows": int(len(out)),
                                 "first_utc": out["time_utc"].iloc[0], "last_utc": out["time_utc"].iloc[-1]}
        print(tf, len(out), out["time_utc"].iloc[0], "->", out["time_utc"].iloc[-1], flush=True)
    (OUT / "manifest_full.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # validation vs the API H1 pull
    api = pd.read_csv(OUT / "XAUUSD_H1.csv")
    full = pd.read_csv(OUT / "XAUUSD_H1_full.csv")
    j = api.merge(full, on="time_utc", suffixes=("_api", "_full"))
    for c in ("open", "high", "low", "close"):
        d = (j[f"{c}_api"] - j[f"{c}_full"]).abs()
        print("H1 api vs decoded", c, "n", len(j), "exact share", round(float((d < 0.005).mean()), 4), "p99", float(d.quantile(0.99)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Broker (MetaQuotes-Demo MT5) XAUUSD history: import, time-zone fix, spread model.

Raw pulls come from C:\\winpy\\broker_history_ro.py / broker_history_chunks_ro.py
(read-only MetaTrader5 copy_rates_range; no trading calls). MT5 bar times are
broker *server* wall-clock. MetaQuotes-Demo runs on ET+7 all year (EET/EEST
with US DST dates), verified by matching H1 closes to HistData (ET): offset 7h
gives a median |diff| of $0.03 in 2019 and ~$0.2 in 2025–26 for every month
tested, 6h/8h give $0.7–7.

Saved CSVs (data/broker/, git-ignored): time_utc, time_et, OHLC, tick_volume,
spread_pts, spread_usd. `spread` in an MT5 bar is the *minimum* spread seen in
that bar, so on H1 it understates the cost; the retest uses
max(bar spread, 2026 M1 median spread for that ET hour) — see `spread_model`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_SRC = Path("/home/box/.wine-mt5/drive_c/winpy/broker")
OUT = ROOT / "data" / "broker"
ET = "America/New_York"
SERVER_MINUS_ET_HOURS = 7
POINT = 0.01

SOURCES = {
    "M1": "XAUUSD_M1_chunked.csv",
    "M15": "XAUUSD_M15_chunked.csv",
    "H1": "XAUUSD_H1_chunked.csv",
    "H4": "XAUUSD_H4.csv",
    "D1": "XAUUSD_D1.csv",
}


def server_to_et(epoch_server: pd.Series) -> pd.DatetimeIndex:
    naive = pd.to_datetime(epoch_server, unit="s") - pd.Timedelta(hours=SERVER_MINUS_ET_HOURS)
    return pd.DatetimeIndex(naive).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")


def import_raw() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"source": "MetaQuotes-Demo MT5, XAUUSD, MetaTrader5.copy_rates_range (read-only)",
                "server_tz": "ET+7 (EET/EEST on US DST dates)", "terminal_maxbars": 100000, "files": {}}
    for tf, fn in SOURCES.items():
        p = RAW_SRC / fn
        if not p.exists():
            continue
        raw = pd.read_csv(p)
        if tf == "D1":
            # D1 bars open at 00:00 server = 17:00 ET of the prior day -> label by session date.
            et = server_to_et(raw["time"])
        else:
            et = server_to_et(raw["time"])
        df = pd.DataFrame({
            "time_utc": et.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S"),
            "time_et": et.strftime("%Y-%m-%d %H:%M:%S%z"),
            "open": raw["open"], "high": raw["high"], "low": raw["low"], "close": raw["close"],
            "tick_volume": raw["tick_volume"], "spread_pts": raw["spread"],
            "spread_usd": (raw["spread"] * POINT).round(2),
        })
        df = df[pd.notna(et)]
        df.to_csv(OUT / f"XAUUSD_{tf}.csv", index=False)
        manifest["files"][tf] = {"file": f"data/broker/XAUUSD_{tf}.csv", "rows": int(len(df)),
                                 "first_utc": df["time_utc"].iloc[0], "last_utc": df["time_utc"].iloc[-1],
                                 "median_spread_usd": float(df["spread_usd"].median())}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def load_tf(tf: str) -> pd.DataFrame:
    """OHLC frame indexed by ET bar-open time, engine column names."""
    df = pd.read_csv(OUT / f"XAUUSD_{tf}.csv")
    idx = pd.to_datetime(df["time_utc"], utc=True).dt.tz_convert(ET)
    out = pd.DataFrame({
        "Open": df["open"].to_numpy(), "High": df["high"].to_numpy(), "Low": df["low"].to_numpy(),
        "Close": df["close"].to_numpy(), "Volume": df["tick_volume"].to_numpy(),
        "spread_bar_usd": df["spread_usd"].to_numpy(),
    }, index=pd.DatetimeIndex(idx, name="Datetime"))
    return out[~out.index.duplicated()].sort_index()


def spread_profile() -> pd.Series:
    """Median M1 spread ($) per ET hour, from the M1 sample (Jul–Nov 2026)."""
    m1 = load_tf("M1")
    return m1.groupby(m1.index.hour)["spread_bar_usd"].median()


def spread_model(h1: pd.DataFrame) -> pd.Series:
    prof = spread_profile()
    hour_typ = pd.Series(h1.index.hour, index=h1.index).map(prof).fillna(prof.median())
    return pd.concat([h1["spread_bar_usd"], hour_typ], axis=1).max(axis=1)


if __name__ == "__main__":
    print(json.dumps(import_raw(), indent=2))
    print(spread_profile().round(2).to_dict())

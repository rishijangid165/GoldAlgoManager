"""Data layer for the weekend study: decoded broker M1 + research feature frames.

All prices are broker BID (MT5 bars are bid). Spread model (pre-registered):
max(recorded M1 spread, 2026 M1 median spread for that ET hour).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from research.backtest import config as C  # noqa: E402,F401

DEEP = ROOT / "research" / "deep-study-2026-11-14"
BROKER = ROOT / "data" / "broker"
CACHE = Path("/tmp/wk_cache")
CACHE.mkdir(exist_ok=True)
ET = "America/New_York"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ds = _load("deep_dataset", DEEP / "dataset.py")
p2 = _load("phase2_setups", DEEP / "phase2_setups.py")
rt = _load("retest_setups", DEEP / "retest_setups.py")


def _read(tf: str) -> pd.DataFrame:
    p = BROKER / (f"XAUUSD_{tf}_full.csv.gz" if tf in ("M1", "M5") else f"XAUUSD_{tf}_full.csv")
    return pd.read_csv(p, usecols=["time_utc", "open", "high", "low", "close", "tick_volume", "spread_pts"])


def m1_arrays() -> dict:
    f = CACHE / "m1.npz"
    if f.exists():
        z = np.load(f)
        return {k: z[k] for k in z.files}
    df = _read("M1")
    t = pd.to_datetime(df["time_utc"], utc=True)
    et = t.dt.tz_convert(ET)
    out = {
        "t": t.dt.as_unit("ns").astype("int64").to_numpy(),
        "o": df["open"].to_numpy(float), "h": df["high"].to_numpy(float),
        "l": df["low"].to_numpy(float), "c": df["close"].to_numpy(float),
        "spr_rec": df["spread_pts"].to_numpy(float) / 100.0,
        "et_hour": et.dt.hour.to_numpy(np.int8), "et_min": et.dt.minute.to_numpy(np.int8),
        "et_wd": et.dt.weekday.to_numpy(np.int8), "et_year": et.dt.year.to_numpy(np.int16),
    }
    np.savez(f, **out)
    return out


def spread_profile(m: dict) -> np.ndarray:
    # Same window as the 2026-11-14 retest profile: the last 100k M1 bars (Jul-Nov 2026),
    # which is what the live API returns. Older stored spreads look compressed (Jan-Jun 2026
    # median 4 pts vs 17 pts live), so the live-window profile is the realistic floor.
    sel = np.zeros(len(m["t"]), dtype=bool)
    sel[-100_000:] = True
    prof = np.zeros(24)
    for hr in range(24):
        v = m["spr_rec"][sel & (m["et_hour"] == hr)]
        prof[hr] = np.median(v) if len(v) else np.nan
    prof[np.isnan(prof)] = np.nanmedian(prof)
    return prof


def m1_with_spread() -> dict:
    m = m1_arrays()
    prof = spread_profile(m)
    m["spr"] = np.maximum(m["spr_rec"], prof[m["et_hour"]])
    m["profile"] = prof
    return m


def load_ohlc(tf: str) -> pd.DataFrame:
    df = _read(tf)
    idx = pd.to_datetime(df["time_utc"], utc=True).dt.tz_convert(ET)
    out = pd.DataFrame({"Open": df["open"].to_numpy(), "High": df["high"].to_numpy(),
                        "Low": df["low"].to_numpy(), "Close": df["close"].to_numpy(),
                        "Volume": df["tick_volume"].to_numpy(),
                        "spread_bar_usd": df["spread_pts"].to_numpy() / 100.0},
                       index=pd.DatetimeIndex(idx, name="Datetime"))
    return out[~out.index.duplicated()].sort_index()


def build_frames(profile: np.ndarray) -> dict:
    f = CACHE / "frames.pkl"
    if f.exists():
        return pd.read_pickle(f)
    h1 = load_ohlc("H1")
    m15 = load_ohlc("M15")
    daily = ds.session_daily(h1[["Open", "High", "Low", "Close", "Volume"]])
    cal = p2._load_news()
    frames = {"daily": daily}
    for tf, ex in (("1h", h1), ("15m", m15)):
        df = ds.build_exec_from_series(daily, h1, ex, tf)
        hr = pd.DatetimeIndex(df.index).hour
        df["spread_usd"] = np.maximum(ex["spread_bar_usd"].reindex(df.index).to_numpy(), profile[hr])
        df = df[df["d_sma200"].notna()].copy()
        df = p2.add_london_range(df)
        df = p2.add_donchian(df, daily)
        df = p2.add_news_flags(df, cal)
        frames[tf] = df
    pd.to_pickle(frames, f)
    return frames

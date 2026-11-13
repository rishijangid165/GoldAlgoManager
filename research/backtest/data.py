"""Load raw GC=F series, resample 4H, and tag COMEX sessions.

All timestamps are converted to America/New_York so session hours stay
stable across DST. Daily bars are dated by the COMEX session end date
(Yahoo convention). The in-progress last daily bar is dropped.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config as C

OHLC = ["Open", "High", "Low", "Close"]


def _fix_offset(series: pd.Series) -> pd.Series:
    # yfinance CSVs write "-0400" without a colon; pandas wants "-04:00".
    return series.astype(str).str.replace(r"([+-]\d{2})(\d{2})$", r"\1:\2", regex=True)


def _clean_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in OHLC:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if "Volume" in out.columns:
        out["Volume"] = pd.to_numeric(out["Volume"], errors="coerce").fillna(0)
    out = out.dropna(subset=OHLC)
    out = out[out["High"] >= out["Low"]]
    out = out[out["Close"] > 0]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def load_intraday(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    ts = pd.to_datetime(_fix_offset(raw["Datetime"]), utc=True)
    df = raw.set_index(ts).drop(columns=["Datetime"])
    df.index = df.index.tz_convert(C.TZ)
    df.index.name = "Datetime"
    return _clean_ohlc(df)


def load_daily(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    ts = pd.to_datetime(raw["Date"]).dt.tz_localize(C.TZ)
    df = raw.set_index(ts).drop(columns=["Date"])
    df.index.name = "Date"
    df = _clean_ohlc(df)
    # Last daily bar is the in-progress COMEX session more often than not.
    # Always drop it; a completed prior session is never dropped this way.
    if len(df) >= 2:
        df = df.iloc[:-1]
    return df


def load_gold_raw() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = load_daily(C.RAW_DIR / "GC=F_daily.csv")
    h1 = load_intraday(C.RAW_DIR / "GC=F_1h.csv")
    m15 = load_intraday(C.RAW_DIR / "GC=F_15m.csv")
    return daily, h1, m15


def resample_4h(h1: pd.DataFrame) -> pd.DataFrame:
    """4H bars aligned to the COMEX session: 18:00, 22:00, 02:00, 06:00, 10:00, 14:00 ET.

    offset='2h' shifts midnight-aligned 4H bins so they start at 18:00 ET.
    The 14:00 bar only covers 14:00–17:00 ET (the daily close); that is intended.
    """
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in h1.columns:
        agg["Volume"] = "sum"
    h4 = h1.resample("4h", offset="2h", label="left", closed="left").agg(agg)
    h4 = h4.dropna(subset=OHLC)
    h4.index.name = "Datetime"
    return h4


def session_date(index: pd.DatetimeIndex) -> pd.Series:
    """COMEX session date: 18:00 ET onward belongs to the next calendar date."""
    idx = pd.DatetimeIndex(index)
    nxt = (idx + pd.Timedelta(days=1)).date
    same = idx.date
    return pd.Series(
        [n if h >= C.ASIA_START_HOUR else s for h, n, s in zip(idx.hour, nxt, same)],
        index=index,
        name="session_date",
    )


def session_name(index: pd.DatetimeIndex) -> pd.Series:
    hours = pd.DatetimeIndex(index).hour
    names = []
    for h in hours:
        if h >= C.ASIA_START_HOUR or h < C.ASIA_END_HOUR:
            names.append("asia")
        elif h < C.LONDON_END_HOUR:
            names.append("london")
        elif h < C.NY_END_HOUR:
            names.append("ny")
        else:
            names.append("break")
    return pd.Series(names, index=index, name="session")


def bar_delta(tf: str) -> pd.Timedelta:
    return {"1h": pd.Timedelta(hours=1), "15m": pd.Timedelta(minutes=15), "4h": pd.Timedelta(hours=4)}[tf]


def load_exec(tf: str) -> pd.DataFrame:
    daily, h1, m15 = load_gold_raw()
    if tf == "1h":
        exec_df = h1.copy()
    elif tf == "15m":
        exec_df = m15.copy()
    else:
        raise ValueError(f"unsupported exec tf: {tf}")
    return daily, h1, resample_4h(h1), exec_df

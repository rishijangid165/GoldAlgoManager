#!/usr/bin/env python3
"""Load HistData XAUUSD and Yahoo GC=F, resample, and build no-lookahead features.

HistData M1 timestamps are treated as America/New_York wall clocks (the daily
break sits at 17:00-18:00 ET in both winter and summer). Session daily bars
use the same COMEX session date as research.backtest.data (18:00 ET onward
belongs to the next date).
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from research.backtest import config as C
from research.backtest.data import resample_4h, session_date, session_name
from research.backtest.features import build_exec_frame as _unused_build  # noqa: F401
from research.backtest.features import (
    add_asia_break_flags,
    add_bar_shape,
    add_base_indicators,
    add_session_levels,
    add_swing_pairs,
    atr,
    rsi,
    _map_closed,
    _raw_swing_stamps,
)
from research.backtest.data import bar_delta

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
HD_ZIPS = RAW / "histdata" / "zips"
PROC = ROOT / "data" / "processed"
STUDY = Path(__file__).resolve().parent
OHLC = ["Open", "High", "Low", "Close"]


def localize_et(naive: pd.DatetimeIndex) -> pd.DatetimeIndex:
    naive = pd.DatetimeIndex(naive)
    try:
        return naive.tz_localize("America/New_York", ambiguous="infer", nonexistent="shift_forward")
    except (ValueError, pytz_error()):
        loc = naive.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
        # Drop the rare DST-fallback ambiguous bar rather than guess wrong.
        return loc


def pytz_error():
    return Exception


def _read_histdata_csv(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(
        io.BytesIO(raw),
        sep=";",
        header=None,
        names=["dt", "Open", "High", "Low", "Close", "Volume"],
        dtype={"Volume": "float64"},
    )
    dt = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S", errors="coerce")
    df = df.loc[dt.notna()].copy()
    df.index = localize_et(pd.DatetimeIndex(dt[dt.notna()]))
    df = df.drop(columns=["dt"])
    for col in OHLC + ["Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=OHLC)
    df = df[df["High"] >= df["Low"]]
    df = df[df["Close"] > 0]
    df = df[~df.index.isna()]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index.name = "Datetime"
    return df


def load_histdata_m1() -> pd.DataFrame:
    zips = sorted(HD_ZIPS.glob("HISTDATA_COM_ASCII_XAUUSD_M1_*.zip"))
    if not zips:
        raise FileNotFoundError(f"no HistData zips in {HD_ZIPS}")
    frames = []
    used = []
    for path in zips:
        with zipfile.ZipFile(path) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                continue
            # Prefer the data CSV, skip status files (already filtered by .csv).
            raw = zf.read(csv_names[0])
        part = _read_histdata_csv(raw)
        frames.append(part)
        used.append((path.name, len(part), str(part.index.min()), str(part.index.max())))
    if not frames:
        raise RuntimeError("no HistData CSVs parsed")
    m1 = pd.concat(frames, axis=0).sort_index()
    m1 = m1[~m1.index.duplicated(keep="last")]
    # If both an annual 2026 zip and monthly 2026 zips exist, last-wins is fine.
    m1.attrs["sources"] = used
    return m1


def resample_ohlc(m1: pd.DataFrame, rule: str, offset: str | None = None) -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    # label/closed left so the stamp is the bar open, matching Yahoo GC=F.
    kw = dict(label="left", closed="left")
    if offset:
        bars = m1.resample(rule, offset=offset, **kw).agg(agg)
    else:
        bars = m1.resample(rule, **kw).agg(agg)
    bars = bars.dropna(subset=OHLC)
    bars.index.name = "Datetime"
    return bars


def session_daily(h1: pd.DataFrame) -> pd.DataFrame:
    """One row per COMEX session date, tz-aware at midnight ET of that date."""
    tmp = h1.copy()
    tmp["session_date"] = session_date(tmp.index)
    daily = tmp.groupby("session_date", sort=True).agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Volume=("Volume", "sum"),
    )
    # Midnight ET on the session date (the date used by Yahoo GC=F daily).
    idx = pd.to_datetime(daily.index).tz_localize(C.TZ)
    daily.index = idx
    daily.index.name = "Date"
    return daily


def save_bars(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if out.index.name is None:
        out.index.name = "Datetime"
    # gzip keeps 15m/5m committable.
    if path.suffixes[-2:] != [".csv", ".gz"]:
        # allow .csv.gz or .csv
        pass
    out.to_csv(path, date_format="%Y-%m-%d %H:%M:%S%z")


def load_yahoo_daily() -> pd.DataFrame:
    from research.backtest.data import load_daily

    return load_daily(RAW / "GC=F_daily.csv")


def load_yahoo_intraday(name: str) -> pd.DataFrame:
    from research.backtest.data import load_intraday

    return load_intraday(RAW / name)


def write_resampled(m1: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    if m1 is None:
        m1 = load_histdata_m1()
    h1 = resample_ohlc(m1, "1h")
    m15 = resample_ohlc(m1, "15min")
    m5 = resample_ohlc(m1, "5min")
    daily = session_daily(h1)
    out = {
        "XAUUSD_m1": m1,
        "XAUUSD_5m": m5,
        "XAUUSD_15m": m15,
        "XAUUSD_1h": h1,
        "XAUUSD_daily": daily,
    }
    # Do not write M1 (too large). Write 5m/15m/1h/daily gzip.
    for key, filename in [
        ("XAUUSD_5m", "XAUUSD_5m.csv.gz"),
        ("XAUUSD_15m", "XAUUSD_15m.csv.gz"),
        ("XAUUSD_1h", "XAUUSD_1h.csv.gz"),
        ("XAUUSD_daily", "XAUUSD_daily.csv.gz"),
    ]:
        save_bars(out[key], RAW / "histdata" / filename)
    meta = []
    for k, df in out.items():
        if k == "XAUUSD_m1":
            continue
        meta.append({"name": k, "rows": int(len(df)), "start": str(df.index.min()), "end": str(df.index.max())})
    print("resampled:", meta)
    return out


def load_resampled() -> dict[str, pd.DataFrame]:
    def _load(path: Path, index_name: str) -> pd.DataFrame:
        raw = pd.read_csv(path)
        col = raw.columns[0]
        ts = pd.to_datetime(raw[col].astype(str).str.replace(r"([+-]\d{2})(\d{2})$", r"\1:\2", regex=True), utc=True)
        df = raw.set_index(ts).drop(columns=[col])
        df.index = df.index.tz_convert(C.TZ)
        df.index.name = index_name
        for c in OHLC:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        if "Volume" in df.columns:
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
        return df.dropna(subset=OHLC).sort_index()

    paths = {
        "XAUUSD_5m": RAW / "histdata" / "XAUUSD_5m.csv.gz",
        "XAUUSD_15m": RAW / "histdata" / "XAUUSD_15m.csv.gz",
        "XAUUSD_1h": RAW / "histdata" / "XAUUSD_1h.csv.gz",
        "XAUUSD_daily": RAW / "histdata" / "XAUUSD_daily.csv.gz",
    }
    if not all(p.exists() for p in paths.values()):
        return write_resampled()
    out = {k: _load(p, "Date" if "daily" in k else "Datetime") for k, p in paths.items()}
    return out


def build_exec_from_series(daily: pd.DataFrame, h1: pd.DataFrame, exec_df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Same no-lookahead feature build as features.build_exec_frame, any source."""
    h4 = resample_4h(h1)
    d = add_base_indicators(daily, "d_", C.SWING_N_D)
    d["d_trend_down_ma"] = d["d_below_mas"]
    d["d_trend_up_ma"] = d["d_above_mas"]
    d["d_trend_down_strict"] = d["d_below_mas"] & d["d_lower_highs"]
    d["d_trend_up_strict"] = d["d_above_mas"] & d["d_higher_lows"]

    h4i = add_base_indicators(h4, "h4_", C.SWING_N_4H)
    h4i["h4_trend_down_ma"] = h4i["h4_below_sma50"]
    h4i["h4_trend_up_ma"] = h4i["h4_above_sma50"]
    h4i["h4_trend_down_strict"] = h4i["h4_below_sma50"] & h4i["h4_lower_highs"]
    h4i["h4_trend_up_strict"] = h4i["h4_above_sma50"] & h4i["h4_higher_lows"]

    h1i = add_base_indicators(h1, "h1_", C.SWING_N_1H)

    daily_cols = [
        "d_close", "d_sma50", "d_sma200", "d_atr", "d_rsi",
        "d_swing_high", "d_prev_swing_high", "d_swing_low", "d_prev_swing_low",
        "d_lower_highs", "d_higher_lows",
        "d_trend_down_ma", "d_trend_up_ma", "d_trend_down_strict", "d_trend_up_strict",
        "d_below_mas", "d_above_mas",
    ]
    h4_cols = [
        "h4_close", "h4_sma50", "h4_sma200", "h4_atr", "h4_rsi",
        "h4_swing_high", "h4_prev_swing_high", "h4_swing_low", "h4_prev_swing_low",
        "h4_lower_highs", "h4_higher_lows",
        "h4_trend_down_ma", "h4_trend_up_ma", "h4_trend_down_strict", "h4_trend_up_strict",
        "h4_below_sma50", "h4_above_sma50",
    ]
    h1_cols = [
        "h1_close", "h1_sma50", "h1_sma200", "h1_atr", "h1_rsi",
        "h1_swing_high", "h1_prev_swing_high", "h1_swing_low", "h1_prev_swing_low",
        "h1_lower_highs", "h1_higher_lows",
    ]

    daily_avail = d[daily_cols].copy()
    daily_avail.index = daily_avail.index + pd.Timedelta(hours=17)
    close_idx = exec_df.index + bar_delta(tf)
    mapped_d = _map_closed(close_idx, daily_avail, duration=pd.Timedelta(0), cols=daily_cols)
    mapped_d.index = exec_df.index
    mapped_h4 = _map_closed(close_idx, h4i, duration=bar_delta("4h"), cols=h4_cols)
    mapped_h4.index = exec_df.index
    mapped_h1 = _map_closed(close_idx, h1i, duration=bar_delta("1h"), cols=h1_cols)
    mapped_h1.index = exec_df.index

    out = exec_df[OHLC + (["Volume"] if "Volume" in exec_df.columns else [])].copy()
    out = add_session_levels(out)
    out = add_bar_shape(out)
    out["atr"] = atr(out)
    out["rsi"] = rsi(out["Close"])
    raw_sh, raw_sl = _raw_swing_stamps(out["High"], out["Low"], C.SWING_N_1H if tf == "1h" else 4)
    out = add_swing_pairs(out, raw_sh, raw_sl, "")

    for mapped in (mapped_d, mapped_h4, mapped_h1):
        for col in mapped.columns:
            out[col] = mapped[col].to_numpy()

    if tf == "1h":
        out["h1_atr"] = out["atr"]
        out["h1_rsi"] = out["rsi"]
        out["h1_close"] = out["Close"]

    out["atr_sl"] = out["h1_atr"].fillna(out["atr"])
    out["trend_down_ma"] = (out["d_trend_down_ma"] == True) & (out["h4_trend_down_ma"] == True)
    out["trend_up_ma"] = (out["d_trend_up_ma"] == True) & (out["h4_trend_up_ma"] == True)
    out["trend_down_strict"] = (out["d_trend_down_strict"] == True) & (out["h4_trend_down_strict"] == True)
    out["trend_up_strict"] = (out["d_trend_up_strict"] == True) & (out["h4_trend_up_strict"] == True)
    out = add_asia_break_flags(out)
    out["tf"] = tf
    return out


def build_xauusd_exec(tf: str = "1h") -> pd.DataFrame:
    bars = load_resampled()
    daily = bars["XAUUSD_daily"]
    h1 = bars["XAUUSD_1h"]
    if tf == "1h":
        exec_df = h1
    elif tf == "15m":
        exec_df = bars["XAUUSD_15m"]
    else:
        raise ValueError(tf)
    return build_exec_from_series(daily, h1, exec_df, tf)


if __name__ == "__main__":
    m1 = load_histdata_m1()
    print("M1", len(m1), m1.index.min(), m1.index.max())
    write_resampled(m1)

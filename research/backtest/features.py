"""Indicators, confirmed swings, and no-lookahead higher-timeframe mapping."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .data import bar_delta, load_exec, session_date, session_name

OHLC = ["Open", "High", "Low", "Close"]


def rma(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(alpha=1.0 / n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = C.ATR_N) -> pd.Series:
    prev = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev).abs(),
            (df["Low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return rma(tr, n).rename("atr")


def rsi(close: pd.Series, n: int = C.RSI_N) -> pd.Series:
    delta = close.diff()
    up = rma(delta.clip(lower=0), n)
    down = rma((-delta).clip(lower=0), n)
    rs = up / down.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).rename("rsi")


def add_swing_pairs(df: pd.DataFrame, raw_high: pd.Series, raw_low: pd.Series, prefix: str) -> pd.DataFrame:
    last_h = np.full(len(df), np.nan)
    prev_h = np.full(len(df), np.nan)
    last_l = np.full(len(df), np.nan)
    prev_l = np.full(len(df), np.nan)
    lh, ph, ll, pl = np.nan, np.nan, np.nan, np.nan
    raw_h = raw_high.to_numpy()
    raw_l = raw_low.to_numpy()
    for i in range(len(df)):
        if np.isfinite(raw_h[i]) and (not np.isfinite(lh) or raw_h[i] != lh):
            ph, lh = lh, raw_h[i]
        if np.isfinite(raw_l[i]) and (not np.isfinite(ll) or raw_l[i] != ll):
            pl, ll = ll, raw_l[i]
        last_h[i], prev_h[i], last_l[i], prev_l[i] = lh, ph, ll, pl
    df[f"{prefix}swing_high"] = last_h
    df[f"{prefix}prev_swing_high"] = prev_h
    df[f"{prefix}swing_low"] = last_l
    df[f"{prefix}prev_swing_low"] = prev_l
    df[f"{prefix}lower_highs"] = last_h < prev_h
    df[f"{prefix}higher_lows"] = last_l > prev_l
    return df


def add_base_indicators(df: pd.DataFrame, prefix: str, swing_n: int) -> pd.DataFrame:
    out = df.copy()
    out[f"{prefix}sma50"] = out["Close"].rolling(C.SMA_FAST, min_periods=C.SMA_FAST).mean()
    out[f"{prefix}sma200"] = out["Close"].rolling(C.SMA_SLOW, min_periods=C.SMA_SLOW).mean()
    out[f"{prefix}atr"] = atr(out)
    out[f"{prefix}rsi"] = rsi(out["Close"])
    raw_sh, raw_sl = _raw_swing_stamps(out["High"], out["Low"], swing_n)
    out = add_swing_pairs(out, raw_sh, raw_sl, prefix)
    close = out["Close"]
    out[f"{prefix}below_mas"] = (close < out[f"{prefix}sma50"]) & (close < out[f"{prefix}sma200"])
    # 4H SMA200 needs ~33 days; also allow a 50-only flag for early 4H bars.
    out[f"{prefix}above_mas"] = (close > out[f"{prefix}sma50"]) & (close > out[f"{prefix}sma200"])
    out[f"{prefix}below_sma50"] = close < out[f"{prefix}sma50"]
    out[f"{prefix}above_sma50"] = close > out[f"{prefix}sma50"]
    out[f"{prefix}close"] = close
    return out


def _raw_swing_stamps(high: pd.Series, low: pd.Series, n: int) -> tuple[pd.Series, pd.Series]:
    h = high.to_numpy(dtype=float)
    l = low.to_numpy(dtype=float)
    sh_vals = np.full(len(h), np.nan)
    sl_vals = np.full(len(l), np.nan)
    for i in range(n, len(h) - n):
        if h[i] >= np.nanmax(h[i - n : i + n + 1]):
            sh_vals[i + n] = h[i]
        if l[i] <= np.nanmin(l[i - n : i + n + 1]):
            sl_vals[i + n] = l[i]
    return pd.Series(sh_vals, index=high.index), pd.Series(sl_vals, index=low.index)


def _map_closed(exec_index: pd.DatetimeIndex, higher: pd.DataFrame, duration: pd.Timedelta, cols: list[str]) -> pd.DataFrame:
    """Map a higher-TF row onto exec bars only after that higher bar has closed."""
    src = higher[cols].copy()
    avail = pd.DatetimeIndex(src.index) + duration
    avail = avail.tz_convert(str(pd.DatetimeIndex(exec_index).tz))
    # pandas 3 can mix datetime64[us] and [ns]; merge_asof requires an exact dtype match.
    avail = avail.as_unit("ns")
    src["_available"] = avail
    src = src.sort_values("_available")
    right = src.reset_index(drop=True)
    left_idx = pd.DatetimeIndex(exec_index).tz_convert(str(avail.tz)).as_unit("ns")
    left = pd.DataFrame({"_available": left_idx}, index=exec_index)
    mapped = pd.merge_asof(
        left.sort_values("_available"),
        right,
        on="_available",
        direction="backward",
    )
    mapped.index = exec_index
    return mapped[cols]


def add_session_levels(exec_df: pd.DataFrame) -> pd.DataFrame:
    out = exec_df.copy()
    out["session_date"] = session_date(out.index)
    out["session"] = session_name(out.index)
    hours = pd.DatetimeIndex(out.index).hour

    sess = (
        out.groupby("session_date", sort=True)
        .agg(sess_high=("High", "max"), sess_low=("Low", "min"))
    )
    sess["prior_high"] = sess["sess_high"].shift(1)
    sess["prior_low"] = sess["sess_low"].shift(1)
    out = out.join(sess[["prior_high", "prior_low"]], on="session_date")

    asia_mask = (hours >= C.ASIA_START_HOUR) | (hours < C.ASIA_END_HOUR)
    asia = (
        out.loc[asia_mask]
        .groupby("session_date", sort=True)
        .agg(asia_high=("High", "max"), asia_low=("Low", "min"))
    )
    # Asia range is only knowable once the 02:00–03:00 ET bar has closed,
    # i.e. from 03:00 ET onward. Do not attach it to Asia bars (look-ahead).
    out = out.join(asia, on="session_date")
    after_asia = (hours >= C.ASIA_END_HOUR) & (hours < C.ASIA_START_HOUR)
    out.loc[~after_asia, ["asia_high", "asia_low"]] = np.nan

    # First Friday NFP window approximation (08:00–10:30 ET).
    dow = pd.DatetimeIndex(out.index).day_of_week
    day = pd.DatetimeIndex(out.index).day
    nfp_day = (dow == 4) & (day <= 7)
    minutes = hours * 60 + pd.DatetimeIndex(out.index).minute
    nfp_window = (minutes >= 8 * 60) & (minutes < int(10.5 * 60))
    out["nfp_blackout"] = nfp_day & nfp_window
    return out


def add_bar_shape(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rng = (out["High"] - out["Low"]).replace(0, np.nan)
    out["bar_range"] = out["High"] - out["Low"]
    out["close_loc"] = (out["Close"] - out["Low"]) / rng  # 0 = at low, 1 = at high
    out["upper_wick"] = out["High"] - out[["Open", "Close"]].max(axis=1)
    out["lower_wick"] = out[["Open", "Close"]].min(axis=1) - out["Low"]
    out["upper_wick_frac"] = out["upper_wick"] / rng
    out["lower_wick_frac"] = out["lower_wick"] / rng
    out["bullish"] = out["Close"] > out["Open"]
    out["bearish"] = out["Close"] < out["Open"]
    return out


def build_exec_frame(tf: str = "1h") -> pd.DataFrame:
    daily, h1, h4, exec_df = load_exec(tf)

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

    # Daily is available from 17:00 ET on its session date.
    daily_avail = d[daily_cols].copy()
    daily_avail.index = daily_avail.index + pd.Timedelta(hours=17)
    # Map as of the exec bar's CLOSE so a signal at close can use just-completed
    # higher-TF bars. That is also what is known at the next bar's open (entry).
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

    # When exec is 1h, the current bar's own 1h indicators at *close* should
    # include this bar (mapping uses close time = open+1h, which equals the
    # next bar's open). Signals are evaluated at close; we rebuild 1h RSI/ATR
    # from the exec series so the signal bar is included, then use mapped
    # swings (which require confirmation) from the mapper.
    if tf == "1h":
        out["h1_atr"] = out["atr"]
        out["h1_rsi"] = out["rsi"]
        out["h1_close"] = out["Close"]

    # Structure-based SL buffer always uses 1h ATR when available, else exec ATR.
    out["atr_sl"] = out["h1_atr"].fillna(out["atr"])

    out["trend_down_ma"] = (out["d_trend_down_ma"] == True) & (out["h4_trend_down_ma"] == True)
    out["trend_up_ma"] = (out["d_trend_up_ma"] == True) & (out["h4_trend_up_ma"] == True)
    out["trend_down_strict"] = (out["d_trend_down_strict"] == True) & (out["h4_trend_down_strict"] == True)
    out["trend_up_strict"] = (out["d_trend_up_strict"] == True) & (out["h4_trend_up_strict"] == True)

    out = add_asia_break_flags(out)
    out["tf"] = tf
    return out


def add_asia_break_flags(df: pd.DataFrame) -> pd.DataFrame:
    """First post-Asia close beyond the completed Asia range, per session.

    Computed left-to-right so later bars in the session are marked False
    once the range has already been closed through.
    """
    first_up = np.zeros(len(df), dtype=bool)
    first_dn = np.zeros(len(df), dtype=bool)
    last_sess = None
    seen_up = False
    seen_dn = False
    closes = df["Close"].to_numpy()
    ahi = df["asia_high"].to_numpy() if "asia_high" in df.columns else np.full(len(df), np.nan)
    alo = df["asia_low"].to_numpy() if "asia_low" in df.columns else np.full(len(df), np.nan)
    sess = df["session_date"].to_numpy()
    for i in range(len(df)):
        if sess[i] != last_sess:
            seen_up = seen_dn = False
            last_sess = sess[i]
        if np.isfinite(ahi[i]) and closes[i] > ahi[i]:
            if not seen_up:
                first_up[i] = True
            seen_up = True
        if np.isfinite(alo[i]) and closes[i] < alo[i]:
            if not seen_dn:
                first_dn[i] = True
            seen_dn = True
    out = df.copy()
    out["asia_first_close_up"] = first_up
    out["asia_first_close_down"] = first_dn
    return out

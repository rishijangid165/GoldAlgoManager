#!/usr/bin/env python3
"""Phase 2 — pre-registered search for setups that hold on 2009–2026 spot.

This list was fixed before looking at P&L. Twelve variants, no post-hoc adds.

Walk-forward: 2009-12 to 2011 is warmup / IS only; OOS years are 2012–2026.
Costs, risk, and 1.5R/3R scale match research.backtest (spread $0.25, slippage
$0.10, 0.5% risk, one trade, 2% daily loss stop).

Adoption bar (also fixed in advance, including the Phase-1 lesson that a
2024–2026-only edge is not enough):
  * OOS 2012–2026: n >= 40, avg R > 0, PF >= 1.20
  * Stability: at least 8 of 15 OOS years with avg R > 0
  * Regime check: 2012–2023 also avg R >= 0 and PF >= 1.0
Fail any one of these and the idea is watchlist only, not a playbook rule.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from research.backtest import config as C
from research.backtest.engine import Engine, Signal, exit_fill, run_engine
from research.backtest.metrics import summarize, trades_frame
from research.backtest.setups import _atr, _finite, _next_level, _rejection

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
RESULTS = STUDY / "results" / "phase2"
FIGS = STUDY / "figures"
OOS_START = pd.Timestamp("2012-01-01", tz="America/New_York")
CUT_2024 = pd.Timestamp("2024-01-01", tz="America/New_York")
ET = "America/New_York"

# ---------------------------------------------------------------------------
# Pre-registered variants (12). Do not append after seeing results.
# ---------------------------------------------------------------------------
# Family A — NY morning (08:00–12:00 ET, covering IST 18:00–21:00 ± DST)
#   with a daily/4H trend filter.
# Family B — post-news, after the first 60 minutes of NFP or FOMC.
# Family C — low-frequency daily Donchian trend following.
# Family D — previous-day high/low sweep-and-reclaim, regime-conditioned.
N_PRE_REGISTERED = 12

# ---------------------------------------------------------------------------
# Feature helpers
# ---------------------------------------------------------------------------

def _load_retest():
    spec = importlib.util.spec_from_file_location("retest_setups", STUDY / "retest_setups.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_dataset():
    spec = importlib.util.spec_from_file_location("deep_dataset", STUDY / "dataset.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_news():
    spec = importlib.util.spec_from_file_location("news_calendar", STUDY / "news_calendar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_calendar()


def add_london_range(df: pd.DataFrame) -> pd.DataFrame:
    """London high/low, only visible from 08:00 ET (no look-ahead)."""
    out = df.copy()
    hours = pd.DatetimeIndex(out.index).hour
    lon = (
        out.loc[(hours >= C.LONDON_START_HOUR) & (hours < C.LONDON_END_HOUR)]
        .groupby("session_date", sort=True)
        .agg(london_high=("High", "max"), london_low=("Low", "min"))
    )
    out = out.join(lon, on="session_date")
    after = (hours >= C.LONDON_END_HOUR) & (hours < C.ASIA_START_HOUR)
    out.loc[~after, ["london_high", "london_low"]] = np.nan
    out["london_mid"] = 0.5 * (out["london_high"] + out["london_low"])
    # First NY-morning close through the completed London range.
    first_up = np.zeros(len(out), dtype=bool)
    first_dn = np.zeros(len(out), dtype=bool)
    last_sess = None
    seen_up = seen_dn = False
    closes = out["Close"].to_numpy()
    ahi = out["london_high"].to_numpy()
    alo = out["london_low"].to_numpy()
    sess = out["session_date"].to_numpy()
    hrs = hours.to_numpy()
    for i in range(len(out)):
        if sess[i] != last_sess:
            seen_up = seen_dn = False
            last_sess = sess[i]
        if hrs[i] < C.NY_START_HOUR or hrs[i] >= 12:
            continue
        if np.isfinite(ahi[i]) and closes[i] > ahi[i]:
            if not seen_up:
                first_up[i] = True
            seen_up = True
        if np.isfinite(alo[i]) and closes[i] < alo[i]:
            if not seen_dn:
                first_dn[i] = True
            seen_dn = True
    out["lon_first_close_up"] = first_up
    out["lon_first_close_down"] = first_dn
    # First mid-touch rejection in NY morning (one long and one short flag).
    first_mid_up = np.zeros(len(out), dtype=bool)
    first_mid_dn = np.zeros(len(out), dtype=bool)
    last_sess = None
    seen_mu = seen_md = False
    highs = out["High"].to_numpy()
    lows = out["Low"].to_numpy()
    mid = out["london_mid"].to_numpy()
    loc = out["close_loc"].to_numpy() if "close_loc" in out.columns else np.full(len(out), np.nan)
    for i in range(len(out)):
        if sess[i] != last_sess:
            seen_mu = seen_md = False
            last_sess = sess[i]
        if hrs[i] < C.NY_START_HOUR or hrs[i] >= 12:
            continue
        if not np.isfinite(mid[i]):
            continue
        touched = lows[i] <= mid[i] <= highs[i]
        if not touched:
            continue
        if (not seen_mu) and closes[i] >= mid[i] and np.isfinite(loc[i]) and loc[i] >= 0.60:
            first_mid_up[i] = True
            seen_mu = True
        if (not seen_md) and closes[i] <= mid[i] and np.isfinite(loc[i]) and loc[i] <= 0.40:
            first_mid_dn[i] = True
            seen_md = True
    out["lon_mid_rej_up"] = first_mid_up
    out["lon_mid_rej_dn"] = first_mid_dn
    return out


def add_donchian(df: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """20-day Donchian flags on completed session dailies, mapped with no look-ahead."""
    d = daily.copy().sort_index()
    # Prior 20 session highs/lows, excluding the current daily bar.
    d["donch_high_20"] = d["High"].shift(1).rolling(20, min_periods=20).max()
    d["donch_low_20"] = d["Low"].shift(1).rolling(20, min_periods=20).min()
    d["donch_break_up"] = d["Close"] > d["donch_high_20"]
    d["donch_break_down"] = d["Close"] < d["donch_low_20"]
    d["donch_atr"] = d["d_atr"] if "d_atr" in d.columns else None
    if "d_atr" not in d.columns:
        from research.backtest.features import atr as atr_fn

        d["donch_atr"] = atr_fn(d)
    cols = ["donch_high_20", "donch_low_20", "donch_break_up", "donch_break_down", "donch_atr", "High", "Low", "Close"]
    src = d[cols].copy()
    # Available from 17:00 ET on that session date (daily close).
    src.index = src.index + pd.Timedelta(hours=17)
    src = src.rename(columns={"High": "d_high", "Low": "d_low", "Close": "d_donch_close"})
    # Map onto exec bars at the bar *open* so an 18:00 entry can use the just-closed daily.
    from research.backtest.features import _map_closed

    mapped = _map_closed(df.index, src, duration=pd.Timedelta(0), cols=list(src.columns))
    mapped.index = df.index
    out = df.copy()
    for c in mapped.columns:
        out[c] = mapped[c].to_numpy()
    return out


def add_news_flags(df: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """NFP/FOMC signal bars and a combined entry blackout."""
    out = df.copy()
    hours = pd.DatetimeIndex(out.index).hour
    dates = pd.DatetimeIndex(out.index).tz_convert(ET).normalize()
    out["news_blackout"] = out["nfp_blackout"].astype(bool) if "nfp_blackout" in out.columns else False

    cal = cal.copy()
    cal["ts"] = pd.to_datetime(cal["ts"], utc=True).dt.tz_convert(ET)
    cal["cal_date"] = cal["ts"].dt.normalize()

    nfp_days = set(cal.loc[cal["event"] == "NFP", "cal_date"])
    fomc_days = set(cal.loc[cal["event"] == "FOMC", "cal_date"])

    is_nfp_day = dates.isin(nfp_days)
    is_fomc_day = dates.isin(fomc_days)

    # FOMC blackout: 13:30–15:30 ET on FOMC dates (30 min before to 90 after 14:00).
    minutes = hours * 60 + pd.DatetimeIndex(out.index).minute
    fomc_win = (minutes >= 13 * 60 + 30) & (minutes < 15 * 60 + 30)
    out.loc[is_fomc_day & fomc_win, "news_blackout"] = True

    # Pre-news close: last close before 08:00 (NFP) / 14:00 (FOMC) on the event day.
    close = out["Close"]
    pre_nfp = close.where((hours == 7) & is_nfp_day)
    pre_fomc = close.where((hours == 13) & is_fomc_day)
    # Forward-fill within the calendar day only.
    pre_nfp = pre_nfp.groupby(dates).ffill()
    pre_fomc = pre_fomc.groupby(dates).ffill()

    out["nfp_signal"] = is_nfp_day & (hours == 9)
    out["fomc_signal"] = is_fomc_day & (hours == 14)
    out["nfp_pre_close"] = pre_nfp
    out["fomc_pre_close"] = pre_fomc
    out["nfp_cont_dir"] = np.where(out["nfp_signal"] & _finite_series(pre_nfp),
                                   np.sign(close - pre_nfp), 0)
    out["fomc_cont_dir"] = np.where(out["fomc_signal"] & _finite_series(pre_fomc),
                                    np.sign(close - pre_fomc), 0)

    # News-window extremes for stops: NFP 08:00–10:00; FOMC 14:00–15:00.
    out["nfp_win_low"] = np.nan
    out["nfp_win_high"] = np.nan
    out["fomc_win_low"] = np.nan
    out["fomc_win_high"] = np.nan
    # Compute per event day from the 08:00 and 09:00 bars (known at 09:00 close).
    hi = out["High"].to_numpy()
    lo = out["Low"].to_numpy()
    hr = hours.to_numpy()
    nfp_hi = np.full(len(out), np.nan)
    nfp_lo = np.full(len(out), np.nan)
    fomc_hi = np.full(len(out), np.nan)
    fomc_lo = np.full(len(out), np.nan)
    # Walk forward; on a 09:00 NFP bar, look back at the same-day 08:00 bar.
    idx_dates = dates
    for i in range(len(out)):
        if is_nfp_day[i] and hr[i] == 9:
            # find 08:00 same calendar date
            h08, l08 = hi[i], lo[i]
            for j in range(i, max(-1, i - 6), -1):
                if idx_dates[j] != idx_dates[i]:
                    break
                if hr[j] == 8:
                    h08 = max(h08, hi[j])
                    l08 = min(l08, lo[j])
                    break
            nfp_hi[i], nfp_lo[i] = h08, l08
        if is_fomc_day[i] and hr[i] == 14:
            fomc_hi[i], fomc_lo[i] = hi[i], lo[i]
    out["nfp_win_high"] = nfp_hi
    out["nfp_win_low"] = nfp_lo
    out["fomc_win_high"] = fomc_hi
    out["fomc_win_low"] = fomc_lo
    return out


def _finite_series(s: pd.Series) -> np.ndarray:
    return pd.notna(s).to_numpy()


def _sl_ok(entry: float, sl: float, direction: int, atr: float, max_atr: float = 3.0, min_sl: float = 5.0) -> bool:
    if not np.isfinite(atr) or atr <= 0 or not np.isfinite(sl) or not np.isfinite(entry):
        return False
    dist = abs(entry - sl)
    if dist < min_sl or dist > max_atr * atr:
        return False
    if direction == 1 and sl >= entry:
        return False
    if direction == -1 and sl <= entry:
        return False
    return True


def _trend(row: pd.Series, direction: int, how: str) -> bool:
    if how == "d4h":
        key = "trend_up_ma" if direction == 1 else "trend_down_ma"
        return bool(row.get(key, False))
    if how == "h4":
        key = "h4_trend_up_ma" if direction == 1 else "h4_trend_down_ma"
        return bool(row.get(key, False))
    return True


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

def sig_ny_lon_break(row: pd.Series, trend: str) -> Signal | None:
    ts = row.name
    hour = ts.hour if hasattr(ts, "hour") else -1
    if hour < C.NY_START_HOUR or hour >= 12:
        return None
    if bool(row.get("news_blackout", False)):
        return None
    if not _finite(row.get("london_high")):
        return None
    ahi, alo = float(row["london_high"]), float(row["london_low"])
    rng = ahi - alo
    if rng < C.MIN_SL:
        return None
    atr = _atr(row)
    close = float(row["Close"])
    if bool(row.get("lon_first_close_up", False)):
        if (close - ahi) > 0.5 * rng:
            return None
        if not _trend(row, 1, trend):
            return None
        sl = alo - C.SL_BUFFER_ATR * atr
        if _sl_ok(close, sl, 1, atr):
            return Signal("ny_lon_brk", 1, sl, f"lon_brk_up_{trend}", _next_level(row, 1, close))
    if bool(row.get("lon_first_close_down", False)):
        if (alo - close) > 0.5 * rng:
            return None
        if not _trend(row, -1, trend):
            return None
        sl = ahi + C.SL_BUFFER_ATR * atr
        if _sl_ok(close, sl, -1, atr):
            return Signal("ny_lon_brk", -1, sl, f"lon_brk_dn_{trend}", _next_level(row, -1, close))
    return None


def sig_ny_lon_mid(row: pd.Series) -> Signal | None:
    ts = row.name
    hour = ts.hour if hasattr(ts, "hour") else -1
    if hour < C.NY_START_HOUR or hour >= 12:
        return None
    if bool(row.get("news_blackout", False)):
        return None
    if not _finite(row.get("london_mid")):
        return None
    atr = _atr(row)
    close = float(row["Close"])
    mid = float(row["london_mid"])
    ahi, alo = float(row["london_high"]), float(row["london_low"])
    if bool(row.get("lon_mid_rej_up", False)) and _trend(row, 1, "d4h"):
        sl = min(float(row["Low"]), alo) - C.SL_BUFFER_ATR * atr
        if _sl_ok(close, sl, 1, atr):
            return Signal("ny_lon_mid", 1, sl, "lon_mid_long", _next_level(row, 1, close))
    if bool(row.get("lon_mid_rej_dn", False)) and _trend(row, -1, "d4h"):
        sl = max(float(row["High"]), ahi) + C.SL_BUFFER_ATR * atr
        if _sl_ok(close, sl, -1, atr):
            return Signal("ny_lon_mid", -1, sl, "lon_mid_short", _next_level(row, -1, close))
    return None


def sig_news(row: pd.Series, event: str, mode: str) -> Signal | None:
    """mode is 'cont' or 'fade'. Signal at the post-60-minute close."""
    flag = "nfp_signal" if event == "NFP" else "fomc_signal"
    dkey = "nfp_cont_dir" if event == "NFP" else "fomc_cont_dir"
    hikey = "nfp_win_high" if event == "NFP" else "fomc_win_high"
    lokey = "nfp_win_low" if event == "NFP" else "fomc_win_low"
    if not bool(row.get(flag, False)):
        return None
    direction = int(np.sign(row.get(dkey, 0) or 0))
    if direction == 0:
        return None
    if mode == "fade":
        direction = -direction
    atr = _atr(row)
    close = float(row["Close"])
    if direction == 1:
        sl = float(row[lokey]) - C.SL_BUFFER_ATR * atr
    else:
        sl = float(row[hikey]) + C.SL_BUFFER_ATR * atr
    if _sl_ok(close, sl, direction, atr):
        return Signal(f"news_{event.lower()}_{mode}", direction, sl, f"{event}_{mode}", None)
    return None


def sig_pdh_sweep(row: pd.Series, session: str) -> Signal | None:
    """Prior-day high/low sweep and close back in, with D+4H trend, one session."""
    if str(row.get("session", "")) != session:
        return None
    if bool(row.get("news_blackout", False)):
        return None
    atr = _atr(row)
    if not np.isfinite(atr):
        return None
    close = float(row["Close"])
    high = float(row["High"])
    low = float(row["Low"])
    min_excess = max(C.SWEEP_MIN_EXCESS, 0.15 * atr)
    min_inside = max(C.SWEEP_CLOSE_INSIDE, 0.08 * atr)
    # Sell: sweep PDH, close back inside, downtrend.
    if _finite(row.get("prior_high")):
        lvl = float(row["prior_high"])
        if high >= lvl + min_excess and close <= lvl - min_inside and float(row.get("close_loc", 1) or 1) <= 0.55:
            if _trend(row, -1, "d4h"):
                sl = high + C.SL_BUFFER_ATR * atr
                if _sl_ok(close, sl, -1, atr):
                    return Signal("pdh_sweep", -1, sl, f"pdh_{session}", _next_level(row, -1, close))
    if _finite(row.get("prior_low")):
        lvl = float(row["prior_low"])
        if low <= lvl - min_excess and close >= lvl + min_inside and float(row.get("close_loc", 0) or 0) >= 0.45:
            if _trend(row, 1, "d4h"):
                sl = low - C.SL_BUFFER_ATR * atr
                if _sl_ok(close, sl, 1, atr):
                    return Signal("pdh_sweep", 1, sl, f"pdl_{session}", _next_level(row, 1, close))
    return None


def sig_donchian_at_open(row: pd.Series, mode: str) -> Signal | None:
    """Evaluated at the 18:00 ET bar, using the just-closed prior daily only."""
    ts = row.name
    if not hasattr(ts, "hour") or ts.hour != C.ASIA_START_HOUR:
        return None
    if not bool(row.get("donch_break_up", False)) and not bool(row.get("donch_break_down", False)):
        return None
    atr_d = row.get("donch_atr")
    if not _finite(atr_d) or float(atr_d) <= 0:
        atr_d = row.get("d_atr")
    if not _finite(atr_d) or float(atr_d) <= 0:
        return None
    atr_d = float(atr_d)
    mid = float(row["Open"])  # entry is this open; signal uses daily flags only
    # Regime: close of the completed daily vs its 200-SMA (already mapped, no look-ahead).
    above_200 = bool(row.get("d_above_mas", False)) or (
        _finite(row.get("d_close")) and _finite(row.get("d_sma200")) and float(row["d_close"]) > float(row["d_sma200"])
    )
    below_200 = bool(row.get("d_below_mas", False)) or (
        _finite(row.get("d_close")) and _finite(row.get("d_sma200")) and float(row["d_close"]) < float(row["d_sma200"])
    )
    if bool(row.get("donch_break_up", False)):
        if mode == "long" or mode == "both" or (mode == "reg" and above_200):
            sl = mid - 2.0 * atr_d
            # Daily stops are wide; allow up to 4x daily ATR (exactly 2x by construction,
            # plus a small gap/open difference). Min $10.
            if _sl_ok(mid, sl, 1, atr_d, max_atr=4.0, min_sl=10.0):
                return Signal("donch20", 1, sl, f"donch_up_{mode}", None)
    if bool(row.get("donch_break_down", False)) and mode != "long":
        if mode == "both" or (mode == "reg" and below_200):
            sl = mid + 2.0 * atr_d
            if _sl_ok(mid, sl, -1, atr_d, max_atr=4.0, min_sl=10.0):
                return Signal("donch20", -1, sl, f"donch_dn_{mode}", None)
    return None


# ---------------------------------------------------------------------------
# Donchian runner: enter at the 18:00 open (stock engine would miss this
# because the daily close falls in the 17:00 break hour).
# ---------------------------------------------------------------------------

def run_open_entry(df: pd.DataFrame, signal_at_bar, setup_name: str):
    n = len(df)
    idx = df.index
    equity = C.START_EQUITY
    trades = []
    pos = None
    sess_start_eq = equity
    sess_realized = 0.0
    last_session = None
    eq_times, eq_vals = [], []
    engine = Engine(df, lambda r: None, setup_name=setup_name)

    for i in range(n):
        row = df.iloc[i]
        t = idx[i]
        sess = row["session_date"]
        if last_session is None or sess != last_session:
            sess_start_eq = equity
            sess_realized = 0.0
            last_session = sess

        if pos is not None:
            engine._manage(pos, row, t, equity)
            if not pos.open:
                equity += pos.pnl
                sess_realized += pos.pnl
                trades.append(pos)
                pos = None

        if pos is None:
            blocked = sess_realized <= -C.DAILY_LOSS_STOP * sess_start_eq
            if (not blocked) and str(row.get("session", "")) != "break":
                sig = signal_at_bar(row)
                if sig is not None:
                    pos = engine._try_enter(sig, row, t, equity)
                    if pos is not None:
                        engine._manage(pos, row, t, equity, entry_bar=True)
                        if not pos.open:
                            equity += pos.pnl
                            sess_realized += pos.pnl
                            trades.append(pos)
                            pos = None

        mtm = equity
        if pos is not None:
            mtm += pos.direction * (float(row["Close"]) - pos.entry) * pos.remaining * C.CONTRACT_OZ
            if pos.tp1_done:
                mtm += pos.pnl
        eq_times.append(t)
        eq_vals.append(mtm)

    if pos is not None:
        last = df.iloc[-1]
        px = exit_fill(pos.direction, float(last["Close"]))
        engine._close(pos, idx[-1], px, pos.remaining, "eod_flat")
        equity += pos.pnl
        trades.append(pos)

    eq = pd.DataFrame({"equity": eq_vals}, index=pd.DatetimeIndex(eq_times, name="Datetime"))
    return trades, eq


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _year_col(tf: pd.DataFrame) -> pd.Series:
    et = pd.to_datetime(tf["entry_time"], utc=True)
    return et.dt.tz_convert(ET).dt.year


def slice_metrics(tf: pd.DataFrame, equity: pd.DataFrame | None, mask: pd.Series | None) -> dict:
    if tf is None or tf.empty:
        return summarize(tf, None)
    part = tf if mask is None else tf.loc[mask]
    return summarize(part, None)


def year_table(tf: pd.DataFrame) -> pd.DataFrame:
    if tf is None or tf.empty:
        return pd.DataFrame()
    t = tf.copy()
    t["year"] = _year_col(t)
    t = t[t["year"] >= 2012]
    rows = []
    for y, part in t.groupby("year"):
        s = summarize(part, None)
        s["year"] = int(y)
        rows.append(s)
    return pd.DataFrame(rows)


def stability(years: pd.DataFrame) -> dict:
    if years is None or years.empty:
        return {"oos_years": 0, "oos_years_positive": 0, "oos_year_share_positive": np.nan,
                "oos_avg_r_mean": np.nan, "oos_avg_r_std": np.nan, "oos_min_year_avg_r": np.nan,
                "oos_min_year": None}
    pos = int((years["avg_r"] > 0).sum())
    return {
        "oos_years": int(len(years)),
        "oos_years_positive": pos,
        "oos_year_share_positive": pos / len(years) if len(years) else np.nan,
        "oos_avg_r_mean": float(years["avg_r"].mean()),
        "oos_avg_r_std": float(years["avg_r"].std(ddof=1)) if len(years) > 1 else np.nan,
        "oos_min_year_avg_r": float(years["avg_r"].min()),
        "oos_min_year": int(years.loc[years["avg_r"].idxmin(), "year"]),
    }


def adopt_decision(oos: dict, mid: dict, stab: dict) -> tuple[bool, str]:
    reasons = []
    n = int(oos.get("n") or 0)
    avg = oos.get("avg_r")
    pf = oos.get("profit_factor")
    if n < 40:
        reasons.append(f"OOS n={n}<40")
    if not (isinstance(avg, (int, float)) and np.isfinite(avg) and avg > 0):
        reasons.append(f"OOS avgR={avg}")
    if not (isinstance(pf, (int, float)) and np.isfinite(pf) and pf >= 1.20):
        reasons.append(f"OOS PF={pf}")
    if int(stab.get("oos_years_positive") or 0) < 8:
        reasons.append(f"green years {stab.get('oos_years_positive')}/{stab.get('oos_years')}")
    mid_r, mid_pf = mid.get("avg_r"), mid.get("profit_factor")
    mid_n = int(mid.get("n") or 0)
    if mid_n < 20:
        reasons.append(f"2012-2023 n={mid_n}<20")
    if not (isinstance(mid_r, (int, float)) and np.isfinite(mid_r) and mid_r >= 0):
        reasons.append(f"2012-2023 avgR={mid_r}")
    if not (isinstance(mid_pf, (int, float)) and np.isfinite(mid_pf) and mid_pf >= 1.0):
        reasons.append(f"2012-2023 PF={mid_pf}")
    if reasons:
        return False, "; ".join(reasons)
    return True, "meets pre-registered bar"


def _record(name: str, family: str, trades, equity, rows: list, year_rows: list):
    RESULTS.mkdir(parents=True, exist_ok=True)
    tf = trades_frame(trades)
    if not tf.empty:
        tf.to_csv(RESULTS / f"trades_{name}.csv", index=False)
    et = pd.to_datetime(tf["entry_time"], utc=True) if not tf.empty else pd.Series(dtype="datetime64[ns, UTC]")
    if not tf.empty:
        et = et.dt.tz_convert(ET)
    def _mask(start, end=None):
        if tf.empty:
            return pd.Series(dtype=bool)
        if end is None:
            return et >= start
        return (et >= start) & (et < end)

    full = summarize(trades, equity)
    is_ = slice_metrics(tf, None, _mask(tf["entry_time"].min() if not tf.empty else OOS_START, OOS_START) if not tf.empty else None)
    # rebuild IS mask cleanly
    if not tf.empty:
        is_ = summarize(tf.loc[et < OOS_START], None)
        oos = summarize(tf.loc[et >= OOS_START], None)
        mid = summarize(tf.loc[(et >= OOS_START) & (et < CUT_2024)], None)
        rec = summarize(tf.loc[et >= CUT_2024], None)
    else:
        is_ = oos = mid = rec = summarize(tf, None)
    yrs = year_table(tf)
    stab = stability(yrs)
    adopted, why = adopt_decision(oos, mid, stab)
    for s, sample in ((full, "full"), (is_, "IS_2009_2011"), (oos, "OOS_2012_2026"),
                      (mid, "OOS_2012_2023"), (rec, "OOS_2024_2026")):
        s = dict(s)
        s["variant"] = name
        s["family"] = family
        s["sample"] = sample
        if sample == "OOS_2012_2026":
            s.update(stab)
            s["adopt"] = adopted
            s["adopt_reason"] = why
        rows.append(s)
    if not yrs.empty:
        yrs = yrs.copy()
        yrs["variant"] = name
        yrs["family"] = family
        year_rows.append(yrs)
    print(
        f"{name:22s} OOS n={oos.get('n')} wr={oos.get('win_rate')} "
        f"avgR={oos.get('avg_r')} PF={oos.get('profit_factor')} "
        f"DD={oos.get('max_dd_pct')} 2012-23 avgR={mid.get('avg_r')} PF={mid.get('profit_factor')} "
        f"24-26 avgR={rec.get('avg_r')} yrs={stab.get('oos_years_positive')}/{stab.get('oos_years')} "
        f"{'ADOPT' if adopted else 'watchlist'} ({why})"
    )
    return adopted


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    rt = _load_retest()
    print("loading exec + features...")
    df = rt.load_exec()
    ds = _load_dataset()
    daily = ds.load_resampled()["XAUUSD_daily"]
    cal = _load_news()
    print("adding London range, Donchian, news flags...")
    df = add_london_range(df)
    df = add_donchian(df, daily)
    df = add_news_flags(df, cal)
    # For A/D, reuse the engine news block by copying news_blackout onto nfp_blackout.
    df_ad = df.copy()
    df_ad["nfp_blackout"] = df_ad["news_blackout"].astype(bool)

    rows: list[dict] = []
    year_rows: list[pd.DataFrame] = []
    adopted_names: list[str] = []

    # ----- Family A -----
    variants_a = [
        ("A_ny_lon_brk_d4h", lambda r: sig_ny_lon_break(r, "d4h")),
        ("A_ny_lon_brk_h4", lambda r: sig_ny_lon_break(r, "h4")),
        ("A_ny_lon_mid_pb", sig_ny_lon_mid),
    ]
    for name, fn in variants_a:
        print("running", name, "...")
        trades, eq = run_engine(df_ad, fn, nfp_filter=True, setup_name=name)
        if _record(name, "A_ny", trades, eq, rows, year_rows):
            adopted_names.append(name)

    # ----- Family B -----
    variants_b = [
        ("B_nfp_cont", lambda r: sig_news(r, "NFP", "cont")),
        ("B_nfp_fade", lambda r: sig_news(r, "NFP", "fade")),
        ("B_fomc_cont", lambda r: sig_news(r, "FOMC", "cont")),
        ("B_fomc_fade", lambda r: sig_news(r, "FOMC", "fade")),
    ]
    for name, fn in variants_b:
        print("running", name, "...")
        trades, eq = run_engine(df, fn, nfp_filter=False, setup_name=name)
        if _record(name, "B_news", trades, eq, rows, year_rows):
            adopted_names.append(name)

    # ----- Family C -----
    variants_c = [
        ("C_donch20", "both"),
        ("C_donch20_long", "long"),
        ("C_donch20_reg", "reg"),
    ]
    for name, mode in variants_c:
        print("running", name, "...")
        trades, eq = run_open_entry(df, lambda r, m=mode: sig_donchian_at_open(r, m), name)
        if _record(name, "C_trend", trades, eq, rows, year_rows):
            adopted_names.append(name)

    # ----- Family D -----
    variants_d = [
        ("D_pdh_ny_reg", lambda r: sig_pdh_sweep(r, "ny")),
        ("D_pdh_lon_reg", lambda r: sig_pdh_sweep(r, "london")),
    ]
    for name, fn in variants_d:
        print("running", name, "...")
        trades, eq = run_engine(df_ad, fn, nfp_filter=True, setup_name=name)
        if _record(name, "D_sweep", trades, eq, rows, year_rows):
            adopted_names.append(name)

    summary = pd.DataFrame(rows)
    yearly = pd.concat(year_rows, ignore_index=True) if year_rows else pd.DataFrame()
    summary.to_csv(RESULTS / "wf_summary.csv", index=False)
    yearly.to_csv(RESULTS / "wf_oos_years.csv", index=False)
    (RESULTS / "adoption.json").write_text(json.dumps({
        "n_pre_registered": N_PRE_REGISTERED,
        "n_tested": N_PRE_REGISTERED,
        "n_post_hoc": 0,
        "adopted": adopted_names,
        "criteria": {
            "oos_n_min": 40,
            "oos_avg_r": ">0",
            "oos_pf_min": 1.20,
            "oos_green_years_min": 8,
            "oos_green_years_of": 15,
            "mid_2012_2023_avg_r": ">=0",
            "mid_2012_2023_pf_min": 1.0,
            "mid_n_min": 20,
        },
    }, indent=2) + "\n")

    # Yearly plot
    if not yearly.empty:
        fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True, sharey=True)
        fams = [("A_ny", "A: NY + trend"), ("B_news", "B: post-news"),
                ("C_trend", "C: daily Donchian"), ("D_sweep", "D: PDH sweep")]
        for ax, (fam, title) in zip(axes.ravel(), fams):
            part = yearly[yearly["family"] == fam]
            for name, g in part.groupby("variant"):
                ax.plot(g["year"], g["avg_r"], marker="o", ms=3.5, label=name)
            ax.axhline(0, color="black", lw=0.8)
            ax.set_title(title)
            ax.legend(fontsize=7)
            ax.set_ylabel("avg R")
        fig.suptitle("Phase 2 walk-forward yearly expectancy (OOS 2012–2026)")
        fig.tight_layout()
        fig.savefig(FIGS / "phase2_yearly_avg_r.png", dpi=140)
        plt.close()

    print("\nTESTED", N_PRE_REGISTERED, "pre-registered variants; post-hoc adds: 0")
    print("ADOPTED:", adopted_names or "(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

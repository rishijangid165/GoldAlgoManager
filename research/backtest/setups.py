"""Rule-based approximations of the discretionary gold setups.

These are intentionally simple. They do not capture the full chart read
(the human process still decides live). They exist so we can measure
whether the *shape* of each idea had a positive expectancy on GC=F.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .engine import Signal

SETUP_NAMES = ("pullback", "sweep", "breakout", "rsi_mr")
COMBO_CORE = ("pullback", "sweep")  # chosen a priori: structure setups, not the RSI control
COMBO_ALL = ("pullback", "sweep", "breakout", "rsi_mr")

# Zones for pullback / next-target use major (4H and daily) swings only.
# 1H swings are too local and flooded the first signal count (~2,600/2y).
SUPPLY_KEYS = ("h4_swing_high", "d_swing_high")
DEMAND_KEYS = ("h4_swing_low", "d_swing_low")


def _finite(x) -> bool:
    try:
        return x is not None and np.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _atr(row: pd.Series) -> float:
    for key in ("atr_sl", "h1_atr", "atr"):
        if _finite(row.get(key)):
            return float(row[key])
    return float("nan")


def _trend_ok(row: pd.Series, direction: int, trend_filter: bool, strict: bool) -> bool:
    if not trend_filter:
        return True
    down_key = "trend_down_strict" if strict else "trend_down_ma"
    up_key = "trend_up_strict" if strict else "trend_up_ma"
    if direction == -1:
        return bool(row.get(down_key, False))
    return bool(row.get(up_key, False))


def _sl_valid(row: pd.Series, sl: float, planned_entry: float, direction: int) -> bool:
    atr = _atr(row)
    if not np.isfinite(atr) or atr <= 0:
        return False
    dist = abs(planned_entry - sl)
    if dist < C.MIN_SL:
        return False
    if dist > C.MAX_SL_ATR_1H * atr:
        return False
    if direction == 1 and sl >= planned_entry:
        return False
    if direction == -1 and sl <= planned_entry:
        return False
    return True


def _next_level(row: pd.Series, direction: int, planned_entry: float) -> float | None:
    keys = DEMAND_KEYS if direction == -1 else SUPPLY_KEYS
    # For a sell, the next support is a swing low below entry; also prior/asia lows.
    extras = ("prior_low", "asia_low") if direction == -1 else ("prior_high", "asia_high")
    cands = []
    for k in keys + extras:
        v = row.get(k)
        if not _finite(v):
            continue
        v = float(v)
        if direction == -1 and v < planned_entry:
            cands.append(v)
        if direction == 1 and v > planned_entry:
            cands.append(v)
    if not cands:
        return None
    # Nearest level in the trade's direction.
    return max(cands) if direction == -1 else min(cands)


def _tagged_zones(row: pd.Series, side: str) -> list[tuple[str, float, float, float]]:
    atr = _atr(row)
    if not np.isfinite(atr):
        return []
    keys = SUPPLY_KEYS if side == "supply" else DEMAND_KEYS
    high, low = float(row["High"]), float(row["Low"])
    out = []
    for key in keys:
        if not _finite(row.get(key)):
            continue
        level = float(row[key])
        if side == "supply":
            zlo = level - C.ZONE_INSIDE_ATR * atr
            zhi = level + C.ZONE_OUTSIDE_ATR * atr
        else:
            zlo = level - C.ZONE_OUTSIDE_ATR * atr
            zhi = level + C.ZONE_INSIDE_ATR * atr
        if high >= zlo and low <= zhi:
            out.append((key, level, zlo, zhi))
    return out


def _rejection(row: pd.Series, direction: int) -> bool:
    atr = _atr(row)
    if not np.isfinite(atr) or float(row["bar_range"]) < C.MIN_REJECTION_ATR * atr:
        return False
    close_loc = row.get("close_loc")
    if not _finite(close_loc):
        return False
    if direction == -1:
        wick_ok = float(row.get("upper_wick_frac", 0) or 0) >= C.REJECTION_WICK_FRAC
        loc_ok = float(close_loc) <= C.REJECTION_BODY_SIDE
        body_ok = bool(row.get("bearish", False)) or wick_ok
        return loc_ok and body_ok
    wick_ok = float(row.get("lower_wick_frac", 0) or 0) >= C.REJECTION_WICK_FRAC
    loc_ok = float(close_loc) >= (1.0 - C.REJECTION_BODY_SIDE)
    body_ok = bool(row.get("bullish", False)) or wick_ok
    return loc_ok and body_ok


def pullback(row: pd.Series, trend_filter: bool, strict: bool) -> Signal | None:
    """D/4H trend + 1H (or exec-TF) rejection in a prior swing supply/demand zone."""
    if str(row.get("session", "")) not in ("london", "ny"):
        return None
    close = float(row["Close"])
    atr = _atr(row)
    for direction, side in ((-1, "supply"), (1, "demand")):
        if not _trend_ok(row, direction, trend_filter, strict):
            continue
        if not _rejection(row, direction):
            continue
        zones = _tagged_zones(row, side)
        if not zones:
            continue
        # Nearest zone to price (lowest supply / highest demand).
        if direction == -1:
            key, level, zlo, zhi = min(zones, key=lambda z: z[1])
            if close > zhi:
                continue  # closed through supply — not a rejection
            sl = max(float(row["High"]), zhi) + C.SL_BUFFER_ATR * atr
        else:
            key, level, zlo, zhi = max(zones, key=lambda z: z[1])
            if close < zlo:
                continue
            sl = min(float(row["Low"]), zlo) - C.SL_BUFFER_ATR * atr
        if not _sl_valid(row, sl, close, direction):
            continue
        return Signal(
            setup="pullback",
            direction=direction,
            sl=sl,
            reason=f"reject_{key}",
            next_level=_next_level(row, direction, close),
        )
    return None


def sweep(row: pd.Series, trend_filter: bool, strict: bool) -> Signal | None:
    """Sweep of prior-day or Asia high/low, close back inside, then fade."""
    sess = str(row.get("session", ""))
    if sess not in ("london", "ny"):
        return None
    atr = _atr(row)
    close = float(row["Close"])
    high = float(row["High"])
    low = float(row["Low"])

    sell_levels = []
    buy_levels = []
    if _finite(row.get("prior_high")):
        sell_levels.append(("pdh", float(row["prior_high"])))
    if _finite(row.get("asia_high")):
        sell_levels.append(("asia_h", float(row["asia_high"])))
    if _finite(row.get("prior_low")):
        buy_levels.append(("pdl", float(row["prior_low"])))
    if _finite(row.get("asia_low")):
        buy_levels.append(("asia_l", float(row["asia_low"])))

    def _fade(direction: int, tags: list[str], swept_extreme: float) -> Signal | None:
        if not _trend_ok(row, direction, trend_filter, strict):
            return None
        sl = (swept_extreme + C.SL_BUFFER_ATR * atr) if direction == -1 else (
            swept_extreme - C.SL_BUFFER_ATR * atr
        )
        if not _sl_valid(row, sl, close, direction):
            return None
        return Signal(
            setup="sweep",
            direction=direction,
            sl=sl,
            reason="sweep_" + "+".join(tags),
            next_level=_next_level(row, direction, close),
        )

    min_excess = max(C.SWEEP_MIN_EXCESS, 0.15 * atr) if np.isfinite(atr) else C.SWEEP_MIN_EXCESS
    min_inside = max(C.SWEEP_CLOSE_INSIDE, 0.08 * atr) if np.isfinite(atr) else C.SWEEP_CLOSE_INSIDE

    sell_tags = [
        name
        for name, lvl in sell_levels
        if high >= lvl + min_excess and close <= lvl - min_inside
        and float(row.get("close_loc", 1) or 1) <= 0.55
    ]
    if sell_tags:
        swept = max(lvl for name, lvl in sell_levels if name in sell_tags)
        # extreme is the wick, not just the level
        sig = _fade(-1, sell_tags, high)
        if sig:
            return sig

    buy_tags = [
        name
        for name, lvl in buy_levels
        if low <= lvl - min_excess and close >= lvl + min_inside
        and float(row.get("close_loc", 0) or 0) >= 0.45
    ]
    if buy_tags:
        sig = _fade(1, buy_tags, low)
        if sig:
            return sig
    return None


def breakout(row: pd.Series, trend_filter: bool, strict: bool) -> Signal | None:
    """London/NY close-break of the completed Asia range, in the trend direction."""
    ts = row.name
    hour = ts.hour if hasattr(ts, "hour") else -1
    if hour < C.ASIA_END_HOUR or hour >= C.BREAKOUT_ENTRY_UNTIL_HOUR:
        return None
    if not _finite(row.get("asia_high")) or not _finite(row.get("asia_low")):
        return None
    ahi, alo = float(row["asia_high"]), float(row["asia_low"])
    rng = ahi - alo
    if rng < C.MIN_SL:
        return None
    atr = _atr(row)
    close = float(row["Close"])

    if bool(row.get("asia_first_close_up", False)):
        direction = 1
        if (close - ahi) > 0.5 * rng:
            return None  # already extended — don't chase
        sl = alo - C.SL_BUFFER_ATR * atr
        if _trend_ok(row, direction, trend_filter, strict) and _sl_valid(row, sl, close, direction):
            return Signal("breakout", direction, sl, "asia_break_up", _next_level(row, direction, close))
    if bool(row.get("asia_first_close_down", False)):
        direction = -1
        if (alo - close) > 0.5 * rng:
            return None
        sl = ahi + C.SL_BUFFER_ATR * atr
        if _trend_ok(row, direction, trend_filter, strict) and _sl_valid(row, sl, close, direction):
            return Signal("breakout", direction, sl, "asia_break_down", _next_level(row, direction, close))
    return None


def rsi_mr(row: pd.Series, trend_filter: bool, strict: bool) -> Signal | None:
    """Control: 1H (exec) RSI extreme at a prior-day / swing level, fade the spike."""
    if str(row.get("session", "")) not in ("london", "ny"):
        return None
    if not _finite(row.get("rsi")):
        return None
    rsi = float(row["rsi"])
    atr = _atr(row)
    close = float(row["Close"])
    high = float(row["High"])
    low = float(row["Low"])
    band = 0.35 * atr if np.isfinite(atr) else 5.0

    supports = [row.get(k) for k in ("d_swing_low", "h4_swing_low", "prior_low", "asia_low")]
    resists = [row.get(k) for k in ("d_swing_high", "h4_swing_high", "prior_high", "asia_high")]

    def _near(level, extreme) -> bool:
        return _finite(level) and abs(float(level) - extreme) <= band

    if rsi <= 30:
        tagged = [float(lv) for lv in supports if _near(lv, low)]
        if tagged and close >= min(tagged) - C.SWEEP_CLOSE_INSIDE:
            if _trend_ok(row, 1, trend_filter, strict):
                sl = min(low, min(tagged)) - C.SL_BUFFER_ATR * atr
                if _sl_valid(row, sl, close, 1):
                    return Signal("rsi_mr", 1, sl, f"rsi_{rsi:.0f}_support", _next_level(row, 1, close))
    if rsi >= 70:
        tagged = [float(lv) for lv in resists if _near(lv, high)]
        if tagged and close <= max(tagged) + C.SWEEP_CLOSE_INSIDE:
            if _trend_ok(row, -1, trend_filter, strict):
                sl = max(high, max(tagged)) + C.SL_BUFFER_ATR * atr
                if _sl_valid(row, sl, close, -1):
                    return Signal("rsi_mr", -1, sl, f"rsi_{rsi:.0f}_resist", _next_level(row, -1, close))
    return None


EVALUATORS = {
    "pullback": pullback,
    "sweep": sweep,
    "breakout": breakout,
    "rsi_mr": rsi_mr,
}


def make_signal_fn(setup: str, trend_filter: bool = False, strict: bool = False):
    if setup.startswith("combo"):
        names = COMBO_ALL if setup == "combo_all" else COMBO_CORE

        def combo(row: pd.Series) -> Signal | None:
            for name in names:
                sig = EVALUATORS[name](row, trend_filter, strict)
                if sig is not None:
                    sig.setup = f"{setup}:{sig.setup}"
                    return sig
            return None

        return combo

    ev = EVALUATORS[setup]

    def fn(row: pd.Series) -> Signal | None:
        return ev(row, trend_filter, strict)

    return fn

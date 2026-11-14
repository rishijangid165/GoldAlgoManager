"""M1-path trade simulator for the weekend study (pre-registered in PREREGISTRATION.md).

Prices are broker BID bars; a long is filled at ask (= bid + spread) and exits at bid,
a short is filled at bid and exits at ask. Every fill also pays $0.10 slippage.
The only remaining same-bar ambiguity is inside one M1 bar, where the stop is assumed first.

Exit modes
 0 baseline: TP1 1.5R (half) -> stop to entry; TP2 3R or next_level in (1.5R, 3R)
 1 EA v1.03.1 trail: baseline, plus after TP1 the runner stop trails to the tighter of
   the last confirmed M15 swing (2 bars each side) and market -/+ 1 x ATR(M15,14),
   only tightening, >= $0.20 step, re-evaluated at every M1 close
 2 no partial, fixed 2R target
 3 chandelier: no partial, no TP; once +1R is reached, stop = best close -/+ 3 x ATR(H1,14)
"""
from __future__ import annotations

import numpy as np
from numba import njit

SLIP = 0.10
MIN_SL = 5.0

# reason codes
R_SKIP, R_SL, R_TP2, R_BE, R_TRAIL, R_FRI, R_EOD, R_TP_FULL = -1, 1, 2, 3, 4, 5, 6, 7


@njit(cache=True)
def simulate(o, h, l, c, spr, start, d, sl0, next_level, mode, fri_flat, tr_lo, tr_hi, atr15, atr_h1):
    """Returns (exit_i, R, tp1_hit, reason, n_ambiguous, entry_fill, sl_dist)."""
    n = len(o)
    s0 = spr[start]
    if d == 1:
        entry = o[start] + s0 + SLIP
    else:
        entry = o[start] - SLIP
    if (d == 1 and entry <= sl0) or (d == -1 and entry >= sl0):
        return start, 0.0, False, R_SKIP, 0, entry, 0.0
    dist = abs(entry - sl0)
    if dist < MIN_SL:
        return start, 0.0, False, R_SKIP, 0, entry, dist
    tp1 = entry + d * 1.5 * dist
    tp2 = entry + d * 3.0 * dist
    if mode == 0 or mode == 1:
        if np.isfinite(next_level):
            ld = d * (next_level - entry)
            if 1.5 * dist < ld < 3.0 * dist:
                tp2 = next_level
    use_tp1 = mode == 0 or mode == 1
    if mode == 2:
        tp2 = entry + d * 2.0 * dist
    use_tp2 = mode != 3
    sl = sl0
    tp1_done = False
    realized = 0.0  # in price units per full position
    rem = 1.0
    amb = 0
    best = entry
    armed = False
    for i in range(start, n):
        sp = spr[i]
        if d == 1:
            p_open, p_adv, p_fav, p_close = o[i], l[i], h[i], c[i]
        else:
            p_open, p_adv, p_fav, p_close = o[i] + sp, h[i] + sp, l[i] + sp, c[i] + sp
        if i > start:
            if fri_flat[i]:
                realized += rem * d * (p_open - d * SLIP - entry)
                return i, realized / dist, tp1_done, R_FRI, amb, entry, dist
            # gap at the open
            if d * (p_open - sl) <= 0:
                realized += rem * d * (p_open - d * SLIP - entry)
                rc = R_SL
                if tp1_done:
                    rc = R_BE if sl == entry else R_TRAIL
                elif mode == 3 and armed:
                    rc = R_TRAIL
                return i, realized / dist, tp1_done, rc, amb, entry, dist
            if use_tp2 and d * (p_open - tp2) >= 0:
                if use_tp1 and not tp1_done:
                    realized += 0.5 * d * (p_open - d * SLIP - entry)
                    rem = 0.5
                    tp1_done = True
                realized += rem * d * (p_open - d * SLIP - entry)
                return i, realized / dist, tp1_done, R_TP2 if use_tp1 else R_TP_FULL, amb, entry, dist
            if use_tp1 and (not tp1_done) and d * (p_open - tp1) >= 0:
                realized += 0.5 * d * (p_open - d * SLIP - entry)
                rem = 0.5
                tp1_done = True
                if mode == 0 or mode == 1:
                    sl = entry if d * (entry - sl) > 0 else sl
        sl_touch = d * (p_adv - sl) <= 0
        tp2_touch = use_tp2 and d * (p_fav - tp2) >= 0
        tp1_touch = use_tp1 and (not tp1_done) and d * (p_fav - tp1) >= 0
        if sl_touch and (tp1_touch or tp2_touch):
            amb += 1
            realized += rem * d * (sl - d * SLIP - entry)
            rc = R_SL
            if tp1_done:
                rc = R_BE if sl == entry else R_TRAIL
            elif mode == 3 and armed:
                rc = R_TRAIL
            return i, realized / dist, tp1_done, rc, amb, entry, dist
        if sl_touch:
            realized += rem * d * (sl - d * SLIP - entry)
            rc = R_SL
            if tp1_done:
                rc = R_BE if sl == entry else R_TRAIL
            elif mode == 3 and armed:
                rc = R_TRAIL
            return i, realized / dist, tp1_done, rc, amb, entry, dist
        if tp1_touch:
            realized += 0.5 * d * (tp1 - d * SLIP - entry)
            rem = 0.5
            tp1_done = True
            sl = entry
            be_touch = d * (p_adv - sl) <= 0
            if be_touch:
                # order of TP1 and the return to entry inside one M1 bar is unknown: assume worst
                amb += 1
                realized += rem * d * (sl - d * SLIP - entry)
                return i, realized / dist, True, R_BE, amb, entry, dist
            if tp2_touch:
                realized += rem * d * (tp2 - d * SLIP - entry)
                return i, realized / dist, True, R_TP2, amb, entry, dist
        elif tp2_touch:
            realized += rem * d * (tp2 - d * SLIP - entry)
            return i, realized / dist, tp1_done, R_TP2 if use_tp1 else R_TP_FULL, amb, entry, dist
        # ---- end-of-M1-bar stop updates (apply from the next bar) ----
        if mode == 1 and tp1_done:
            if d == 1:
                cand = tr_lo[i]
                a = c[i] - atr15[i]
                if np.isfinite(a) and (not np.isfinite(cand) or a > cand):
                    cand = a
                if np.isfinite(cand) and cand < c[i] and cand - sl >= 0.20:
                    sl = cand
            else:
                cand = tr_hi[i]
                a = c[i] + sp + atr15[i]
                if np.isfinite(a) and (not np.isfinite(cand) or a < cand):
                    cand = a
                if np.isfinite(cand) and cand > c[i] + sp and sl - cand >= 0.20:
                    sl = cand
        if mode == 3:
            if d * (p_fav - entry) >= dist:
                armed = True
            if d * (p_close - best) > 0:
                best = p_close
            if armed and np.isfinite(atr_h1[i]):
                cand = best - d * 3.0 * atr_h1[i]
                if d * (cand - sl) > 0 and d * (p_close - cand) > 0:
                    sl = cand
    # end of data: mark at last close
    i = n - 1
    pc = c[i] if d == 1 else c[i] + spr[i]
    realized += rem * d * (pc - d * SLIP - entry)
    return i, realized / dist, tp1_done, R_EOD, amb, entry, dist


@njit(cache=True)
def m15_trail_levels(hi, lo):
    """Per closed M15 bar j: the EA's LastClosedSwing low/high as seen right after bar j closes."""
    n = len(hi)
    sw_lo = np.full(n, np.nan)
    sw_hi = np.full(n, np.nan)
    side = 2
    need = side * 2 + 8
    for j in range(n):
        # buf[k] = bar j-k, k = 0..need-1
        cnt = min(need, j + 1)
        if cnt < side * 2 + 1:
            continue
        for want_high in (True, False):
            for k in range(side, cnt - side):
                ok = True
                for q in range(1, side + 1):
                    if want_high:
                        if not (hi[j - k] >= hi[j - k + q] and hi[j - k] > hi[j - k - q]):
                            ok = False
                            break
                    else:
                        if not (lo[j - k] <= lo[j - k + q] and lo[j - k] < lo[j - k - q]):
                            ok = False
                            break
                if ok:
                    if want_high:
                        sw_hi[j] = hi[j - k]
                    else:
                        sw_lo[j] = lo[j - k]
                    break
    return sw_lo, sw_hi


def sma_atr(hi, lo, cl, n=14):
    pc = np.concatenate([[np.nan], cl[:-1]])
    tr = np.nanmax(np.vstack([hi - lo, np.abs(hi - pc), np.abs(lo - pc)]), axis=0)
    out = np.convolve(tr, np.ones(n) / n, mode="full")[: len(tr)]
    out[: n - 1] = np.nan
    return out


def map_closed_to_m1(m1_t_ns, bar_open_ns, bar_ns, vals):
    """Value of the latest bar whose close <= the M1 bar's close."""
    m1_close = m1_t_ns + 60_000_000_000
    bar_close = bar_open_ns + bar_ns
    j = np.searchsorted(bar_close, m1_close, side="right") - 1
    out = np.full(len(m1_t_ns), np.nan)
    ok = j >= 0
    out[ok] = vals[j[ok]]
    return out

"""Weekend study 2026-11-15: runs everything pre-registered in PREREGISTRATION.md.

python research/weekend-study-2026-11-15/study.py   (about 5-10 minutes)
Outputs go to research/weekend-study-2026-11-15/results/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m1engine as M  # noqa: E402
import wdata as W  # noqa: E402
from research.backtest import config as C  # noqa: E402
from research.backtest import engine as E  # noqa: E402

p2, rt = W.p2, W.rt
RES = HERE / "results"
RES.mkdir(exist_ok=True)
ET = "America/New_York"
NS_MIN = 60_000_000_000
OOS0, CUT24, BACK0 = 2012, 2024, 2005
MODE_NAME = {0: "baseline", 1: "X1_ea_trail", 2: "X2_fixed2R", 3: "X3_chandelier"}
REASON = {1: "sl", 2: "tp2", 3: "be", 4: "trail", 5: "fri_close", 6: "eod", 7: "tp_full"}

# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
t0 = time.time()
m1 = W.m1_with_spread()
FR = W.build_frames(m1["profile"])
F1H, F15 = FR["1h"], FR["15m"]
T = m1["t"]
print(f"data loaded {time.time()-t0:.0f}s  M1={len(T):,}", flush=True)

m15b = W.load_ohlc("M15")
m15_open = m15b.index.tz_convert("UTC").asi8 if hasattr(m15b.index, "asi8") else m15b.index.view("i8")
m15_open = pd.DatetimeIndex(m15b.index).tz_convert("UTC").as_unit("ns").asi8
sw_lo, sw_hi = M.m15_trail_levels(m15b["High"].to_numpy(float), m15b["Low"].to_numpy(float))
a15 = M.sma_atr(m15b["High"].to_numpy(float), m15b["Low"].to_numpy(float), m15b["Close"].to_numpy(float))
TR_LO = M.map_closed_to_m1(T, m15_open, 15 * NS_MIN, sw_lo)
TR_HI = M.map_closed_to_m1(T, m15_open, 15 * NS_MIN, sw_hi)
ATR15 = M.map_closed_to_m1(T, m15_open, 15 * NS_MIN, a15)
h1b = W.load_ohlc("H1")
h1_open = pd.DatetimeIndex(h1b.index).tz_convert("UTC").as_unit("ns").asi8
ATRH1 = M.map_closed_to_m1(T, h1_open, 60 * NS_MIN, M.sma_atr(h1b["High"].to_numpy(float), h1b["Low"].to_numpy(float), h1b["Close"].to_numpy(float)))
mins = m1["et_hour"].astype(int) * 60 + m1["et_min"].astype(int)
FRI_FLAT = ((m1["et_wd"] == 4) & (mins >= 16 * 60 + 15)) | (m1["et_wd"] == 5)
NO_FLAT = np.zeros(len(T), dtype=bool)
O, H, L, Cc, SPR = m1["o"], m1["h"], m1["l"], m1["c"], m1["spr"]
print(f"trail arrays ready {time.time()-t0:.0f}s", flush=True)


def ns(idx) -> np.ndarray:
    return pd.DatetimeIndex(idx).tz_convert("UTC").as_unit("ns").asi8


# ---------------------------------------------------------------------------
# candidates
# ---------------------------------------------------------------------------
def frame_candidates(df, fn, mask, bar_min, nfp_filter=False, open_entry=False, tag=""):
    idx_ns = ns(df.index)
    sess = df["session"].astype(str).to_numpy()
    blk = df["news_blackout"].astype(bool).to_numpy() if nfp_filter else np.zeros(len(df), bool)
    out = []
    for i in np.flatnonzero(mask):
        sig = fn(df.iloc[i])
        if sig is None:
            continue
        e = i if open_entry else i + 1
        if e >= len(df) or sess[e] == "break" or blk[e]:
            continue
        out.append(dict(sig_ns=int(idx_ns[i] if open_entry else idx_ns[i] + bar_min * NS_MIN),
                        entry_ns=int(idx_ns[e]), d=int(sig.direction), sl=float(sig.sl),
                        nl=float(sig.next_level) if sig.next_level is not None and np.isfinite(sig.next_level) else np.nan,
                        session_date=df["session_date"].iloc[i], tag=tag))
    return out


def cand_ny(df, bar_min):
    m = (df["lon_first_close_up"] | df["lon_first_close_down"]).to_numpy()
    return frame_candidates(df, lambda r: p2.sig_ny_lon_break(r, "d4h"), m, bar_min, nfp_filter=True)


def cand_fomc():
    return frame_candidates(F1H, lambda r: p2.sig_news(r, "FOMC", "cont"), F1H["fomc_signal"].to_numpy(), 60)


def cand_donch():
    m = ((pd.DatetimeIndex(F1H.index).hour == 18) & F1H["donch_break_up"].fillna(False).astype(bool)).to_numpy()
    return frame_candidates(F1H, lambda r: p2.sig_donchian_at_open(r, "long"), m, 60, open_entry=True)


ASIA_P = [p for p in rt.A_VARIANTS if p["name"] == "A_trend_ma"][0]


def cand_asia(df, bar_min):
    m = (df["asia_first_close_up"] | df["asia_first_close_down"]).to_numpy()
    return frame_candidates(df, lambda r: rt.breakout_signal(r, ASIA_P), m, bar_min)


def cand_event(dates: set, win_bars: int, tag: str):
    """F1-F4: continuation after CPI/NFP on M15. win_bars=4 -> 60 min, 2 -> 30 min."""
    df = F15
    idx = pd.DatetimeIndex(df.index)
    day = idx.normalize()
    hm = idx.hour * 60 + idx.minute
    hi, lo, cl = df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy()
    atr = df["atr_sl"].to_numpy()
    sess = df["session"].astype(str).to_numpy()
    idx_ns = ns(idx)
    pos_of = {}
    for i in np.flatnonzero(day.isin(list(dates)) & (hm >= 8 * 60 + 15) & (hm <= 9 * 60 + 30)):
        pos_of[(day[i], hm[i])] = i
    out = []
    for dt in sorted(dates):
        dts = pd.Timestamp(dt)
        pre = pos_of.get((dts, 8 * 60 + 15))
        last_hm = 8 * 60 + 30 + 15 * (win_bars - 1)
        sig_i = pos_of.get((dts, last_hm))
        win = [pos_of.get((dts, 8 * 60 + 30 + 15 * k)) for k in range(win_bars)]
        if pre is None or sig_i is None or any(w is None for w in win) or sig_i + 1 >= len(df):
            continue
        d = int(np.sign(cl[sig_i] - cl[pre]))
        if d == 0:
            continue
        a = atr[sig_i]
        sl = (min(lo[w] for w in win) - C.SL_BUFFER_ATR * a) if d == 1 else (max(hi[w] for w in win) + C.SL_BUFFER_ATR * a)
        if not p2._sl_ok(cl[sig_i], sl, d, a):
            continue
        if sess[sig_i + 1] == "break":
            continue
        out.append(dict(sig_ns=int(idx_ns[sig_i] + 15 * NS_MIN), entry_ns=int(idx_ns[sig_i + 1]), d=d, sl=float(sl), nl=np.nan,
                        session_date=df["session_date"].iloc[sig_i], tag=tag))
    return out


def cand_pdhl():
    df = F15
    idx = pd.DatetimeIndex(df.index)
    hm = idx.hour * 60 + idx.minute
    cl, hi, lo = df["Close"].to_numpy(), df["High"].to_numpy(), df["Low"].to_numpy()
    ph, pl = df["prior_high"].to_numpy(), df["prior_low"].to_numpy()
    sess_d = df["session_date"].to_numpy()
    atr = df["atr_sl"].to_numpy()
    up = df["trend_up_ma"].astype(bool).to_numpy()
    dn = df["trend_down_ma"].astype(bool).to_numpy()
    blk = df["news_blackout"].astype(bool).to_numpy()
    sname = df["session"].astype(str).to_numpy()
    idx_ns = ns(idx)
    out, last, seen_u, seen_d = [], None, False, False
    for i in range(len(df)):
        if sess_d[i] != last:
            last, seen_u, seen_d = sess_d[i], False, False
        first_u = np.isfinite(ph[i]) and cl[i] > ph[i] and not seen_u
        first_d = np.isfinite(pl[i]) and cl[i] < pl[i] and not seen_d
        if np.isfinite(ph[i]) and cl[i] > ph[i]:
            seen_u = True
        if np.isfinite(pl[i]) and cl[i] < pl[i]:
            seen_d = True
        if not (8 * 60 <= hm[i] < 11 * 60) or blk[i] or i + 1 >= len(df):
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        for d, first, lvl, tr in ((1, first_u, ph[i], up[i]), (-1, first_d, pl[i], dn[i])):
            if not first or not tr or d * (cl[i] - lvl) > 0.5 * a:
                continue
            j0 = max(0, i - 3)
            sl = (lo[j0:i + 1].min() - C.SL_BUFFER_ATR * a) if d == 1 else (hi[j0:i + 1].max() + C.SL_BUFFER_ATR * a)
            if not p2._sl_ok(cl[i], sl, d, a) or sname[i + 1] == "break" or blk[i + 1]:
                continue
            nl = p2._next_level(df.iloc[i], d, cl[i])
            out.append(dict(sig_ns=int(idx_ns[i] + 15 * NS_MIN), entry_ns=int(idx_ns[i + 1]), d=d, sl=float(sl),
                            nl=float(nl) if nl is not None and np.isfinite(nl) else np.nan,
                            session_date=sess_d[i], tag="pdhl"))
    return out


def cand_gap(mode: str):
    df = F1H
    idx = pd.DatetimeIndex(df.index)
    op, cl, lo, hi = df["Open"].to_numpy(), df["Close"].to_numpy(), df["Low"].to_numpy(), df["High"].to_numpy()
    datr, atr = df["d_atr"].to_numpy(), df["atr_sl"].to_numpy()
    idx_ns = ns(idx)
    out = []
    for i in np.flatnonzero((idx.weekday == 6) & (idx.hour == 18)):
        if i == 0 or i + 1 >= len(df) or (idx_ns[i] - idx_ns[i - 1]) < 30 * 3600 * 10**9:
            continue
        fri = cl[i - 1]
        gap = op[i] - fri
        if not np.isfinite(datr[i]) or abs(gap) < max(3.0, 0.25 * datr[i]):
            continue
        filled = lo[i] <= fri if gap > 0 else hi[i] >= fri
        if filled:
            continue
        d = -int(np.sign(gap)) if mode == "fade" else int(np.sign(gap))
        ref = cl[i]
        sl = ref - d * max(abs(gap), 5.0)
        if not p2._sl_ok(ref, sl, d, atr[i]):
            continue
        out.append(dict(sig_ns=int(idx_ns[i] + 60 * NS_MIN), entry_ns=int(idx_ns[i + 1]), d=d, sl=float(sl), nl=np.nan,
                        session_date=df["session_date"].iloc[i], tag=f"gap_{mode}"))
    return out


# ---------------------------------------------------------------------------
# book runner
# ---------------------------------------------------------------------------
def _fri_block(entry_ns: int) -> bool:
    t = pd.Timestamp(entry_ns, tz="UTC").tz_convert(ET)
    return (t.weekday() == 4 and t.hour * 60 + t.minute >= 14 * 60 + 15) or t.weekday() == 5


def simulate_one(c, mode, fri):
    st = int(np.searchsorted(T, c["entry_ns"], side="left"))
    if st >= len(T):
        return None
    r = M.simulate(O, H, L, Cc, SPR, st, c["d"], c["sl"], c["nl"], mode, FRI_FLAT if fri else NO_FLAT,
                   TR_LO, TR_HI, ATR15, ATRH1)
    ex, R, tp1, rc, amb, fill, dist = r
    if rc == M.R_SKIP:
        return None
    return dict(entry_time=pd.Timestamp(T[st], tz="UTC"), exit_time=pd.Timestamp(T[ex], tz="UTC"),
                exit_end_ns=int(T[ex] + NS_MIN), direction=c["d"], entry=round(fill, 3), sl=round(c["sl"], 3),
                sl_dist=round(dist, 3), r=float(R), tp1_hit=bool(tp1), exit_reason=REASON.get(rc, str(rc)),
                m1_ambiguous=int(amb), session_date=str(c["session_date"]), sig_ns=c["sig_ns"], entry_ns=c["entry_ns"])


def run_book(cands, mode=0, fri=False, keep=None) -> pd.DataFrame:
    cands = sorted(cands, key=lambda c: (c["entry_ns"], c["sig_ns"]))
    last_end = -1
    rows = []
    for c in cands:
        if keep is not None and not keep(c):
            continue
        if fri and _fri_block(c["entry_ns"]):
            continue
        if c["sig_ns"] < last_end:
            continue
        tr = simulate_one(c, mode, fri)
        if tr is None:
            continue
        rows.append(tr)
        last_end = tr["exit_end_ns"]
    return pd.DataFrame(rows)


def fixed_entries(book: pd.DataFrame, mode: int) -> pd.DataFrame:
    rows = []
    for _, b in book.iterrows():
        c = dict(entry_ns=int(b["entry_ns"]), sig_ns=int(b["sig_ns"]), d=int(b["direction"]), sl=float(b["sl"]),
                 nl=float(b["nl"]) if "nl" in b and np.isfinite(b["nl"]) else np.nan, session_date=b["session_date"])
        tr = simulate_one(c, mode, False)
        rows.append(tr if tr is not None else {})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def _yr(df):
    return pd.to_datetime(df["entry_time"], utc=True).dt.tz_convert(ET).dt.year


def summ(r: np.ndarray) -> dict:
    r = np.asarray(r, float)
    if len(r) == 0:
        return dict(n=0, win_rate=np.nan, avg_r=np.nan, profit_factor=np.nan, total_r=0.0, max_dd_pct=np.nan)
    gp, gl = r[r > 0].sum(), -r[r < 0].sum()
    eq = np.cumprod(1 + C.RISK_PCT * r)
    dd = (1 - eq / np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]).max()
    return dict(n=int(len(r)), win_rate=round(float((r > 0).mean()), 3), avg_r=round(float(r.mean()), 4),
                profit_factor=round(float(gp / gl), 3) if gl > 0 else np.inf, total_r=round(float(r.sum()), 2),
                max_dd_pct=round(float(dd * 100), 2))


def boot_p(r, seed=7, B=20000) -> float:
    r = np.asarray(r, float)
    if len(r) < 2:
        return 1.0
    rng = np.random.default_rng(seed)
    means = r[rng.integers(0, len(r), size=(B, len(r)))].mean(axis=1)
    return float((means <= 0).mean())


def evaluate(book: pd.DataFrame, name: str, new_idea=False) -> dict:
    if book.empty:
        return dict(variant=name, oos_n=0, adopt=False, adopt_reason="no trades")
    y = _yr(book)
    r = book["r"].to_numpy()
    oos, mid, rec, back = (y >= OOS0), (y >= OOS0) & (y < CUT24), (y >= CUT24), (y >= BACK0) & (y < OOS0)
    so, sm, sr, sb = summ(r[oos]), summ(r[mid]), summ(r[rec]), summ(r[back])
    yt = book[oos].groupby(y[oos])["r"].mean()
    stab = {"oos_years": int(len(yt)), "oos_years_positive": int((yt > 0).sum())}
    ok, why = p2.adopt_decision(so, sm, stab)
    if new_idea and ok and not (sm["avg_r"] > 0):
        ok, why = False, "2012-2023 avgR not > 0"
    out = dict(variant=name)
    for tag, s in (("oos", so), ("mid", sm), ("rec", sr), ("back", sb)):
        for k, v in s.items():
            out[f"{tag}_{k}"] = v
    out.update(green_years=f"{stab['oos_years_positive']}/{stab['oos_years']}", p_boot=round(boot_p(r[oos]), 4),
               m1_ambiguous_trades=int((book["m1_ambiguous"] > 0).sum()), bar_pass=ok, bar_reason=why)
    return out


def holm(pvals: dict, alpha=0.05) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    res, still = {}, True
    for k, (name, p) in enumerate(items):
        thr = alpha / (m - k)
        if still and p <= thr:
            res[name] = (True, thr)
        else:
            still = False
            res[name] = (False, thr)
    return res


def year_rows(book, name):
    if book.empty:
        return []
    y = _yr(book)
    return [dict(variant=name, year=int(k), n=int(len(g)), avg_r=round(float(g.mean()), 4), total_r=round(float(g.sum()), 2))
            for k, g in book.groupby(y)["r"]]


# ---------------------------------------------------------------------------
# A0: old conservative H1 engine on the same broker frame (for the same-bar effect)
# ---------------------------------------------------------------------------
class BrokerEngine(E.Engine):
    def _set(self, row):
        s = row.get("spread_usd")
        if s is not None and np.isfinite(s):
            C.SPREAD = float(s)

    def _try_enter(self, sig, row, t, equity):
        self._set(row)
        return super()._try_enter(sig, row, t, equity)

    def _manage(self, pos, row, t, equity, entry_bar=False):
        self._set(row)
        return super()._manage(pos, row, t, equity, entry_bar=entry_bar)


p2.Engine = BrokerEngine
p2.run_engine = lambda df, fn, **kw: BrokerEngine(df, fn, **kw).run()
rt.run_engine = p2.run_engine


def run_a0():
    df_ad = F1H.copy()
    df_ad["nfp_blackout"] = df_ad["news_blackout"].astype(bool)
    jobs = {
        "A1_ny_lon_brk_d4h": lambda: p2.run_engine(df_ad, lambda r: p2.sig_ny_lon_break(r, "d4h"), nfp_filter=True),
        "A2_fomc_cont": lambda: p2.run_engine(F1H, lambda r: p2.sig_news(r, "FOMC", "cont"), nfp_filter=False),
        "A3_donch20_long": lambda: p2.run_open_entry(F1H, lambda r: p2.sig_donchian_at_open(r, "long"), "donch"),
        "A4_asia_brk_trend": lambda: rt.run_next_open(F1H, ASIA_P),
    }
    out = {}
    for k, job in jobs.items():
        C.SPREAD = 0.25
        trades, _ = job()
        tf = pd.DataFrame([t.to_row() for t in trades])
        tf["entry_time"] = pd.to_datetime(tf["entry_time"], utc=True)
        tf["r"] = tf["r_multiple"].astype(float)
        tf["m1_ambiguous"] = 0
        out[k] = tf
        print(f"A0 {k}: {len(tf)} trades", flush=True)
    C.SPREAD = 0.25
    return out


# ---------------------------------------------------------------------------
def main():
    summary, years, notes = [], [], {}
    # ---------------- Part A ----------------
    CA = {"A1_ny_lon_brk_d4h": cand_ny(F1H, 60), "A2_fomc_cont": cand_fomc(),
          "A3_donch20_long": cand_donch(), "A4_asia_brk_trend": cand_asia(F1H, 60)}
    print(f"candidates built {time.time()-t0:.0f}s", {k: len(v) for k, v in CA.items()}, flush=True)
    A0 = run_a0()
    books = {}
    for k, cands in CA.items():
        b = run_book(cands, 0)
        nl = {c["entry_ns"]: c["nl"] for c in cands}
        b["nl"] = b["entry_ns"].map(nl)
        books[k] = b
        b.drop(columns=["exit_end_ns"]).to_csv(RES / f"trades_{k}_m1.csv", index=False)
        A0[k].to_csv(RES / f"trades_{k}_h1conservative.csv", index=False)
        e1, e0 = evaluate(b, k + " [M1-managed]"), evaluate(A0[k], k + " [H1 conservative]")
        e0["samebar_exits"] = int(A0[k]["exit_reason"].astype(str).str.contains("samebar").sum())
        e0["samebar_share"] = round(e0["samebar_exits"] / max(1, len(A0[k])), 3)
        summary += [dict(part="A", **e0), dict(part="A", **e1)]
        years += year_rows(b, k + " [M1]") + year_rows(A0[k], k + " [H1c]")
        # R1: Friday flatten realism
        bf = run_book(cands, 0, fri=True)
        summary.append(dict(part="R1", **evaluate(bf, k + " [M1 + EA Friday close]")))
        years += year_rows(bf, k + " [M1+Fri]")
        print(f"A {k} done {time.time()-t0:.0f}s", flush=True)

    # ---------------- Family F ----------------
    vol = vol_pct()
    def vkeep(lo=None, hi=None):
        def f(c):
            v = vol.get(c["session_date"], np.nan)
            if not np.isfinite(v):
                return False
            return (lo is None or v >= lo) and (hi is None or v <= hi)
        return f
    cpi = set(pd.to_datetime(pd.read_csv(HERE / "cpi_dates.csv")["cpi_release_et_date"]))
    cal = p2._load_news()
    nfp = set(pd.to_datetime(cal.loc[cal["event"] == "NFP", "ts"], utc=True).dt.tz_convert(ET).dt.tz_localize(None).dt.normalize())
    cpi = {pd.Timestamp(d).tz_localize(ET) for d in cpi}
    nfp = {pd.Timestamp(d).tz_localize(ET) for d in nfp}
    FAM = {
        "F1_cpi_cont_60": lambda: run_book(cand_event(cpi, 4, "cpi60")),
        "F2_cpi_cont_30": lambda: run_book(cand_event(cpi, 2, "cpi30")),
        "F3_nfp_cont_30": lambda: run_book(cand_event(nfp, 2, "nfp30")),
        "F4_nfp_cont_60": lambda: run_book(cand_event(nfp, 4, "nfp60")),
        "F5_pdhl_brk_ny": lambda: run_book(cand_pdhl()),
        "F6_ny_brk_vol_le80": lambda: run_book(CA["A1_ny_lon_brk_d4h"], keep=vkeep(hi=80)),
        "F7_ny_brk_vol_ge20": lambda: run_book(CA["A1_ny_lon_brk_d4h"], keep=vkeep(lo=20)),
        "F8_asia_trend_vol_le80": lambda: run_book(CA["A4_asia_brk_trend"], keep=vkeep(hi=80)),
        "F9_asia_trend_vol_ge20": lambda: run_book(CA["A4_asia_brk_trend"], keep=vkeep(lo=20)),
        "F10_donch_vol_le80": lambda: run_book(CA["A3_donch20_long"], keep=vkeep(hi=80)),
        "F11_gap_fade": lambda: run_book(cand_gap("fade")),
        "F12_gap_go": lambda: run_book(cand_gap("go")),
        "F13_ny_lon_brk_15m": lambda: run_book(cand_ny(F15, 15)),
        "F14_asia_trend_15m": lambda: run_book(cand_asia(F15, 15)),
    }
    fam_rows, pv = [], {}
    for k, job in FAM.items():
        b = job()
        if not b.empty:
            b.drop(columns=["exit_end_ns"]).to_csv(RES / f"trades_{k}.csv", index=False)
        e = evaluate(b, k, new_idea=True)
        pv[k] = e.get("p_boot", 1.0) if e.get("oos_n", 0) else 1.0
        fam_rows.append(e)
        years += year_rows(b, k)
        print(f"F {k}: n={e.get('oos_n')} avgR={e.get('oos_avg_r')} PF={e.get('oos_profit_factor')} p={pv[k]} {e.get('bar_reason')}", flush=True)
    hf = holm(pv)
    for e in fam_rows:
        ok, thr = hf[e["variant"]]
        e["holm_threshold"] = round(thr, 5)
        e["holm_pass"] = ok
        e["adopt"] = bool(e.get("bar_pass")) and ok
        summary.append(dict(part="F", **e))

    # ---------------- Family X ----------------
    xpv, xrows = {}, []
    for k, b in books.items():
        base_r = b["r"].to_numpy()
        y = _yr(b)
        oos = (y >= OOS0).to_numpy()
        for mode in (1, 2, 3):
            alt = fixed_entries(b, mode)
            alt["entry_time"] = b["entry_time"].values
            alt["m1_ambiguous"] = alt["m1_ambiguous"].fillna(0)
            ok_rows = alt["r"].notna().to_numpy()
            dr = (alt["r"].to_numpy() - base_r)[oos & ok_rows]
            name = f"{k}|{MODE_NAME[mode]}"
            p = boot_p(dr)
            xpv[name] = p
            e = evaluate(alt[ok_rows], name)
            e.update(delta_r_oos=round(float(np.mean(dr)), 4), p_delta=round(p, 4))
            xrows.append(e)
            years += year_rows(alt[ok_rows], name)
            alt.to_csv(RES / f"trades_{k}_{MODE_NAME[mode]}.csv", index=False)
        print(f"X {k} done {time.time()-t0:.0f}s", flush=True)
    hx = holm(xpv)
    for e in xrows:
        ok, thr = hx[e["variant"]]
        e["holm_threshold"] = round(thr, 5)
        e["holm_pass"] = ok
        e["adopt"] = bool(e.get("bar_pass")) and ok and e["delta_r_oos"] > 0
        summary.append(dict(part="X", **e))

    pd.DataFrame(summary).to_csv(RES / "summary.csv", index=False)
    pd.DataFrame(years).to_csv(RES / "years.csv", index=False)
    descriptives(books)
    print(f"all done {time.time()-t0:.0f}s", flush=True)


def vol_pct() -> dict:
    s = F1H.groupby("session_date")["d_atr"].first().dropna()
    v = s.to_numpy()
    out = np.full(len(v), np.nan)
    for i in range(251, len(v)):
        w = v[i - 251:i + 1]
        out[i] = 100.0 * (w <= v[i]).mean()
    return dict(zip(s.index, out))


def descriptives(books):
    from scipy import stats
    df = F1H
    y = pd.DatetimeIndex(df.index).year
    d = df[(y >= OOS0) & df["session"].isin(["asia", "london", "ny"])]
    g = d.groupby(["session_date", "session"]).agg(o=("Open", "first"), c=("Close", "last"))
    g["ret_pct"] = 100 * (g["c"] / g["o"] - 1)
    g = g.reset_index()
    g["weekday"] = pd.to_datetime(g["session_date"].astype(str)).dt.day_name()
    g["year"] = pd.to_datetime(g["session_date"].astype(str)).dt.year
    rows = []
    for key, part in list(g.groupby("session")) + [(f"day_{k}", v) for k, v in g.groupby(["session_date"]).agg(ret_pct=("ret_pct", "sum"), weekday=("weekday", "first"), year=("year", "first")).groupby("weekday")]:
        x = part["ret_pct"].to_numpy()
        t, p = stats.ttest_1samp(x, 0.0)
        mid = part[part["year"] < CUT24]["ret_pct"].mean()
        rec = part[part["year"] >= CUT24]["ret_pct"].mean()
        rows.append(dict(bucket=key if isinstance(key, str) else str(key), n=len(x), mean_pct=round(x.mean(), 4),
                         mean_2012_23=round(mid, 4), mean_2024_26=round(rec, 4), t=round(t, 2), p=round(p, 4)))
    D1 = pd.DataFrame(rows)
    h = holm(dict(zip(D1["bucket"], D1["p"])))
    D1["holm_pass"] = D1["bucket"].map(lambda b: h[b][0])
    D1.to_csv(RES / "D1_session_weekday.csv", index=False)
    D2 = []
    for k, b in books.items():
        yy = _yr(b)
        bo = b[yy >= OOS0]
        wd = pd.to_datetime(bo["entry_time"], utc=True).dt.tz_convert(ET).dt.day_name()
        for w, part in bo.groupby(wd):
            s = summ(part["r"].to_numpy())
            D2.append(dict(setup=k, weekday=w, **s))
    pd.DataFrame(D2).to_csv(RES / "D2_setup_weekday.csv", index=False)
    # D3 gap fill
    idx = pd.DatetimeIndex(df.index)
    op, cl, lo, hi = df["Open"].to_numpy(), df["Close"].to_numpy(), df["Low"].to_numpy(), df["High"].to_numpy()
    idx_ns = ns(idx)
    hours = idx.hour
    recs = []
    for i in np.flatnonzero((idx.weekday == 6) & (hours == 18) & (idx.year >= OOS0)):
        if i == 0 or (idx_ns[i] - idx_ns[i - 1]) < 30 * 3600 * 10**9:
            continue
        fri, gap = cl[i - 1], op[i] - cl[i - 1]
        if abs(gap) < max(3.0, 0.25 * (df["d_atr"].iloc[i] or 0)):
            continue
        j_end_sun = i
        while j_end_sun + 1 < len(df) and df["session_date"].iloc[j_end_sun + 1] == df["session_date"].iloc[i]:
            j_end_sun += 1
        def filled_by(j1):
            seg_lo, seg_hi = lo[i:j1 + 1].min(), hi[i:j1 + 1].max()
            return bool(seg_lo <= fri) if gap > 0 else bool(seg_hi >= fri)
        j_ny = i
        while j_ny + 1 < len(df) and not (idx[j_ny + 1].weekday() == 0 and idx[j_ny + 1].hour >= 9) and j_ny - i < 40:
            j_ny += 1
        recs.append(dict(date=str(idx[i].date()), gap=round(gap, 2), filled_18h_bar=filled_by(i),
                         filled_by_session_end=filled_by(j_end_sun), filled_by_mon_0930=filled_by(j_ny)))
    D3 = pd.DataFrame(recs)
    D3.to_csv(RES / "D3_gap_fills.csv", index=False)
    meta = dict(gaps=len(D3), fill_first_hour=float(D3["filled_18h_bar"].mean()) if len(D3) else None,
                fill_session=float(D3["filled_by_session_end"].mean()) if len(D3) else None,
                fill_mon_ny=float(D3["filled_by_mon_0930"].mean()) if len(D3) else None)
    (RES / "D3_gap_summary.json").write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    main()

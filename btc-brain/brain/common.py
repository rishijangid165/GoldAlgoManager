"""Shared helpers for the BTC trader brain. Stdlib only. No secrets."""
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import os
import statistics
import time
import urllib.error
import urllib.request
from bisect import bisect_left
from calendar import timegm
from pathlib import Path

BRAIN_ROOT = Path(__file__).resolve().parent
BTC_BRAIN = BRAIN_ROOT.parent
PAPER_CANDIDATES = [
    Path("/workspace/btc_paper_trades.json"),
    BTC_BRAIN / "paper" / "btc_paper_trades.json",
]
LESSONS_PATH = BRAIN_ROOT / "lessons" / "lessons.json"
EPISODES_DIR = BRAIN_ROOT / "memory" / "episodes"
EPISODES_JSONL = BRAIN_ROOT / "memory" / "episodes.jsonl"
SITUATIONS_GZ = BRAIN_ROOT / "patterns" / "situations.csv.gz"
FNG_CACHE = BRAIN_ROOT / "patterns" / "fng.csv"
MOOD_LOG = BRAIN_ROOT / "mood" / "mood_log.jsonl"
ACCOUNT0 = 1000.0

DELTA_TICKER = "https://api.india.delta.exchange/v2/tickers/BTCUSD"
DELTA_CANDLES = "https://api.india.delta.exchange/v2/history/candles?resolution={res}&symbol=BTCUSD&start={s}&end={e}"
FNG_URL = "https://api.alternative.me/fng/?limit={limit}"

# US macro events in UTC (same list as research/advanced/engine.py).
def _U(y, m, d, h, mi=0):
    return timegm((y, m, d, h, mi, 0))


EVENTS = [
    ("NFP(Sep25, unsure)", _U(2025, 11, 20, 13, 30)),
    ("FOMC", _U(2025, 12, 10, 19)),
    ("NFP(Oct+Nov25, unsure)", _U(2025, 12, 16, 13, 30)),
    ("CPI(Nov25, unsure)", _U(2025, 12, 18, 13, 30)),
    ("NFP", _U(2026, 1, 9, 13, 30)),
    ("CPI", _U(2026, 1, 13, 13, 30)),
    ("FOMC", _U(2026, 1, 28, 19)),
    ("NFP", _U(2026, 2, 11, 13, 30)),
    ("CPI", _U(2026, 2, 13, 13, 30)),
    ("NFP", _U(2026, 3, 6, 13, 30)),
    ("CPI", _U(2026, 3, 11, 12, 30)),
    ("FOMC", _U(2026, 3, 18, 18)),
    ("NFP", _U(2026, 4, 3, 12, 30)),
    ("CPI", _U(2026, 4, 10, 12, 30)),
    ("FOMC", _U(2026, 4, 29, 18)),
    ("NFP", _U(2026, 5, 8, 12, 30)),
    ("CPI", _U(2026, 5, 12, 12, 30)),
    ("NFP", _U(2026, 6, 5, 12, 30)),
    ("CPI", _U(2026, 6, 10, 12, 30)),
    ("FOMC", _U(2026, 6, 17, 18)),
    ("NFP", _U(2026, 7, 2, 12, 30)),
    ("CPI", _U(2026, 7, 14, 12, 30)),
    ("FOMC", _U(2026, 7, 29, 18)),
    ("NFP", _U(2026, 8, 7, 12, 30)),
    ("CPI", _U(2026, 8, 12, 12, 30)),
    ("NFP", _U(2026, 9, 4, 12, 30)),
    ("CPI", _U(2026, 9, 11, 12, 30)),
    ("FOMC", _U(2026, 9, 16, 18)),
    ("NFP", _U(2026, 10, 2, 12, 30)),
    ("CPI", _U(2026, 10, 14, 12, 30)),
    ("FOMC", _U(2026, 10, 28, 18)),
    ("NFP", _U(2026, 11, 6, 13, 30)),
    ("CPI", _U(2026, 11, 10, 13, 30)),
]
EVENT_TIMES = sorted(t for _, t in EVENTS)


def ist_fmt(t, fmt="%Y-%m-%d %H:%M"):
    return time.strftime(fmt, time.gmtime(int(t) + 19800))


def now_epoch():
    return time.time()


def now_ist(fmt="%Y-%m-%d %H:%M IST"):
    return ist_fmt(now_epoch(), fmt if "%IST" in fmt or fmt.endswith("IST") else fmt)


def near_event(t, win=7200):
    i = bisect_left(EVENT_TIMES, t - win)
    return i < len(EVENT_TIMES) and EVENT_TIMES[i] <= t + win


def event_name_near(t, win=7200):
    i = bisect_left(EVENT_TIMES, t - win)
    if i < len(EVENT_TIMES) and EVENT_TIMES[i] <= t + win:
        # find label
        et = EVENT_TIMES[i]
        for name, ts in EVENTS:
            if ts == et:
                return name
    return None


def load_candle_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "t": int(float(r["time"])),
                "o": float(r["open"]),
                "h": float(r["high"]),
                "l": float(r["low"]),
                "c": float(r["close"]),
                "v": float(r["volume"]),
            })
    rows.sort(key=lambda x: x["t"])
    return rows


def ema(xs, n):
    k = 2 / (n + 1)
    out = [None] * len(xs)
    e = None
    for i, x in enumerate(xs):
        e = x if e is None else x * k + e * (1 - k)
        if i >= n - 1:
            out[i] = e
    return out


def atr(bars, n=14):
    out = [None] * len(bars)
    a = None
    for i, b in enumerate(bars):
        if i == 0:
            tr = b["h"] - b["l"]
        else:
            prev = bars[i - 1]["c"]
            tr = max(b["h"] - b["l"], abs(b["h"] - prev), abs(b["l"] - prev))
        if i < n:
            a = (a or 0) + tr / n
        else:
            a = (a * (n - 1) + tr) / n
        if i >= n - 1:
            out[i] = a
    return out


def adx(bars, n=14):
    out = [None] * len(bars)
    trs, pdm, ndm = [], [], []
    for i in range(1, len(bars)):
        up = bars[i]["h"] - bars[i - 1]["h"]
        dn = bars[i - 1]["l"] - bars[i]["l"]
        pdm.append(up if up > dn and up > 0 else 0)
        ndm.append(dn if dn > up and dn > 0 else 0)
        trs.append(max(bars[i]["h"] - bars[i]["l"], abs(bars[i]["h"] - bars[i - 1]["c"]), abs(bars[i]["l"] - bars[i - 1]["c"])))
    if len(trs) < n:
        return out
    tr_s = sum(trs[:n])
    p_s = sum(pdm[:n])
    n_s = sum(ndm[:n])
    dxs = []
    a = None
    for k in range(n, len(trs) + 1):
        if k > n:
            tr_s = tr_s - tr_s / n + trs[k - 1]
            p_s = p_s - p_s / n + pdm[k - 1]
            n_s = n_s - n_s / n + ndm[k - 1]
        pdi = 100 * p_s / tr_s if tr_s else 0
        ndi = 100 * n_s / tr_s if tr_s else 0
        dx = 100 * abs(pdi - ndi) / (pdi + ndi) if (pdi + ndi) else 0
        dxs.append(dx)
        if len(dxs) == n:
            a = sum(dxs) / n
        elif len(dxs) > n:
            a = (a * (n - 1) + dx) / n
        out[k] = a
    return out


def map_h1_to_h4(h1, h4):
    """Index of last 4H candle completed by the time this 1H candle completes."""
    m = []
    j = -1
    for b in h1:
        while j + 1 < len(h4) and h4[j + 1]["t"] + 14400 <= b["t"] + 3600:
            j += 1
        m.append(j)
    return m


def trend_4h(h4, e4, j4):
    if j4 < 3 or e4[j4] is None or e4[j4 - 3] is None:
        return None
    c, e = h4[j4]["c"], e4[j4]
    s = e - e4[j4 - 3]
    if c > e and s > 0:
        return "UP"
    if c < e and s < 0:
        return "DOWN"
    return None


def compute_series(h1, h4):
    a1 = atr(h1)
    e4 = ema([x["c"] for x in h4], 50)
    ad4 = adx(h4)
    vavg = [None] * len(h1)
    for i in range(20, len(h1)):
        vavg[i] = sum(x["v"] for x in h1[i - 20:i]) / 20
    m = map_h1_to_h4(h1, h4)
    atr_pct = [None] * len(h1)
    for i in range(len(h1)):
        if a1[i] is not None and i >= 720 + 14:
            prev = sorted(a1[i - 720:i])
            atr_pct[i] = bisect_left(prev, a1[i]) / 720
    return dict(a1=a1, e4=e4, ad4=ad4, vavg=vavg, m=m, atr_pct=atr_pct)


def regime_at(h1, h4, series, j):
    """Regime label as in research/advanced/report.md Phase 2. Past data only."""
    if series["atr_pct"][j] is None or series["vavg"][j] is None:
        return None
    dec = h1[j]["t"] + 3600
    if near_event(dec, 7200) or series["atr_pct"][j] >= 0.90 or h1[j]["v"] > 3 * series["vavg"][j]:
        return "HIGHVOL_NEWS"
    j4 = series["m"][j]
    tr = trend_4h(h4, series["e4"], j4) if j4 >= 0 else None
    ad = (series["ad4"][j4] or 0) if j4 >= 0 else 0
    if tr == "UP" and ad >= 20:
        return "TREND_UP"
    if tr == "DOWN" and ad >= 20:
        return "TREND_DOWN"
    return "SIDEWAYS"


def bar_features(h1, h4, series, j):
    """Feature dict for 1H bar j using only past/current completed bar. None if not ready."""
    if j < 24:
        return None
    reg = regime_at(h1, h4, series, j)
    if reg is None:
        return None
    a = series["a1"][j]
    j4 = series["m"][j]
    if a is None or a <= 0 or j4 < 0 or series["e4"][j4] is None or series["vavg"][j] in (None, 0):
        return None
    b = h1[j]
    prev = h1[j - 24]
    if prev["c"] == 0:
        return None
    rng = b["h"] - b["l"]
    body = abs(b["c"] - b["o"])
    body_frac = (body / rng) if rng > 0 else 0.0
    dec = b["t"] + 3600
    tm = time.gmtime(b["t"] + 19800)
    return {
        "t": b["t"],
        "t_close": dec,
        "ist": ist_fmt(b["t"]),
        "date_ist": ist_fmt(b["t"], "%Y-%m-%d"),
        "hour_ist": tm.tm_hour,
        "dow": tm.tm_wday,  # Mon=0
        "regime": reg,
        "close": b["c"],
        "ret_24h": (b["c"] - prev["c"]) / prev["c"],
        "dist_ema50_atr": (b["c"] - series["e4"][j4]) / a,
        "atr_pct": series["atr_pct"][j],
        "vol_ratio": b["v"] / series["vavg"][j],
        "body_frac": body_frac,
        "doji": body_frac < 0.20,
        "news_window": near_event(dec, 7200),
        "news_name": event_name_near(dec, 7200),
    }


def forward_outcomes(h1, j, n=24):
    if j + n >= len(h1):
        return None
    c0 = h1[j]["c"]
    if c0 == 0:
        return None
    # next 4h: bar j+4 close (4 hours after this 1H close)
    if j + 4 >= len(h1):
        return None
    highs = [h1[k]["h"] for k in range(j + 1, j + n + 1)]
    lows = [h1[k]["l"] for k in range(j + 1, j + n + 1)]
    return {
        "fwd_ret_4h": (h1[j + 4]["c"] - c0) / c0,
        "fwd_ret_24h": (h1[j + n]["c"] - c0) / c0,
        "fwd_max_up_24h": (max(highs) - c0) / c0,
        "fwd_max_down_24h": (c0 - min(lows)) / c0,
    }


# ---- HTTP (no secrets) ----
def http_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "btc-brain/1.0 (research; no-auth)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_ticker():
    try:
        d = http_json(DELTA_TICKER, timeout=15)
        r = d.get("result") or {}
        px = r.get("close") or r.get("mark_price") or r.get("spot_price")
        ts = r.get("timestamp")
        t = int(ts) // 1_000_000 if ts else int(now_epoch())
        return {"price": float(px), "t": t}
    except Exception:
        return None


def fetch_delta_candles(resolution, start, end, bar_sec):
    rows = {}
    s = int(start)
    end = int(end)
    while s < end:
        e = min(end, s + bar_sec * 1000)
        last_err = None
        payload = None
        for _ in range(3):
            try:
                payload = http_json(DELTA_CANDLES.format(res=resolution, s=s, e=e), timeout=30)
                break
            except Exception as ex:
                last_err = ex
                time.sleep(1.2)
        if payload is None:
            raise RuntimeError(f"delta candles failed: {last_err}")
        for c in payload.get("result") or []:
            rows[int(c["time"])] = c
        s = e
        time.sleep(0.15)
    now = int(now_epoch())
    out = []
    for t in sorted(rows):
        if t + bar_sec <= now:  # completed only
            c = rows[t]
            out.append({
                "t": t,
                "o": float(c["open"]),
                "h": float(c["high"]),
                "l": float(c["low"]),
                "c": float(c["close"]),
                "v": float(c["volume"]),
            })
    return out


def fetch_live_bars(days_1h=50, days_4h=40):
    tick = fetch_ticker()
    end = tick["t"] if tick else int(now_epoch())
    h1 = fetch_delta_candles("1h", end - days_1h * 86400, end, 3600)
    h4 = fetch_delta_candles("4h", end - days_4h * 86400, end, 14400)
    return h1, h4, tick


def live_features():
    """Features of the last completed 1H candle, or None on failure."""
    try:
        h1, h4, tick = fetch_live_bars()
    except Exception:
        return None, None, "data nahi hai (Delta candles fetch fail)"
    if len(h1) < 800 or len(h4) < 80:
        return None, tick, "data nahi hai (not enough live candles for indicators)"
    series = compute_series(h1, h4)
    feat = bar_features(h1, h4, series, len(h1) - 1)
    if feat is None:
        return None, tick, "data nahi hai (indicators not ready on last 1H)"
    return feat, tick, None


# ---- Fear & Greed ----
def fetch_fng(limit=0):
    """List of {t, date, value, cls} or None."""
    try:
        d = http_json(FNG_URL.format(limit=int(limit)), timeout=25)
        out = []
        for x in d.get("data") or []:
            t = int(x["timestamp"])
            out.append({
                "t": t,
                "date": time.strftime("%Y-%m-%d", time.gmtime(t)),  # UTC date of the F&G day
                "value": int(float(x["value"])),
                "cls": x.get("value_classification") or "",
            })
        out.sort(key=lambda r: r["t"])
        return out
    except Exception:
        return None


def save_fng_cache(rows):
    FNG_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(FNG_CACHE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["t", "date", "value", "cls"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def load_fng_cache():
    if not FNG_CACHE.exists():
        return None
    rows = []
    with open(FNG_CACHE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"t": int(r["t"]), "date": r["date"], "value": int(r["value"]), "cls": r["cls"]})
    return rows or None


def fng_on_date(fng_rows, date_str):
    """Join by UTC date string YYYY-MM-DD. None if missing."""
    if not fng_rows:
        return None
    by = {r["date"]: r for r in fng_rows}
    return by.get(date_str)


def fng_latest(fng_rows=None):
    live = fetch_fng(limit=2)
    if live:
        return live[-1]
    if fng_rows:
        return fng_rows[-1]
    cached = load_fng_cache()
    if cached:
        return cached[-1]
    return None


# ---- lessons ----
def strength(fr, ag):
    return (fr + 1) / (fr + ag + 2)


def lesson_status(fr, ag):
    obs = fr + ag
    s = strength(fr, ag)
    if obs < 3:
        return "weak/untested"
    if obs >= 5 and s < 0.4:
        return "forgotten"
    if s >= 0.4:
        return "active"
    return "weak"


def recompute_lesson(L):
    fr = int(L.get("evidence_for") or 0)
    ag = int(L.get("evidence_against") or 0)
    L["evidence_for"] = fr
    L["evidence_against"] = ag
    L["strength"] = round(strength(fr, ag), 4)
    L["status"] = lesson_status(fr, ag)
    L["observations"] = fr + ag
    return L


def load_lessons():
    with open(LESSONS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    lessons = data["lessons"] if isinstance(data, dict) and "lessons" in data else data
    for L in lessons:
        recompute_lesson(L)
    return lessons


def save_lessons(lessons):
    for L in lessons:
        recompute_lesson(L)
    LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_ist": ist_fmt(now_epoch(), "%Y-%m-%d %H:%M IST"),
        "strength_rule": "Laplace (for+1)/(for+against+2). obs<3 => weak/untested; obs>=5 and strength<0.4 => forgotten; else active if strength>=0.4 else weak. Lessons never become trading rules automatically.",
        "lessons": lessons,
    }
    with open(LESSONS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def parse_condition_tags(cond):
    if not cond:
        return []
    if isinstance(cond, list):
        return [str(x).strip() for x in cond if str(x).strip()]
    return [t.strip() for t in str(cond).split(",") if t.strip()]


def trade_tags(feat, side=None, stop_distance=None, risk_pct=1.0):
    tags = set()
    if feat:
        tags.add(f"regime={feat['regime']}")
        if feat.get("doji"):
            tags.add("entry_candle=doji")
        if feat.get("news_window"):
            tags.add("news_window")
        dist = feat.get("dist_ema50_atr")
        if dist is not None and dist > 5:
            tags.add("late_entry_atr>5")
        if dist is not None and dist < -5:
            tags.add("late_short_atr>5")
    if side:
        tags.add(f"side={side.lower()}")
        if side.lower() in ("long", "buy"):
            tags.add("side=long")
        if side.lower() in ("short", "sell"):
            tags.add("side=short")
    tags.add("timeframe=1h")
    if stop_distance is not None and risk_pct and (ACCOUNT0 * (risk_pct / 100) / stop_distance) < 0.01:
        tags.add("wide_stop_lot_block")
        tags.add("stop_distance>1000")
    elif stop_distance is not None and stop_distance > 1000:
        tags.add("stop_distance>1000")
    return tags


def lesson_applies(L, tags):
    if L.get("auto_update") is False:
        return False
    need = parse_condition_tags(L.get("condition"))
    if not need:
        return False  # empty condition = standing meta lesson, no auto update from a single trade
    tags = set(tags)
    for n in need:
        if n.startswith("late_entry_atr>5"):
            if "late_entry_atr>5" not in tags:
                return False
            continue
        if n not in tags:
            return False
    return True


def show_lesson_for_situation(L, tags):
    """Relevant to display: applies by tags, or standing (empty condition) active/meta lessons."""
    need = parse_condition_tags(L.get("condition"))
    if not need:
        return L.get("status") in ("active", "weak", "weak/untested")
    return lesson_applies({**L, "auto_update": True}, tags) and L.get("status") != "forgotten"


def apply_evidence(lessons, episode_id, tags, won, source="paper"):
    """for = lesson predicted correctly. Lessons with predicts=loss: win => against, loss => for."""
    touched = []
    for L in lessons:
        if not lesson_applies(L, tags):
            continue
        applied = L.setdefault("applied_episodes", [])
        if episode_id in applied:
            continue
        predicts = (L.get("predicts") or "loss").lower()
        if predicts in ("loss", "negative", "skip", "danger"):
            correct = (not won)
        elif predicts in ("win", "positive"):
            correct = bool(won)
        else:
            continue
        if correct:
            L["evidence_for"] = int(L.get("evidence_for") or 0) + 1
        else:
            L["evidence_against"] = int(L.get("evidence_against") or 0) + 1
        applied.append(episode_id)
        recompute_lesson(L)
        touched.append((L["id"], "for" if correct else "against", L["strength"], L["status"]))
    return touched


# ---- paper trades / equity ----
def load_paper_trades():
    for p in PAPER_CANDIDATES:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return data, p
    return [], None


def paper_stats(trades=None):
    if trades is None:
        trades, _ = load_paper_trades()
    closed = []
    open_n = 0
    for t in trades:
        if t.get("status") == "closed":
            closed.append(t)
        elif t.get("status") == "open" or (t.get("qty_open_btc") or 0) > 0:
            open_n += 1
    def closed_key(t):
        return t.get("closed") or t.get("opened") or ""
    closed.sort(key=closed_key)
    equity = ACCOUNT0
    peak = ACCOUNT0
    max_dd = 0.0
    curve = []
    for t in closed:
        pnl = float(t.get("realized_pnl_usdt") or 0)
        equity += pnl
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        curve.append((t.get("id"), equity, dd, pnl))
    streak = 0
    for t in reversed(closed):
        pnl = float(t.get("realized_pnl_usdt") or 0)
        if pnl < 0:
            streak += 1
        else:
            break
    return {
        "n_closed": len(closed),
        "n_open": open_n,
        "equity": round(equity, 2),
        "peak": round(peak, 2),
        "pnl": round(equity - ACCOUNT0, 2),
        "max_dd": round(max_dd, 2),
        "max_dd_pct": round(100 * max_dd / ACCOUNT0, 2),
        "current_dd": round(peak - equity, 2),
        "loss_streak": streak,
        "start": ACCOUNT0,
    }


def parse_ist_to_epoch(s):
    """Parse strings like '2026-11-17 15:41 IST' or '2026-11-19 ~21:45 IST' to epoch seconds."""
    if not s:
        return None
    raw = str(s).replace("~", "").replace("IST", "").strip()
    raw = raw.split("(")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            t = time.strptime(raw, fmt)
            # that struct was clock-IST; convert to UTC epoch
            return timegm(t) - 19800
        except ValueError:
            continue
    return None


def get_trade(trades, trade_id):
    for t in trades:
        if int(t.get("id")) == int(trade_id):
            return t
    return None


def side_of(trade):
    s = (trade.get("side") or "").lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return s or "unknown"


# ---- situations ----
SIT_FIELDS = [
    "t", "ist", "date_ist", "hour_ist", "dow", "regime",
    "ret_24h", "dist_ema50_atr", "atr_pct", "vol_ratio",
    "fng", "fng_class",
    "fwd_ret_4h", "fwd_ret_24h", "fwd_max_up_24h", "fwd_max_down_24h",
    "close",
]


def load_situations():
    if not SITUATIONS_GZ.exists():
        return []
    with gzip.open(SITUATIONS_GZ, "rt", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    def num(r, k):
        v = r.get(k, "")
        if v in ("", None, "data nahi hai"):
            return None
        try:
            if k in ("t", "hour_ist", "dow", "fng"):
                return int(float(v))
            return float(v)
        except ValueError:
            return None
    out = []
    for r in rows:
        item = {k: num(r, k) if k not in ("ist", "date_ist", "regime", "fng_class") else r.get(k, "") for k in SIT_FIELDS}
        out.append(item)
    return out


def similar_to(feat, situations, k=10):
    """Return (k nearest rows, meta). Normalized Euclidean distance. History, not a prediction."""
    if not feat or not situations:
        return [], {"n_library": len(situations or []), "n_used": 0, "k": 0}
    numeric = ["ret_24h", "dist_ema50_atr", "atr_pct", "vol_ratio"]
    use_fng = feat.get("fng") is not None
    if use_fng:
        numeric = numeric + ["fng"]
    # stats from library rows that have all numeric fields
    cols = {n: [] for n in numeric}
    usable = []
    for r in situations:
        if r.get("fwd_ret_24h") is None:
            continue
        ok = True
        for n in numeric:
            if r.get(n) is None:
                ok = False
                break
        if not ok:
            continue
        usable.append(r)
        for n in numeric:
            cols[n].append(r[n])
    if len(usable) < 5:
        return [], {"n_library": len(situations), "n_used": len(usable), "k": 0}
    stats = {}
    for n in numeric:
        mu = sum(cols[n]) / len(cols[n])
        var = sum((x - mu) ** 2 for x in cols[n]) / len(cols[n])
        sd = math.sqrt(var) if var > 0 else 1.0
        stats[n] = (mu, sd if sd > 0 else 1.0)

    def z(row, n):
        mu, sd = stats[n]
        return (row[n] - mu) / sd

    fq = {n: z(feat, n) if feat.get(n) is not None else 0.0 for n in numeric}

    def dist(r):
        s = 0.0
        for n in numeric:
            d = z(r, n) - fq[n]
            s += d * d
        # regime mismatch is a large, clear gap
        if r.get("regime") != feat.get("regime"):
            s += 2.0 * 2.0
        # circular hour (0-23) and dow (0-6), already roughly 0-1
        dh = min(abs((r.get("hour_ist") or 0) - (feat.get("hour_ist") or 0)), 24 - abs((r.get("hour_ist") or 0) - (feat.get("hour_ist") or 0))) / 12.0
        dd = min(abs((r.get("dow") or 0) - (feat.get("dow") or 0)), 7 - abs((r.get("dow") or 0) - (feat.get("dow") or 0))) / 3.5
        s += dh * dh + dd * dd
        return math.sqrt(s)

    scored = [(dist(r), r) for r in usable]
    scored.sort(key=lambda x: x[0])
    top = scored[:k]
    return top, {"n_library": len(situations), "n_used": len(usable), "k": len(top), "used_fng": use_fng}


def summarize_similar(top, meta):
    lines = []
    n = len(top)
    if n == 0:
        lines.append("Similar past situations: data nahi hai (pattern library empty or too small).")
        lines.append("Ye history hai, prediction nahi.")
        return lines
    rets = [r["fwd_ret_24h"] for _, r in top]
    ups = sum(1 for x in rets if x > 0)
    downs = [r["fwd_max_down_24h"] for _, r in top]
    ups_m = [r["fwd_max_up_24h"] for _, r in top]
    med = statistics.median(rets)
    med_down = statistics.median(downs)
    med_up = statistics.median(ups_m)
    lines.append(
        f"Similar past situations: {n} nearest of {meta['n_used']} usable "
        f"(library {meta['n_library']} 1H bars). Ye HISTORY hai, prediction nahi."
    )
    lines.append(
        f"  Next 24h in those {n}: median return {med*100:+.2f}%, "
        f"{ups}/{n} finished up ({100*ups/n:.0f}%). "
        f"Typical max adverse (median max-down) {med_down*100:.2f}%, median max-up {med_up*100:.2f}%."
    )
    # 3 examples
    for i, (d, r) in enumerate(top[:3], 1):
        lines.append(
            f"  e.g.{i} {r.get('ist')} {r.get('regime')} close={r.get('close'):.0f} "
            f"dist={r.get('dist_ema50_atr'):+.2f}ATR 24h={r['fwd_ret_24h']*100:+.2f}%  d={d:.2f}"
        )
    return lines


def local_candle_paths():
    """Prefer uncompressed training files, else gunzipped copies in this repo."""
    h1 = Path("/workspace/btc-training/advanced/delta_1h.csv")
    h4 = Path("/workspace/btc-training/advanced/delta_4h.csv")
    if h1.exists() and h4.exists():
        return h1, h4
    # fallback: temporary decompress is the caller's job; return gz paths as None here
    return None, None

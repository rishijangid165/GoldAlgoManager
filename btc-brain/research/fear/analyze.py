#!/usr/bin/env python3
"""Extreme-fear buy study. No lookahead: enter at the next daily close after the F&G signal.

Sources: Alternative.me Fear & Greed (brain/patterns/fng.csv), Binance BTCUSDT 1d.
Stdlib only.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAIN = HERE.parents[1]  # btc-brain
FNG_PATH = BRAIN / "brain" / "patterns" / "fng.csv"
PRICE_PATH = HERE / "btc_daily.csv"
DELTA_PATHS = [
    Path("/workspace/btc-training/advanced/delta_1d.csv"),
    BRAIN / "data" / "advanced" / "delta_1d.csv.gz",
]
SPOT_RT = 0.002  # 0.2% round trip
XM_SPREAD = 40.0  # $ per BTC, round trip
XM_SWAP = 35.0  # $ per BTC per night, long
STOP_PCT = 0.15
HORIZONS = (7, 30, 90)
THRESHOLDS = (10, 20, 25)
GREED = 75


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_prices():
    rows = []
    with open(PRICE_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "date": parse_date(r["date"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
            })
    rows.sort(key=lambda x: x["date"])
    return rows


def load_fng():
    rows = []
    with open(FNG_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "date": parse_date(r["date"]),
                "value": int(r["value"]),
                "cls": r["cls"],
                "t": int(r["t"]),
            })
    rows.sort(key=lambda x: x["date"])
    return rows


def spot_check_delta(prices):
    import gzip
    delta = None
    for p in DELTA_PATHS:
        if not p.exists():
            continue
        opener = gzip.open if p.suffix == ".gz" else open
        with opener(p, "rt", encoding="utf-8") as f:
            delta = list(csv.DictReader(f))
        break
    if not delta:
        return {"status": "data nahi hai (no Delta 1d file)"}
    by = {x["date"]: x for x in prices}
    diffs = []
    missing = 0
    for r in delta:
        d = datetime.fromtimestamp(int(r["time"]), tz=__import__('datetime').timezone.utc).date()
        if d not in by:
            missing += 1
            continue
        bc = by[d]["close"]
        dc = float(r["close"])
        diffs.append(abs(dc - bc) / bc * 100)
    diffs.sort()
    n = len(diffs)
    return {
        "status": "ok",
        "overlap_days": n,
        "missing_on_binance": missing,
        "close_abs_pct_median": diffs[n // 2] if n else None,
        "close_abs_pct_mean": sum(diffs) / n if n else None,
        "close_abs_pct_p99": diffs[int(0.99 * (n - 1))] if n else None,
        "close_abs_pct_max": diffs[-1] if n else None,
    }


def build_series(prices, fng):
    fng_by = {r["date"]: r for r in fng}
    # forward-fill F&G for weekly DCA / SMA days only; signals use observed values
    filled = {}
    last = None
    if not prices:
        return []
    d = prices[0]["date"]
    end = prices[-1]["date"]
    cursor = {r["date"]: r for r in prices}
    while d <= end:
        if d in fng_by:
            last = fng_by[d]
        if last is not None:
            filled[d] = last["value"]
        d += timedelta(days=1)
    out = []
    closes = []
    for i, p in enumerate(prices):
        closes.append(p["close"])
        sma = None
        if i >= 19:
            sma = sum(closes[i - 19:i + 1]) / 20
        obs = fng_by.get(p["date"])
        out.append({
            **p,
            "i": i,
            "fng": obs["value"] if obs else None,
            "fng_cls": obs["cls"] if obs else None,
            "fng_filled": filled.get(p["date"]),
            "sma20": sma,
        })
    return out


def ret(a, b):
    if a is None or b is None or a == 0:
        return None
    return b / a - 1


def mae_from_entry(series, entry_i, n):
    """Max adverse excursion using lows of the next n days after entry (entry is a close)."""
    px = series[entry_i]["close"]
    end = entry_i + n
    if end >= len(series) or px <= 0:
        return None
    lows = [series[j]["low"] for j in range(entry_i + 1, end + 1)]
    return min(lows) / px - 1


def mfe_from_entry(series, entry_i, n):
    px = series[entry_i]["close"]
    end = entry_i + n
    if end >= len(series) or px <= 0:
        return None
    highs = [series[j]["high"] for j in range(entry_i + 1, end + 1)]
    return max(highs) / px - 1


def summarize(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {}
    pos = sum(1 for x in xs if x > 0)
    return {
        "n": len(xs),
        "mean": statistics.mean(xs),
        "median": statistics.median(xs),
        "pct_pos": pos / len(xs),
        "worst": min(xs),
        "best": max(xs),
        "stdev": statistics.pstdev(xs) if len(xs) > 1 else 0.0,
    }


def year_return(series, year):
    days = [r for r in series if r["date"].year == year]
    if len(days) < 2:
        return None
    return days[-1]["close"] / days[0]["close"] - 1


def classify_years(series):
    years = sorted({r["date"].year for r in series})
    out = {}
    for y in years:
        r = year_return(series, y)
        if r is None:
            label = "unknown"
        elif r <= -0.30:
            label = "bear"
        elif r >= 0.30:
            label = "bull"
        else:
            label = "mixed"
        # conventional labels if close
        if y in (2018, 2022):
            label = "bear"
        out[y] = {"return": r, "label": label}
    return out


def fear_episodes(series, thresh=20):
    """Independent contiguous episodes of observed F&G <= thresh."""
    eps = []
    cur = None
    for r in series:
        if r["fng"] is None:
            continue
        if r["fng"] <= thresh:
            if cur is None:
                cur = {"start": r["date"], "start_i": r["i"], "min_fng": r["fng"], "min_date": r["date"], "days": 1, "end": r["date"], "end_i": r["i"]}
            else:
                cur["end"] = r["date"]
                cur["end_i"] = r["i"]
                cur["days"] += 1
                if r["fng"] < cur["min_fng"]:
                    cur["min_fng"] = r["fng"]
                    cur["min_date"] = r["date"]
        else:
            if cur is not None:
                eps.append(cur)
                cur = None
    if cur is not None:
        eps.append(cur)
    return eps


def event_rows(series, pred, horizon, nonoverlap=False):
    """pred(row) -> True for a signal on that date. Enter next close. Forward `horizon` days."""
    rows = []
    next_ok = 0
    n = len(series)
    for i, r in enumerate(series):
        if i < next_ok:
            continue
        if r["fng"] is None:
            continue
        if not pred(r):
            continue
        entry_i = i + 1
        exit_i = entry_i + horizon
        if exit_i >= n:
            continue
        entry = series[entry_i]["close"]
        exitp = series[exit_i]["close"]
        r_ = ret(entry, exitp)
        mae = mae_from_entry(series, entry_i, horizon)
        mfe = mfe_from_entry(series, entry_i, horizon)
        rows.append({
            "signal_date": r["date"].isoformat(),
            "entry_date": series[entry_i]["date"].isoformat(),
            "exit_date": series[exit_i]["date"].isoformat(),
            "fng": r["fng"],
            "entry": entry,
            "exit": exitp,
            "ret": r_,
            "mae": mae,
            "mfe": mfe,
            "year": r["date"].year,
            "horizon": horizon,
        })
        if nonoverlap:
            # ignore signals for `horizon` days after this signal date
            # signal at i, skip until date >= signal + horizon, i.e. index i+horizon
            next_ok = i + horizon
    return rows


def pack_event(label, rows):
    rets = [r["ret"] for r in rows]
    maes = [r["mae"] for r in rows]
    s = summarize(rets)
    m = summarize(maes)
    s["mae_mean"] = m.get("mean")
    s["mae_median"] = m.get("median")
    s["mae_worst"] = m.get("worst")  # most negative
    s["label"] = label
    s["n_events"] = len(rows)
    return s


def apply_costs_return(gross_ret, entry_price, nights, cost_model):
    """Convert a gross price return to a net return."""
    if cost_model == "none":
        return gross_ret
    if cost_model == "spot":
        # buy at entry*(1+0.001), sell at exit*(1-0.001)
        exitp = entry_price * (1 + gross_ret)
        buy = entry_price * (1 + SPOT_RT / 2)
        sell = exitp * (1 - SPOT_RT / 2)
        return sell / buy - 1
    if cost_model == "xm":
        exitp = entry_price * (1 + gross_ret)
        # $20 each way from $40 RT spread, plus swap per night
        buy = entry_price + XM_SPREAD / 2
        sell = exitp - XM_SPREAD / 2
        swap = XM_SWAP * nights
        pnl = (sell - buy) - swap
        return pnl / entry_price
    raise ValueError(cost_model)


def run_hold_strategy(series, thresh, horizon, cost_model="spot"):
    """One position at a time: F&G <= thresh, enter next close, exit after horizon days."""
    trades = []
    n = len(series)
    i = 0
    while i < n:
        r = series[i]
        if r["fng"] is not None and r["fng"] <= thresh:
            entry_i = i + 1
            exit_i = entry_i + horizon
            if exit_i >= n:
                break
            entry = series[entry_i]["close"]
            exitp = series[exit_i]["close"]
            nights = horizon  # daily bars, one night per day held
            gross = ret(entry, exitp)
            net = apply_costs_return(gross, entry, nights, cost_model)
            mae = mae_from_entry(series, entry_i, horizon)
            trades.append({
                "signal_date": r["date"].isoformat(),
                "entry_date": series[entry_i]["date"].isoformat(),
                "exit_date": series[exit_i]["date"].isoformat(),
                "fng": r["fng"],
                "entry": entry,
                "exit": exitp,
                "gross": gross,
                "net": net,
                "mae": mae,
                "nights": nights,
                "year": r["date"].year,
                "stopped": False,
            })
            i = exit_i  # next scan after exit (flat, can re-enter same day if signal)
            continue
        i += 1
    return trades


def run_confirmed(series, fear_thresh=20, confirm_fng=25, horizon=90, stop=STOP_PCT, cost_model="spot"):
    """After F&G <= fear_thresh, wait for F&G > confirm_fng OR close > SMA20; enter next close.
    One trade per fear episode. Exit at horizon or -stop using daily low (fill at stop).
    """
    trades = []
    n = len(series)
    i = 0
    while i < n:
        r = series[i]
        if r["fng"] is None or r["fng"] > fear_thresh:
            i += 1
            continue
        # episode starts at i; look for confirmation on i or later, until F&G has been
        # above confirm_fng for a stretch after leaving fear, or we confirm.
        flagged = True
        j = i
        confirmed = None
        while j < n and flagged:
            rj = series[j]
            fng = rj["fng"]
            sma = rj["sma20"]
            close = rj["close"]
            fng_ok = fng is not None and fng > confirm_fng
            sma_ok = sma is not None and close > sma
            if fng_ok or sma_ok:
                confirmed = j
                how = "fng_above_25" if fng_ok else "close_above_sma20"
                if fng_ok and sma_ok:
                    how = "both"
                break
            # end wait if we have left fear for a long time without confirm? keep waiting
            # until the episode is clearly over AND still no confirm: if F&G observed > 50
            # and never confirmed, drop the setup (fear faded without confirm in a greedy zone)
            j += 1
        if confirmed is None:
            break
        entry_i = confirmed + 1
        if entry_i >= n:
            break
        entry = series[entry_i]["close"]
        exit_i = None
        stopped = False
        fill = None
        last = min(n - 1, entry_i + horizon)
        for k in range(entry_i + 1, last + 1):
            # stop: if low hits entry*(1-stop)
            if series[k]["low"] <= entry * (1 - stop):
                exit_i = k
                stopped = True
                fill = entry * (1 - stop)
                break
        if exit_i is None:
            exit_i = last
            fill = series[exit_i]["close"]
            # if we ran out of data before full horizon and not stopped, drop incomplete
            if exit_i < entry_i + horizon and not stopped:
                break
        nights = (series[exit_i]["date"] - series[entry_i]["date"]).days
        gross = ret(entry, fill)
        net = apply_costs_return(gross, entry, nights, cost_model)
        trades.append({
            "signal_date": series[i]["date"].isoformat(),
            "confirm_date": series[confirmed]["date"].isoformat(),
            "confirm_how": how,
            "entry_date": series[entry_i]["date"].isoformat(),
            "exit_date": series[exit_i]["date"].isoformat(),
            "fng": series[i]["fng"],
            "entry": entry,
            "exit": fill,
            "gross": gross,
            "net": net,
            "nights": nights,
            "year": series[i]["date"].year,
            "stopped": stopped,
        })
        i = exit_i
    return trades


def trade_metrics(trades, key="net"):
    rets = [t[key] for t in trades]
    if not rets:
        return {"trades": 0}
    wins = [x for x in rets if x > 0]
    losses = [x for x in rets if x <= 0]
    gw = sum(wins) if wins else 0.0
    gl = abs(sum(losses)) if losses else 0.0
    # equity curve, all-in each trade, idle otherwise (compound)
    eq = 1.0
    peak = 1.0
    max_dd = 0.0
    for x in rets:
        eq *= 1 + x
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak)
    return {
        "trades": len(rets),
        "win_rate": len(wins) / len(rets),
        "avg_win": statistics.mean(wins) if wins else None,
        "avg_loss": statistics.mean(losses) if losses else None,
        "expectancy": statistics.mean(rets),
        "profit_factor": (gw / gl) if gl > 0 else (math.inf if gw > 0 else 0.0),
        "total_return": eq - 1,
        "max_dd": max_dd,
        "median": statistics.median(rets),
        "worst": min(rets),
        "best": max(rets),
        "n_stopped": sum(1 for t in trades if t.get("stopped")),
    }


def buy_and_hold(series, start_d, end_d, cost_model="spot"):
    days = [r for r in series if start_d <= r["date"] <= end_d]
    if len(days) < 2:
        return {}
    entry, exitp = days[0]["close"], days[-1]["close"]
    nights = (days[-1]["date"] - days[0]["date"]).days
    gross = ret(entry, exitp)
    net = apply_costs_return(gross, entry, nights, cost_model)
    # daily DD
    peak = entry
    max_dd = 0.0
    for r in days:
        peak = max(peak, r["close"])
        max_dd = max(max_dd, (peak - r["close"]) / peak)
    return {
        "start": days[0]["date"].isoformat(),
        "end": days[-1]["date"].isoformat(),
        "gross": gross,
        "net": net,
        "max_dd": max_dd,
        "nights": nights,
    }


def weekly_dca(series, start_d, end_d, mode="plain"):
    """Weekly purchases. mode=plain or fear. Returns list of (date, usd, price, units)."""
    days = [r for r in series if start_d <= r["date"] <= end_d]
    if not days:
        return []
    buys = []
    # every 7 calendar days from first date
    want = days[0]["date"]
    by = {r["date"]: r for r in days}
    last = days[-1]["date"]
    while want <= last:
        # if weekend/missing, use next available day
        r = by.get(want)
        if r is None:
            nxt = [x for x in days if x["date"] >= want]
            if not nxt:
                break
            r = nxt[0]
        fng = r["fng_filled"]
        if mode == "plain":
            usd = 1.0
        else:
            if fng is None:
                usd = 1.0
            elif fng <= 25:
                usd = 2.0
            elif fng >= 75:
                usd = 0.5
            else:
                usd = 1.0
        price = r["close"] * (1 + SPOT_RT / 2)  # pay entry half-spread
        units = usd / price
        buys.append({"date": r["date"], "usd": usd, "price": r["close"], "units": units, "fng": fng})
        want = r["date"] + timedelta(days=7)
    return buys


def dca_stats(series, buys, end_d):
    if not buys:
        return {}
    # scale is applied by caller; here raw
    total_usd = sum(b["usd"] for b in buys)
    units = sum(b["units"] for b in buys)
    # last close (sell cost on residual ignored for apples-to-apples MTM; apply half spread on final)
    last = [r for r in series if r["date"] <= end_d][-1]
    end_px = last["close"] * (1 - SPOT_RT / 2)
    value = units * end_px
    # daily MTM DD: after each day, units bought so far * close / usd spent so far
    bought_u = 0.0
    spent = 0.0
    by_buy = {b["date"]: b for b in buys}
    peak = 0.0
    max_dd = 0.0
    eq_path = []
    start = buys[0]["date"]
    for r in series:
        if r["date"] < start or r["date"] > end_d:
            continue
        if r["date"] in by_buy:
            bought_u += by_buy[r["date"]]["units"]
            spent += by_buy[r["date"]]["usd"]
        if spent <= 0:
            continue
        eq = bought_u * r["close"] / spent
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak else 0
        max_dd = max(max_dd, dd)
        eq_path.append((r["date"], eq))
    return {
        "n_buys": len(buys),
        "total_usd": total_usd,
        "units": units,
        "end_value": value,
        "total_return": value / total_usd - 1 if total_usd else None,
        "max_dd": max_dd,
        "end_date": last["date"].isoformat(),
        "start_date": buys[0]["date"].isoformat(),
    }


def scale_buys(buys, target_usd):
    spent = sum(b["usd"] for b in buys)
    if spent <= 0:
        return buys
    k = target_usd / spent
    return [{**b, "usd": b["usd"] * k, "units": b["units"] * k} for b in buys]


def write_csv(path, rows, fields=None):
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = {}
            for k in fields:
                v = r.get(k)
                if isinstance(v, float):
                    out[k] = f"{v:.8f}"
                elif isinstance(v, date):
                    out[k] = v.isoformat()
                else:
                    out[k] = v
            w.writerow(out)


def pct(x, d=2):
    if x is None:
        return "data nahi hai"
    if x == math.inf:
        return "inf"
    return f"{x*100:.{d}f}%"


def xf(x, d=2):
    if x is None:
        return "data nahi hai"
    if x == math.inf:
        return "inf"
    return f"{x:.{d}f}"


def main():
    prices = load_prices()
    fng = load_fng()
    series = build_series(prices, fng)
    check = spot_check_delta(prices)
    years = classify_years(series)
    start_d, end_d = series[0]["date"], series[-1]["date"]
    # sample for F&G overlap
    fng_first, fng_last = fng[0]["date"], fng[-1]["date"]

    # ---- event study ----
    event_tables = []
    all_event_rows = []
    for h in HORIZONS:
        variants = [
            (f"F&G<=10", lambda r: r["fng"] is not None and r["fng"] <= 10),
            (f"F&G<=20", lambda r: r["fng"] is not None and r["fng"] <= 20),
            (f"F&G<=25", lambda r: r["fng"] is not None and r["fng"] <= 25),
            (f"F&G>={GREED}", lambda r: r["fng"] is not None and r["fng"] >= GREED),
            ("all days", lambda r: True),
        ]
        for name, pred in variants:
            for ov_name, ov in (("overlap", False), ("nonoverlap", True)):
                if name == "all days" and ov:
                    continue
                rows = event_rows(series, pred, h, nonoverlap=ov)
                pack = pack_event(f"{name} {h}d {ov_name}", rows)
                pack["horizon"] = h
                pack["group"] = name
                pack["overlap"] = ov_name
                event_tables.append(pack)
                for r in rows:
                    all_event_rows.append({**r, "group": name, "overlap": ov_name})

    write_csv(HERE / "event_study_events.csv", all_event_rows)

    episodes = {t: fear_episodes(series, t) for t in THRESHOLDS}
    ep_rows = []
    for t, eps in episodes.items():
        for e in eps:
            rec = {**e, "threshold": t}
            # outcomes from first day, enter next close
            entry_i = e["start_i"] + 1
            rec["start"] = e["start"].isoformat()
            rec["end"] = e["end"].isoformat()
            rec["min_date"] = e["min_date"].isoformat()
            for h in HORIZONS:
                if entry_i + h < len(series):
                    rec[f"ret_{h}d"] = ret(series[entry_i]["close"], series[entry_i + h]["close"])
                    rec[f"mae_{h}d"] = mae_from_entry(series, entry_i, h)
                else:
                    rec[f"ret_{h}d"] = None
                    rec[f"mae_{h}d"] = None
            ep_rows.append(rec)
    write_csv(HERE / "fear_episodes.csv", ep_rows)

    # ---- strategies ----
    strat_trades = {}
    strat_metrics = []
    bh_spot = buy_and_hold(series, max(parse_date("2018-02-01"), series[0]["date"]), end_d, "spot")
    bh_none = buy_and_hold(series, max(parse_date("2018-02-01"), series[0]["date"]), end_d, "none")
    bh_xm = buy_and_hold(series, max(parse_date("2018-02-01"), series[0]["date"]), end_d, "xm")

    for thresh in (10, 20, 25):
        for h in (30, 90):
            for cost in ("none", "spot", "xm"):
                tr = run_hold_strategy(series, thresh, h, cost)
                key = f"hold_fng{thresh}_{h}d_{cost}"
                strat_trades[key] = tr
                m = trade_metrics(tr, "net")
                m.update(name=key, kind="hold", thresh=thresh, horizon=h, cost=cost)
                strat_metrics.append(m)
                write_csv(HERE / f"trades_{key}.csv", tr)

    for cost in ("none", "spot", "xm"):
        tr = run_confirmed(series, 20, 25, 90, STOP_PCT, cost)
        key = f"confirm_fng20_90d_{cost}"
        strat_trades[key] = tr
        m = trade_metrics(tr, "net")
        m.update(name=key, kind="confirm", thresh=20, horizon=90, cost=cost)
        strat_metrics.append(m)
        write_csv(HERE / f"trades_{key}.csv", tr)

    # DCA
    dca_start = max(parse_date("2018-02-01"), series[0]["date"])
    plain = weekly_dca(series, dca_start, end_d, "plain")
    fear = weekly_dca(series, dca_start, end_d, "fear")
    plain_s = dca_stats(series, plain, end_d)
    fear_raw = dca_stats(series, fear, end_d)
    fear_scaled = dca_stats(series, scale_buys(fear, plain_s["total_usd"]), end_d)
    # B&H of same total money at first weekly date
    bh_dca = buy_and_hold(series, plain[0]["date"] if plain else dca_start, end_d, "spot")
    write_csv(HERE / "dca_plain_buys.csv", [
        {**b, "date": b["date"].isoformat()} for b in plain
    ])
    write_csv(HERE / "dca_fear_buys.csv", [
        {**b, "date": b["date"].isoformat()} for b in fear
    ])

    # ---- walk-forward threshold selection on 2018-2022 ----
    train_end = parse_date("2022-12-31")
    test_start = parse_date("2023-01-01")
    train_s = [r for r in series if r["date"] <= train_end]
    test_s = [r for r in series if r["date"] >= test_start]

    def pick_threshold(sub, horizon=30, cost="spot"):
        scored = []
        for t in (10, 15, 20, 25):
            tr = run_hold_strategy(sub, t, horizon, cost)
            m = trade_metrics(tr, "net")
            # also excess vs all-day mean
            ev = event_rows(sub, lambda r, tt=t: r["fng"] is not None and r["fng"] <= tt, horizon, True)
            base = event_rows(sub, lambda r: True, horizon, False)
            ev_m = summarize([x["ret"] for x in ev])
            base_m = summarize([x["ret"] for x in base])
            excess = (ev_m.get("mean") or 0) - (base_m.get("mean") or 0) if ev_m and base_m else None
            scored.append({
                "thresh": t,
                "trades": m.get("trades", 0),
                "expectancy": m.get("expectancy"),
                "profit_factor": m.get("profit_factor"),
                "total_return": m.get("total_return"),
                "max_dd": m.get("max_dd"),
                "win_rate": m.get("win_rate"),
                "event_n_nonoverlap": ev_m.get("n"),
                "event_mean": ev_m.get("mean"),
                "baseline_mean": base_m.get("mean"),
                "excess_mean": excess,
            })
        # Selection rule (train only): among thresholds with >= 8 trades,
        # pick highest excess_mean of non-overlap 30d event study; tie-break by expectancy.
        cand = [s for s in scored if (s["trades"] or 0) >= 8 and s["excess_mean"] is not None]
        if not cand:
            cand = [s for s in scored if s["excess_mean"] is not None]
        cand.sort(key=lambda s: (s["excess_mean"], s["expectancy"] or -999), reverse=True)
        chosen = cand[0]["thresh"] if cand else 20
        return chosen, scored

    chosen, train_scores = pick_threshold(train_s, 30, "spot")
    wf_rows = []
    for split_name, sub in (("train_2018-2022", train_s), ("test_2023-now", test_s)):
        for t in (10, 15, 20, 25):
            for h, cost in ((30, "spot"), (30, "xm"), (90, "spot"), (90, "xm")):
                tr = run_hold_strategy(sub, t, h, cost)
                m = trade_metrics(tr, "net")
                ev = event_rows(sub, lambda r, tt=t: r["fng"] is not None and r["fng"] <= tt, h, True)
                base = event_rows(sub, lambda r: True, h, False)
                ev_m = summarize([x["ret"] for x in ev])
                base_m = summarize([x["ret"] for x in base])
                wf_rows.append({
                    "split": split_name,
                    "thresh": t,
                    "horizon": h,
                    "cost": cost,
                    "chosen": (t == chosen),
                    **{f"strat_{k}": v for k, v in m.items()},
                    "event_n": ev_m.get("n"),
                    "event_mean": ev_m.get("mean"),
                    "event_median": ev_m.get("median"),
                    "event_pct_pos": ev_m.get("pct_pos"),
                    "baseline_mean": base_m.get("mean"),
                    "baseline_median": base_m.get("median"),
                    "baseline_pct_pos": base_m.get("pct_pos"),
                    "excess_mean": (ev_m.get("mean") - base_m.get("mean")) if ev_m and base_m and ev_m.get("mean") is not None and base_m.get("mean") is not None else None,
                })
    write_csv(HERE / "walkforward.csv", wf_rows)

    # confirm strategy train/test
    wf_confirm = []
    for split_name, sub in (("train_2018-2022", train_s), ("test_2023-now", test_s)):
        for cost in ("spot", "xm"):
            tr = run_confirmed(sub, 20, 25, 90, STOP_PCT, cost)
            m = trade_metrics(tr, "net")
            wf_confirm.append({"split": split_name, "cost": cost, **m})
    write_csv(HERE / "walkforward_confirm.csv", wf_confirm)

    # ---- bear vs bull year split (event study, F&G<=20, 30d and 90d, nonoverlap) ----
    year_rows = []
    for y, info in years.items():
        sub = [r for r in series if r["date"].year == y]
        if len(sub) < 40:
            continue
        for h in (7, 30, 90):
            ev = event_rows(sub, lambda r: r["fng"] is not None and r["fng"] <= 20, h, True)
            base = event_rows(sub, lambda r: True, h, False)
            ev_m = summarize([x["ret"] for x in ev])
            base_m = summarize([x["ret"] for x in base])
            mae_m = summarize([x["mae"] for x in ev])
            year_rows.append({
                "year": y,
                "year_btc_return": info["return"],
                "label": info["label"],
                "horizon": h,
                "episodes_in_year": sum(1 for e in episodes[20] if e["start"].year == y),
                "n_nonoverlap": ev_m.get("n"),
                "mean": ev_m.get("mean"),
                "median": ev_m.get("median"),
                "pct_pos": ev_m.get("pct_pos"),
                "worst": ev_m.get("worst"),
                "mae_median": mae_m.get("median"),
                "mae_worst": mae_m.get("worst"),
                "baseline_mean": base_m.get("mean"),
                "excess_mean": (ev_m.get("mean") - base_m.get("mean")) if ev_m and base_m and ev_m.get("mean") is not None and base_m.get("mean") is not None else None,
            })
    write_csv(HERE / "year_split.csv", year_rows)

    # Group bear vs bull using the FULL calendar series (do not slice then
    # add +N bars — that would jump from Dec 2018 into 2022).
    regime_rows = []
    year_label = {y: i["label"] for y, i in years.items()}
    for label in ("bear", "bull", "mixed"):
        ys = {y for y, lab in year_label.items() if lab == label}
        for h in (7, 30, 90):
            ev_all = event_rows(series, lambda r: r["fng"] is not None and r["fng"] <= 20, h, True)
            base_all = event_rows(series, lambda r: True, h, False)
            ev = [x for x in ev_all if x["year"] in ys]
            base = [x for x in base_all if x["year"] in ys]
            ev_m = summarize([x["ret"] for x in ev])
            base_m = summarize([x["ret"] for x in base])
            mae_m = summarize([x["mae"] for x in ev])
            regime_rows.append({
                "regime": label,
                "years": ",".join(str(y) for y in sorted(ys)),
                "horizon": h,
                "n_nonoverlap": ev_m.get("n"),
                "mean": ev_m.get("mean"),
                "median": ev_m.get("median"),
                "pct_pos": ev_m.get("pct_pos"),
                "worst": ev_m.get("worst"),
                "mae_median": mae_m.get("median"),
                "baseline_mean": base_m.get("mean"),
                "baseline_median": base_m.get("median"),
                "excess_mean": (ev_m.get("mean") - base_m.get("mean")) if ev_m and base_m and ev_m.get("mean") is not None and base_m.get("mean") is not None else None,
            })
    write_csv(HERE / "regime_split.csv", regime_rows)

    # ---- current episode + similar past ----
    last_fng = fng[-1]
    # streak of <=20 on observed F&G (including last F&G date even if no BTC close yet)
    fng_sorted = list(fng)
    streak20 = 0
    streak10 = 0
    for r in reversed(fng_sorted):
        if r["value"] <= 20:
            streak20 += 1
        else:
            break
    for r in reversed(fng_sorted):
        if r["value"] <= 10:
            streak10 += 1
        else:
            break
    ep_start = None
    for r in reversed(fng_sorted):
        if r["value"] > 20:
            break
        ep_start = r["date"]
    current = {
        "asof_fng_date": last_fng["date"].isoformat(),
        "fng": last_fng["value"],
        "fng_cls": last_fng["cls"],
        "streak_le_20": streak20,
        "streak_le_10": streak10,
        "episode_start": ep_start.isoformat() if ep_start else None,
        "last_btc_close_date": end_d.isoformat(),
        "last_btc_close": series[-1]["close"],
        "forward_returns": "data nahi hai (episode still open; no 7/30/90d outcome yet)",
    }
    # similar: past episodes that reached F&G <= 10, measured from the first day F&G hit <=10
    similar = []
    for e in episodes[20]:
        if e["min_fng"] > 10:
            continue
        # first day in episode with fng <= 10
        hit = None
        for r in series:
            if r["date"] < e["start"] or r["date"] > e["end"]:
                continue
            if r["fng"] is not None and r["fng"] <= 10:
                hit = r
                break
        if hit is None:
            continue
        # skip current open episode (no complete forward)
        entry_i = hit["i"] + 1
        rec = {
            "episode_start": e["start"].isoformat(),
            "episode_end": e["end"].isoformat(),
            "episode_days": e["days"],
            "min_fng": e["min_fng"],
            "first_le10": hit["date"].isoformat(),
            "fng_that_day": hit["fng"],
            "entry_date": series[entry_i]["date"].isoformat() if entry_i < len(series) else None,
        }
        complete = True
        for h in HORIZONS:
            if entry_i + h < len(series):
                rec[f"ret_{h}d"] = ret(series[entry_i]["close"], series[entry_i + h]["close"])
                rec[f"mae_{h}d"] = mae_from_entry(series, entry_i, h)
            else:
                rec[f"ret_{h}d"] = None
                rec[f"mae_{h}d"] = None
                complete = False
        rec["complete"] = complete
        # similarity: closer min_fng to 10, closer episode length so far (7) at the time of first <=10
        days_before_hit = (hit["date"] - e["start"]).days + 1
        rec["days_into_episode_at_le10"] = days_before_hit
        rec["similar_score"] = abs((hit["fng"] or 10) - last_fng["value"]) + 0.3 * abs(days_before_hit - streak20)
        if complete:
            similar.append(rec)
    similar.sort(key=lambda r: r["similar_score"])
    write_csv(HERE / "similar_episodes.csv", similar)

    # also 7th day of <=20 streaks (matched to current 7-day streak)
    similar7 = []
    for e in episodes[20]:
        if e["days"] < 7:
            continue
        # the 7th observed fear day of the episode
        count = 0
        day7 = None
        for r in series:
            if r["date"] < e["start"] or r["date"] > e["end"]:
                continue
            if r["fng"] is not None and r["fng"] <= 20:
                count += 1
                if count == 7:
                    day7 = r
                    break
        if day7 is None:
            continue
        entry_i = day7["i"] + 1
        rec = {
            "episode_start": e["start"].isoformat(),
            "day7": day7["date"].isoformat(),
            "fng_day7": day7["fng"],
            "episode_days": e["days"],
            "min_fng": e["min_fng"],
        }
        complete = True
        for h in HORIZONS:
            if entry_i + h < len(series):
                rec[f"ret_{h}d"] = ret(series[entry_i]["close"], series[entry_i + h]["close"])
                rec[f"mae_{h}d"] = mae_from_entry(series, entry_i, h)
            else:
                rec[f"ret_{h}d"] = None
                rec[f"mae_{h}d"] = None
                complete = False
        rec["complete"] = complete
        if complete:
            similar7.append(rec)
    write_csv(HERE / "similar_day7_streaks.csv", similar7)

    # ---- XM 0.01 lot illustration on hold-30d F&G<=20 ----
    xm001 = []
    tr = strat_trades.get("hold_fng20_30d_none") or run_hold_strategy(series, 20, 30, "none")
    cap = 1000.0
    lot = 0.01  # BTC
    for t in tr:
        nights = t["nights"]
        entry = t["entry"]
        exitp = t["exit"]
        spread = XM_SPREAD * lot
        swap = XM_SWAP * lot * nights
        pnl = lot * (exitp - entry) - spread - swap
        xm001.append({
            **t,
            "pnl_usd_0.01lot": pnl,
            "spread_usd": spread,
            "swap_usd": swap,
            "notional": lot * entry,
        })
    # account path if starting 1000 and taking these sequentially (notional 0.01 doesn't use full cash)
    eq = cap
    peak = cap
    max_dd = 0.0
    for t in xm001:
        eq += t["pnl_usd_0.01lot"]
        peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
    xm001_summary = {
        "trades": len(xm001),
        "start": cap,
        "end": eq,
        "total_pnl": eq - cap,
        "max_dd_usd": max_dd,
        "max_dd_pct": max_dd / cap,
        "mean_pnl": statistics.mean([t["pnl_usd_0.01lot"] for t in xm001]) if xm001 else None,
        "mean_swap": statistics.mean([t["swap_usd"] for t in xm001]) if xm001 else None,
        "mean_spread": statistics.mean([t["spread_usd"] for t in xm001]) if xm001 else None,
    }
    write_csv(HERE / "xm_0.01lot_hold30.csv", xm001)

    # numbers dump for the report
    def ev(group, h, overlap):
        for p in event_tables:
            if p["group"] == group and p["horizon"] == h and p["overlap"] == overlap:
                return p
        return {}

    def sm(name):
        for m in strat_metrics:
            if m["name"] == name:
                return m
        return {}

    out = {
        "generated_ist": time.strftime("%Y-%m-%d %H:%M IST", time.gmtime(time.time() + 19800)),
        "sources": {
            "fng": "Alternative.me Fear & Greed index, daily, 2018-02-01 onward (brain/patterns/fng.csv)",
            "fng_n": len(fng),
            "fng_first": fng_first.isoformat(),
            "fng_last": fng_last.isoformat(),
            "fng_missing_days": 4,
            "price": "Binance BTCUSDT 1-day klines, public data-api.binance.vision, 2018-01-01 onward (spot USDT, no leverage)",
            "price_first": prices[0]["date"].isoformat(),
            "price_last": prices[-1]["date"].isoformat(),
            "price_n": len(prices),
            "delta_spotcheck": check,
            "entry_rule": "No lookahead: if F&G on date D meets the threshold, enter at the next daily close (D+1 close). Outcomes use closes D+1+N. MAE uses lows of the days after entry through day N.",
        },
        "year_labels": {str(y): {"label": i["label"], "return": i["return"]} for y, i in years.items()},
        "independent_episodes": {str(t): len(episodes[t]) for t in THRESHOLDS},
        "event_study": event_tables,
        "strategies": strat_metrics,
        "buy_and_hold": {"none": bh_none, "spot": bh_spot, "xm": bh_xm},
        "dca": {
            "plain": plain_s,
            "fear_raw": fear_raw,
            "fear_scaled_same_cash": fear_scaled,
            "buy_and_hold_same_start_spot": bh_dca,
        },
        "walkforward": {
            "selection_rule": "On 2018-2022 only, among thresholds {10,15,20,25} with at least 8 hold-30d spot trades, pick the highest excess mean vs all-day baseline on non-overlapping 30d event study.",
            "chosen_threshold": chosen,
            "train_scores": train_scores,
            "rows": wf_rows,
            "confirm": wf_confirm,
        },
        "year_split": year_rows,
        "regime_split": regime_rows,
        "current": current,
        "similar_first_le10": similar[:12],
        "similar_day7_count": len(similar7),
        "similar_day7_summary": {
            "n": len(similar7),
            "ret_7_median": summarize([r["ret_7d"] for r in similar7]).get("median"),
            "ret_30_median": summarize([r["ret_30d"] for r in similar7]).get("median"),
            "ret_90_median": summarize([r["ret_90d"] for r in similar7]).get("median"),
            "ret_7_pct_pos": summarize([r["ret_7d"] for r in similar7]).get("pct_pos"),
            "ret_30_pct_pos": summarize([r["ret_30d"] for r in similar7]).get("pct_pos"),
            "ret_90_pct_pos": summarize([r["ret_90d"] for r in similar7]).get("pct_pos"),
            "ret_30_mean": summarize([r["ret_30d"] for r in similar7]).get("mean"),
            "ret_90_mean": summarize([r["ret_90d"] for r in similar7]).get("mean"),
            "ret_30_worst": summarize([r["ret_30d"] for r in similar7]).get("worst"),
            "ret_90_worst": summarize([r["ret_90d"] for r in similar7]).get("worst"),
        },
        "xm_0.01lot_hold30_fng20": xm001_summary,
    }
    with open(HERE / "numbers.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
        f.write("\n")

    # print a short console summary
    print("=== FEAR STUDY ===")
    print("prices", prices[0]["date"], "->", prices[-1]["date"], "n", len(prices))
    print("fng", fng_first, "->", fng_last, "n", len(fng))
    print("delta check", check)
    print("independent episodes", {t: len(episodes[t]) for t in THRESHOLDS})
    print("year labels", {y: (i["label"], None if i["return"] is None else round(i["return"]*100, 1)) for y, i in years.items()})
    print("chosen WF threshold", chosen)
    print("current", current)
    for h in HORIZONS:
        a = ev("F&G<=20", h, "nonoverlap")
        b = ev("all days", h, "overlap")
        g = ev("F&G>=75", h, "nonoverlap")
        print(f"  {h}d F&G<=20 nonov n={a.get('n')} mean={pct(a.get('mean'))} med={pct(a.get('median'))} pos={pct(a.get('pct_pos'),0)} worst={pct(a.get('worst'))} mae_med={pct(a.get('mae_median'))} | baseline mean={pct(b.get('mean'))} | greed mean={pct(g.get('mean'))}")
    for name in ("hold_fng20_30d_spot", "hold_fng20_90d_spot", "hold_fng20_30d_xm", "hold_fng20_90d_xm", "confirm_fng20_90d_spot", "confirm_fng20_90d_xm"):
        m = sm(name)
        print(f"  {name}: trades={m.get('trades')} WR={pct(m.get('win_rate'),0)} exp={pct(m.get('expectancy'))} PF={xf(m.get('profit_factor'),2)} ret={pct(m.get('total_return'))} DD={pct(m.get('max_dd'))}")
    print("B&H spot", pct(bh_spot.get("net")), "DD", pct(bh_spot.get("max_dd")), "XM B&H", pct(bh_xm.get("net")))
    print("DCA plain", pct(plain_s.get("total_return")), "fear scaled", pct(fear_scaled.get("total_return")), "B&H", pct(bh_dca.get("net")))
    print("XM 0.01 lot", xm001_summary)
    print("wrote numbers.json and CSVs")


if __name__ == "__main__":
    main()

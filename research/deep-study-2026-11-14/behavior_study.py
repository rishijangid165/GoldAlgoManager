#!/usr/bin/env python3
"""Gold behaviour study: sessions, day-of-week, news, regimes, sweeps, basis.

Uses HistData spot XAUUSD (2009-03-15 to 2026-11-06) plus Yahoo COMEX GC=F
daily from 2000-08 and 1h from 2024-06 (for the futures-spot basis and the
2026-11-07..13 gap, including the 13 Nov post-mortem).
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
from research.backtest.data import load_daily, load_intraday, session_date, session_name
from research.backtest.features import atr as atr_fn

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
RAW = ROOT / "data" / "raw"
RESULTS = STUDY / "results"
FIGS = STUDY / "figures"
IST = "Asia/Calcutta"
ET = "America/New_York"


def _load_dataset():
    spec = importlib.util.spec_from_file_location("deep_dataset", STUDY / "dataset.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _savefig(fig, name: str) -> Path:
    FIGS.mkdir(parents=True, exist_ok=True)
    path = FIGS / name
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def session_stats(h1: pd.DataFrame) -> pd.DataFrame:
    df = h1.copy()
    df["session_date"] = session_date(df.index)
    df["session"] = session_name(df.index)
    df["ist_hour"] = df.index.tz_convert(IST).hour
    # Per session (asia/london/ny) range and direction
    g = (
        df[df["session"].isin(["asia", "london", "ny"])]
        .groupby(["session_date", "session"], sort=True)
        .agg(
            open=("Open", "first"),
            high=("High", "max"),
            low=("Low", "min"),
            close=("Close", "last"),
            bars=("Close", "size"),
        )
    )
    g["range"] = g["high"] - g["low"]
    g["ret"] = g["close"] - g["open"]
    g["up"] = g["ret"] > 0
    # Daily session range for share
    daily = df.groupby("session_date").agg(d_high=("High", "max"), d_low=("Low", "min"),
                                           d_open=("Open", "first"), d_close=("Close", "last"))
    daily["d_range"] = daily["d_high"] - daily["d_low"]
    g = g.join(daily["d_range"])
    g["range_share"] = g["range"] / g["d_range"].replace(0, np.nan)
    g.to_csv(RESULTS / "session_bars.csv")
    # Summary table
    rows = []
    for sess, part in g.groupby(level="session"):
        rows.append({
            "session": sess,
            "n_days": int(len(part)),
            "mean_range": float(part["range"].mean()),
            "median_range": float(part["range"].median()),
            "p90_range": float(part["range"].quantile(0.90)),
            "mean_abs_ret": float(part["ret"].abs().mean()),
            "up_share": float(part["up"].mean()),
            "mean_range_share_of_day": float(part["range_share"].mean()),
            "median_range_share_of_day": float(part["range_share"].median()),
        })
    tab = pd.DataFrame(rows)
    tab.to_csv(RESULTS / "session_stats.csv", index=False)
    return g, tab


def tod_high_low(m15: pd.DataFrame) -> pd.DataFrame:
    """Hour of the session high / low, in IST and ET, on 15-minute bars."""
    df = m15.copy()
    df["session_date"] = session_date(df.index)
    # First bar that prints the session extreme
    rows = []
    for sess, part in df.groupby("session_date", sort=True):
        if len(part) < 8:
            continue
        hi_i = part["High"].idxmax()
        lo_i = part["Low"].idxmin()
        rows.append({
            "session_date": sess,
            "high_et_hour": hi_i.tz_convert(ET).hour,
            "low_et_hour": lo_i.tz_convert(ET).hour,
            "high_ist_hour": hi_i.tz_convert(IST).hour,
            "low_ist_hour": lo_i.tz_convert(IST).hour,
            "range": float(part["High"].max() - part["Low"].min()),
            "year": pd.Timestamp(sess).year if not hasattr(sess, "year") else sess.year if hasattr(sess, "year") else int(str(sess)[:4]),
        })
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "tod_high_low.csv", index=False)
    # Histograms
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharey=False)
    for ax, col, title in [
        (axes[0, 0], "high_ist_hour", "Hour of session HIGH (IST)"),
        (axes[0, 1], "low_ist_hour", "Hour of session LOW (IST)"),
        (axes[1, 0], "high_et_hour", "Hour of session HIGH (ET)"),
        (axes[1, 1], "low_et_hour", "Hour of session LOW (ET)"),
    ]:
        counts = out[col].value_counts().sort_index()
        ax.bar(counts.index, counts.values, color="#1f4e79")
        ax.set_title(title)
        ax.set_xlabel("hour")
        ax.set_xlim(-0.5, 23.5)
    _savefig(fig, "tod_high_low.png")
    # Probability table
    tab = []
    for col, label in [("high_ist_hour", "high"), ("low_ist_hour", "low")]:
        vc = out[col].value_counts(normalize=True).sort_index()
        for h, p in vc.items():
            tab.append({"kind": label, "ist_hour": int(h), "share": float(p)})
    pd.DataFrame(tab).to_csv(RESULTS / "tod_high_low_share.csv", index=False)
    return out


def dow_effects(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["ret"] = d["Close"] - d["Open"]
    d["logret"] = np.log(d["Close"] / d["Close"].shift(1))
    d["dow"] = d.index.day_of_week
    d["dow_name"] = d.index.day_name()
    d["year"] = d.index.year
    rows = []
    for name, part in [("full", d), ("OOS_2012_2026", d[d["year"] >= 2012]),
                       ("GC_like_2024_2026", d[d["year"] >= 2024])]:
        for dow, g in part.groupby("dow"):
            rows.append({
                "slice": name,
                "dow": int(dow),
                "dow_name": g["dow_name"].iloc[0],
                "n": int(len(g)),
                "mean_close_open": float(g["ret"].mean()),
                "mean_logret": float(g["logret"].mean()),
                "up_share": float((g["ret"] > 0).mean()),
                "mean_range": float((g["High"] - g["Low"]).mean()),
            })
    tab = pd.DataFrame(rows)
    tab.to_csv(RESULTS / "dow_effects.csv", index=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    oos = tab[tab["slice"] == "OOS_2012_2026"]
    ax.bar(oos["dow_name"], oos["mean_close_open"], color="#1f4e79")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("mean close-open ($)")
    ax.set_title("XAUUSD day-of-week drift, 2012-2026 (spot session)")
    _savefig(fig, "dow_effects.png")
    return tab


def asia_width_vs_break(h1: pd.DataFrame) -> pd.DataFrame:
    """Asia range width vs whether London/NY made a close-break, and follow-through."""
    df = h1.copy()
    df["session_date"] = session_date(df.index)
    df["session"] = session_name(df.index)
    df["atr"] = atr_fn(df)
    # Asia range per session (from asia bars only)
    asia = (
        df[df["session"] == "asia"]
        .groupby("session_date")
        .agg(asia_high=("High", "max"), asia_low=("Low", "min"), asia_close=("Close", "last"))
    )
    asia["asia_range"] = asia["asia_high"] - asia["asia_low"]
    # 1h ATR known at 03:00: use the last Asia bar's ATR (no look-ahead into London)
    last_asia_atr = df[df["session"] == "asia"].groupby("session_date")["atr"].last()
    asia["atr"] = last_asia_atr
    asia["width_atr"] = asia["asia_range"] / asia["atr"]
    post = df[df["session"].isin(["london", "ny"]) & (df.index.hour < 13)]
    # first close beyond
    rows = []
    for sess, a in asia.iterrows():
        if not np.isfinite(a["asia_range"]) or a["asia_range"] < 1:
            continue
        day = post[post["session_date"] == sess]
        if day.empty:
            continue
        up = day[day["Close"] > a["asia_high"]]
        dn = day[day["Close"] < a["asia_low"]]
        first = None
        direction = 0
        if not up.empty and (dn.empty or up.index[0] <= dn.index[0]):
            first, direction = up.index[0], 1
        elif not dn.empty:
            first, direction = dn.index[0], -1
        # Follow-through to 17:00: excursion after the break close, or day close vs mid
        rest = df[(df["session_date"] == sess) & (df.index >= (first if first is not None else day.index[0]))]
        follow = np.nan
        faded = np.nan
        if first is not None and len(rest):
            c0 = float(df.loc[first, "Close"])
            if direction == 1:
                follow = float(rest["High"].max() - c0)
                faded = float(c0 - rest["Low"].min())
            else:
                follow = float(c0 - rest["Low"].min())
                faded = float(rest["High"].max() - c0)
        rows.append({
            "session_date": sess,
            "year": pd.Timestamp(str(sess)).year,
            "asia_range": float(a["asia_range"]),
            "atr": float(a["atr"]) if np.isfinite(a["atr"]) else np.nan,
            "width_atr": float(a["width_atr"]) if np.isfinite(a["width_atr"]) else np.nan,
            "broke": first is not None,
            "direction": direction,
            "follow_usd": follow,
            "fade_usd": faded,
            "followed_more": (follow > faded) if np.isfinite(follow) and np.isfinite(faded) else np.nan,
        })
    ev = pd.DataFrame(rows)
    ev.to_csv(RESULTS / "asia_width_events.csv", index=False)
    ev["width_bin"] = pd.cut(
        ev["width_atr"],
        bins=[0, 1, 1.5, 2, 2.5, 3, 4, 20],
        labels=["<1", "1-1.5", "1.5-2", "2-2.5", "2.5-3", "3-4", ">4"],
    )
    oos = ev[ev["year"] >= 2012]
    tab = oos.groupby("width_bin", observed=False).agg(
        n=("broke", "size"),
        break_rate=("broke", "mean"),
        follow_gt_fade=("followed_more", "mean"),
        mean_follow=("follow_usd", "mean"),
        mean_fade=("fade_usd", "mean"),
        mean_range=("asia_range", "mean"),
    ).reset_index()
    tab.to_csv(RESULTS / "asia_width_vs_break.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(tab["width_bin"].astype(str), tab["break_rate"], color="#1f4e79")
    ax.set_ylabel("close-break rate (London or early NY)")
    ax.set_xlabel("Asia range / 1h ATR")
    ax.set_title("Asia width vs breakout frequency, XAUUSD 2012-2026")
    _savefig(fig, "asia_width_vs_break.png")
    return ev, tab


def news_study(m15: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """Pre/post volatility and fade vs follow around NFP (08:30 ET) and FOMC (14:00 ET)."""
    px = m15.copy()
    px["range"] = px["High"] - px["Low"]
    rows = []
    for ev in cal.itertuples(index=False):
        ts = ev.ts
        if ts.tzinfo is None:
            ts = ts.tz_localize(ET)
        else:
            ts = ts.tz_convert(ET)
        # Windows in 15m bars: -2h, 0-30m, 30-90m, 90m-4h
        windows = {
            "pre_2h": (ts - pd.Timedelta(hours=2), ts),
            "post_0_30m": (ts, ts + pd.Timedelta(minutes=30)),
            "post_30_90m": (ts + pd.Timedelta(minutes=30), ts + pd.Timedelta(minutes=90)),
            "post_90m_4h": (ts + pd.Timedelta(minutes=90), ts + pd.Timedelta(hours=4)),
        }
        rec = {"event": ev.event, "ts": ts, "year": ts.year}
        # 15m bar that contains the print: 08:30 -> 08:30 bar if index is left-labeled
        # First-hour move: close at ts+60m minus close at ts-15m (last pre bar).
        pre = px[(px.index >= ts - pd.Timedelta(minutes=15)) & (px.index < ts)]
        post60 = px[(px.index >= ts) & (px.index < ts + pd.Timedelta(minutes=60))]
        post4h = px[(px.index >= ts) & (px.index < ts + pd.Timedelta(hours=4))]
        if pre.empty or post60.empty:
            continue
        pre_close = float(pre.iloc[-1]["Close"])
        # first 60m extreme and close
        h = float(post60["High"].max())
        l = float(post60["Low"].min())
        c60 = float(post60.iloc[-1]["Close"])
        rec["first60_range"] = h - l
        rec["first60_move"] = c60 - pre_close
        rec["first60_abs"] = abs(c60 - pre_close)
        direction = np.sign(c60 - pre_close)
        rec["first60_dir"] = direction
        if not post4h.empty and direction != 0:
            ext = float(post4h["High"].max() - c60) if direction > 0 else float(c60 - post4h["Low"].min())
            fade = float(c60 - post4h["Low"].min()) if direction > 0 else float(post4h["High"].max() - c60)
            rec["follow_after_1h"] = ext
            rec["fade_after_1h"] = fade
            rec["faded"] = fade > 0.5 * abs(c60 - pre_close)  # gave back half of the first-hour close move
            rec["followed"] = ext > fade
        for name, (a, b) in windows.items():
            sl = px[(px.index >= a) & (px.index < b)]
            rec[f"{name}_range"] = float(sl["High"].max() - sl["Low"].min()) if len(sl) else np.nan
            rec[f"{name}_abs_close"] = float(abs(sl.iloc[-1]["Close"] - sl.iloc[0]["Open"])) if len(sl) else np.nan
        rows.append(rec)
    ev = pd.DataFrame(rows)
    ev.to_csv(RESULTS / "news_event_moves.csv", index=False)
    tab_rows = []
    oos = ev[ev["year"] >= 2012]
    for typ, part in oos.groupby("event"):
        tab_rows.append({
            "event": typ,
            "n": int(len(part)),
            "mean_first60_range": float(part["first60_range"].mean()),
            "median_first60_range": float(part["first60_range"].median()),
            "mean_pre_2h_range": float(part["pre_2h_range"].mean()),
            "mean_post_0_30m_range": float(part["post_0_30m_range"].mean()),
            "mean_post_30_90m_range": float(part["post_30_90m_range"].mean()),
            "mean_post_90m_4h_range": float(part["post_90m_4h_range"].mean()),
            "fade_share": float(part["faded"].mean()) if "faded" in part else np.nan,
            "follow_share": float(part["followed"].mean()) if "followed" in part else np.nan,
            "vol_ratio_0_30_vs_pre": float((part["post_0_30m_range"] / part["pre_2h_range"].replace(0, np.nan)).mean()),
        })
    tab = pd.DataFrame(tab_rows)
    tab.to_csv(RESULTS / "news_summary.csv", index=False)
    return ev, tab


def regime_study(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["sma50"] = d["Close"].rolling(50, min_periods=50).mean()
    d["sma200"] = d["Close"].rolling(200, min_periods=200).mean()
    d["atr"] = atr_fn(d)
    d["ret"] = d["Close"] - d["Close"].shift(1)
    d["logret"] = np.log(d["Close"] / d["Close"].shift(1))
    d["regime"] = np.where(
        d["sma50"].isna() | d["sma200"].isna(),
        "warmup",
        np.where(d["Close"] > d["sma50"], np.where(d["Close"] > d["sma200"], "bull_above_both", "above_50_below_200"),
                 np.where(d["Close"] < d["sma200"], "bear_below_both", "below_50_above_200")),
    )
    d["atr_pct"] = d["atr"] / d["Close"]
    d["vol_bin"] = pd.qcut(d["atr_pct"], 4, labels=["Q1_low_vol", "Q2", "Q3", "Q4_high_vol"], duplicates="drop")
    d = d[d["regime"] != "warmup"]
    d.to_csv(RESULTS / "daily_regimes.csv")
    rows = []
    oos = d[d.index.year >= 2012]
    for col in ("regime", "vol_bin"):
        for k, g in oos.groupby(col, observed=False):
            rows.append({
                "group": col, "bucket": str(k), "n": int(len(g)),
                "mean_logret": float(g["logret"].mean()),
                "up_share": float((g["ret"] > 0).mean()),
                "mean_range": float((g["High"] - g["Low"]).mean()),
                "mean_atr": float(g["atr"].mean()),
            })
    tab = pd.DataFrame(rows)
    tab.to_csv(RESULTS / "regime_stats.csv", index=False)
    return d, tab


def sweep_behaviour(h1: pd.DataFrame) -> pd.DataFrame:
    """Prior-day / Asia sweep that closes back in: frequency and follow-through."""
    df = h1.copy()
    df["session_date"] = session_date(df.index)
    df["session"] = session_name(df.index)
    df["atr"] = atr_fn(df)
    # prior day high/low
    daily = df.groupby("session_date").agg(pdh=("High", "max"), pdl=("Low", "min"))
    daily["prior_high"] = daily["pdh"].shift(1)
    daily["prior_low"] = daily["pdl"].shift(1)
    asia = df[df["session"] == "asia"].groupby("session_date").agg(asia_high=("High", "max"), asia_low=("Low", "min"))
    df = df.join(daily[["prior_high", "prior_low"]], on="session_date")
    df = df.join(asia, on="session_date")
    rows = []
    for i in range(len(df)):
        row = df.iloc[i]
        if str(row.get("session")) not in ("london", "ny"):
            continue
        atr = row["atr"]
        if not np.isfinite(atr):
            continue
        excess = max(0.50, 0.15 * atr)
        high, low, close = float(row["High"]), float(row["Low"]), float(row["Close"])
        events = []
        if np.isfinite(row.get("prior_high")) and high >= float(row["prior_high"]) + excess and close <= float(row["prior_high"]) - 0.2:
            events.append(("pdh", -1, high))
        if np.isfinite(row.get("asia_high")) and high >= float(row["asia_high"]) + excess and close <= float(row["asia_high"]) - 0.2:
            events.append(("asia_h", -1, high))
        if np.isfinite(row.get("prior_low")) and low <= float(row["prior_low"]) - excess and close >= float(row["prior_low"]) + 0.2:
            events.append(("pdl", 1, low))
        if np.isfinite(row.get("asia_low")) and low <= float(row["asia_low"]) - excess and close >= float(row["asia_low"]) + 0.2:
            events.append(("asia_l", 1, low))
        if not events:
            continue
        # use first tag
        tag, direction, extreme = events[0]
        # next 8 hours MFE/MAE vs a stop beyond the wick
        sl = extreme + 0.15 * atr if direction == -1 else extreme - 0.15 * atr
        risk = abs(close - sl)
        if risk < 5:
            continue
        mfe = mae = 0.0
        end = min(len(df), i + 9)
        for j in range(i + 1, end):
            h, l = float(df.iloc[j]["High"]), float(df.iloc[j]["Low"])
            fav = (close - l) if direction == -1 else (h - close)
            adv = (h - close) if direction == -1 else (close - l)
            mfe = max(mfe, fav)
            mae = max(mae, adv)
        rows.append({
            "time": df.index[i],
            "year": df.index[i].year,
            "session": row["session"],
            "tag": tag,
            "direction": "SELL" if direction == -1 else "BUY",
            "mfe_r": mfe / risk,
            "mae_r": mae / risk,
            "reached_1_5R": mfe / risk >= 1.5,
            "stopped_1R": mae / risk >= 1.0,
        })
    ev = pd.DataFrame(rows)
    ev.to_csv(RESULTS / "sweep_events.csv", index=False)
    oos = ev[ev["year"] >= 2012] if not ev.empty else ev
    tab = []
    if not oos.empty:
        for keys, g in oos.groupby(["session", "direction"]):
            tab.append({
                "session": keys[0], "direction": keys[1], "n": int(len(g)),
                "mean_mfe_r": float(g["mfe_r"].mean()),
                "mean_mae_r": float(g["mae_r"].mean()),
                "hit_1_5R": float(g["reached_1_5R"].mean()),
                "hit_1R_stop": float(g["stopped_1R"].mean()),
            })
    tab = pd.DataFrame(tab)
    tab.to_csv(RESULTS / "sweep_behaviour.csv", index=False)
    return ev, tab


def basis_study() -> pd.DataFrame:
    """GC=F minus XAUUSD on overlapping 1h bars (2024-06 to 2026-11-06)."""
    ds = _load_dataset()
    xau = ds.load_resampled()["XAUUSD_1h"]
    gc = load_intraday(RAW / "GC=F_1h.csv")
    # align on 1h open stamps
    both = gc[["Open", "High", "Low", "Close"]].join(
        xau[["Open", "High", "Low", "Close"]], how="inner", lsuffix="_gc", rsuffix="_xau"
    )
    if both.empty:
        print("no overlap for basis")
        return pd.DataFrame()
    both["basis"] = both["Close_gc"] - both["Close_xau"]
    both["basis_open"] = both["Open_gc"] - both["Open_xau"]
    both["abs_basis"] = both["basis"].abs()
    both.to_csv(RESULTS / "basis_1h.csv")
    s = {
        "n": int(len(both)),
        "start": str(both.index.min()),
        "end": str(both.index.max()),
        "mean_basis": float(both["basis"].mean()),
        "median_basis": float(both["basis"].median()),
        "p10": float(both["basis"].quantile(0.10)),
        "p90": float(both["basis"].quantile(0.90)),
        "std": float(both["basis"].std()),
        "min": float(both["basis"].min()),
        "max": float(both["basis"].max()),
        "mean_abs": float(both["abs_basis"].mean()),
        "corr_close_ret": float(
            both["Close_gc"].diff().corr(both["Close_xau"].diff())
        ),
    }
    # by month
    both["ym"] = both.index.tz_convert(ET).strftime("%Y-%m")
    monthly = both.groupby("ym")["basis"].agg(["mean", "median", "std", "min", "max", "count"])
    monthly.to_csv(RESULTS / "basis_monthly.csv")
    pd.Series(s).to_csv(RESULTS / "basis_summary.csv")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(both.index, both["basis"], lw=0.6, color="#1f4e79")
    ax.axhline(both["basis"].median(), color="orange", lw=1, label=f"median {both['basis'].median():.2f}")
    ax.set_ylabel("GC=F close − XAUUSD close ($)")
    ax.set_title("Futures vs spot basis, 1h overlap")
    ax.legend()
    _savefig(fig, "basis_1h.png")
    print("basis", s)
    return both


def daily_long_history():
    """GC=F daily since 2000: DOW, 50/200 regime, ATR."""
    d = load_daily(RAW / "GC=F_daily.csv")
    d["ret"] = d["Close"] - d["Close"].shift(1)
    d["logret"] = np.log(d["Close"] / d["Close"].shift(1))
    d["sma50"] = d["Close"].rolling(50).mean()
    d["sma200"] = d["Close"].rolling(200).mean()
    d["atr"] = atr_fn(d)
    d["dow"] = d.index.day_name()
    d["year"] = d.index.year
    d["regime"] = np.where(d["sma200"].isna(), "warmup",
                           np.where((d["Close"] > d["sma50"]) & (d["Close"] > d["sma200"]), "bull",
                                    np.where((d["Close"] < d["sma50"]) & (d["Close"] < d["sma200"]), "bear", "mixed")))
    rows = []
    for slice_name, part in [("2000_2026", d[d["regime"] != "warmup"]),
                             ("2012_2026", d[(d["year"] >= 2012) & (d["regime"] != "warmup")])]:
        for dow, g in part.groupby("dow"):
            rows.append({"slice": slice_name, "kind": "dow", "bucket": dow,
                         "n": len(g), "mean_logret": float(g["logret"].mean()),
                         "up_share": float((g["ret"] > 0).mean())})
        for reg, g in part.groupby("regime"):
            rows.append({"slice": slice_name, "kind": "regime", "bucket": reg,
                         "n": len(g), "mean_logret": float(g["logret"].mean()),
                         "up_share": float((g["ret"] > 0).mean()),
                         "mean_atr": float(g["atr"].mean())})
    tab = pd.DataFrame(rows)
    tab.to_csv(RESULTS / "gcf_daily_longrun.csv", index=False)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(d.index, d["Close"], lw=0.7, color="#1f4e79", label="GC=F")
    ax.plot(d.index, d["sma200"], lw=0.8, color="orange", label="200-day SMA")
    ax.set_title("COMEX gold futures daily, 2000-2026")
    ax.legend()
    ax.set_ylabel("USD / oz")
    _savefig(fig, "gcf_daily_longrun.png")
    return tab


def postmortem_today():
    """Facts for 13 Nov 2026 from Yahoo GC=F (HistData ends 6 Nov)."""
    h1 = load_intraday(RAW / "GC=F_1h.csv")
    m15 = load_intraday(RAW / "GC=F_15m.csv")
    m5_path = RAW / "GC=F_5m.csv"
    m5 = load_intraday(m5_path) if m5_path.exists() else m15
    # COMEX session 12 Nov 18:00 ET -> 13 Nov 17:00 ET
    start = pd.Timestamp("2026-11-12 18:00", tz=ET)
    end = pd.Timestamp("2026-11-13 17:00", tz=ET)
    day_h1 = h1[(h1.index >= start) & (h1.index < end)]
    day_m15 = m15[(m15.index >= start) & (m15.index < end)]
    asia = h1[(h1.index >= start) & (h1.index < pd.Timestamp("2026-11-13 03:00", tz=ET))]
    london = h1[(h1.index >= pd.Timestamp("2026-11-13 03:00", tz=ET)) & (h1.index < pd.Timestamp("2026-11-13 08:00", tz=ET))]
    facts = {
        "source": "Yahoo GC=F (futures). HistData XAUUSD ends 2026-11-06. Basis typically a few dollars.",
        "h1_bars": int(len(day_h1)),
        "m15_bars": int(len(day_m15)),
        "session_high": float(day_h1["High"].max()) if len(day_h1) else None,
        "session_low": float(day_h1["Low"].min()) if len(day_h1) else None,
        "asia_high": float(asia["High"].max()) if len(asia) else None,
        "asia_low": float(asia["Low"].min()) if len(asia) else None,
        "asia_range": None,
        "london_high": float(london["High"].max()) if len(london) else None,
        "london_low": float(london["Low"].min()) if len(london) else None,
        "atr_1h_at_0300": None,
        "london_closed_outside_asia": None,
        "ppi_window": "2026-11-13 08:30 ET / 19:00 IST (US winter)",
    }
    if facts["asia_high"] and facts["asia_low"]:
        facts["asia_range"] = facts["asia_high"] - facts["asia_low"]
    # ATR at last asia bar
    all_h1 = h1.copy()
    all_h1["atr"] = atr_fn(all_h1)
    asia_atr_row = all_h1[(all_h1.index >= start) & (all_h1.index < pd.Timestamp("2026-11-13 03:00", tz=ET))]
    if len(asia_atr_row):
        facts["atr_1h_at_0300"] = float(asia_atr_row["atr"].iloc[-1])
        if facts["asia_range"] and facts["atr_1h_at_0300"]:
            facts["asia_over_atr"] = facts["asia_range"] / facts["atr_1h_at_0300"]
            facts["width_filter_would_block_far_stop"] = bool(facts["asia_over_atr"] > 3.0)
    if facts["asia_high"] and len(london):
        outside = ((london["Close"] > facts["asia_high"]) | (london["Close"] < facts["asia_low"]))
        facts["london_closed_outside_asia"] = bool(outside.any())
        facts["london_closes"] = [round(x, 2) for x in london["Close"].tolist()]
    # Did price trade 3909-3913 spot? On futures, spot ~ futures - ~4 that day.
    # Zone 3909-3913 spot ≈ 3913-3917 GC if basis +4, or check a small band.
    if len(day_m15):
        facts["day_m15_high"] = float(day_m15["High"].max())
        facts["day_m15_low"] = float(day_m15["Low"].min())
        # After 00:00 ET rejection area: max after 01:00 ET and before PPI
        post = day_m15[(day_m15.index >= pd.Timestamp("2026-11-13 01:00", tz=ET))
                       & (day_m15.index < pd.Timestamp("2026-11-13 08:30", tz=ET))]
        if len(post):
            facts["max_after_01ET_before_PPI"] = float(post["High"].max())
            facts["min_after_01ET_before_PPI"] = float(post["Low"].min())
    # PPI window extremes
    ppi = day_m15[(day_m15.index >= pd.Timestamp("2026-11-13 08:00", tz=ET))
                  & (day_m15.index < pd.Timestamp("2026-11-13 10:00", tz=ET))]
    if len(ppi):
        facts["ppi_0800_1000_high"] = float(ppi["High"].max())
        facts["ppi_0800_1000_low"] = float(ppi["Low"].min())
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "postmortem_2026-11-13.json").write_text(json.dumps(facts, indent=2, default=str) + "\n")
    print("postmortem", json.dumps(facts, indent=2, default=str))
    return facts


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    ds = _load_dataset()
    bars = ds.load_resampled()
    h1, m15, daily = bars["XAUUSD_1h"], bars["XAUUSD_15m"], bars["XAUUSD_daily"]
    print("XAUUSD", h1.index.min(), "->", h1.index.max(), "1h", len(h1), "15m", len(m15), "daily", len(daily))

    print("session stats...")
    _, sess_tab = session_stats(h1)
    print(sess_tab.to_string(index=False))

    print("time of day high/low...")
    tod_high_low(m15)

    print("day of week...")
    print(dow_effects(daily).query("slice=='OOS_2012_2026'").to_string(index=False))

    print("asia width vs break...")
    _, wtab = asia_width_vs_break(h1)
    print(wtab.to_string(index=False))

    print("news calendar...")
    import importlib.util
    spec = importlib.util.spec_from_file_location("news_calendar", STUDY / "news_calendar.py")
    news_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(news_mod)
    cal = news_mod.load_calendar()
    ev, ntab = news_study(m15, cal)
    print(ntab.to_string(index=False))

    print("regimes...")
    _, rtab = regime_study(daily)
    print(rtab.to_string(index=False))

    print("sweeps...")
    _, stab = sweep_behaviour(h1)
    print(stab.to_string(index=False))

    print("basis...")
    basis_study()

    print("GC=F daily long run...")
    daily_long_history()

    print("today post-mortem facts...")
    postmortem_today()
    print("behavior study done")
    return 0


if __name__ == "__main__":
    sys.exit(main())

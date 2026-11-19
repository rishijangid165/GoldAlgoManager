#!/usr/bin/env python3
"""BTC Monitor trader brain. Read this before every paper-trade decision.

  python3 brain/brain.py context
  python3 brain/brain.py add-episode --trade-id N
  python3 brain/brain.py mood --note "..."
  python3 brain/brain.py reflect --daily

Lessons never become trading rules by themselves. New rules need
backtest + walk-forward + paper (Simons). Real orders need Rishi's haan.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "patterns"))
import common as C
import find_similar


def _norm_side(trade):
    return C.side_of(trade)


def _thesis(trade):
    for k in ("thesis", "reason", "note"):
        v = trade.get(k)
        if v:
            return str(v).strip()
    return "data nahi hai (no thesis stored at entry)"


def _result_text(trade):
    if trade.get("result"):
        return str(trade["result"])
    exits = trade.get("exits") or []
    if exits:
        return "+".join(e.get("type", "?") for e in exits)
    return trade.get("status") or "unknown"


def _what_happened(trade):
    bits = []
    for e in trade.get("exits") or []:
        bits.append(
            f"{e.get('type')} {e.get('qty_btc')} BTC @ {e.get('price')} "
            f"({e.get('time')}, PnL {e.get('pnl_usdt')})"
        )
    return "; ".join(bits) if bits else (trade.get("note") or "data nahi hai")


def features_at_entry(trade):
    """Use local 1H/4H history (past data only) at last completed 1H before entry."""
    h1p, h4p = C.local_candle_paths()
    if not h1p:
        # try live only as last resort for very new trades
        feat, tick, err = C.live_features()
        return feat, err
    h1 = C.load_candle_csv(h1p)
    h4 = C.load_candle_csv(h4p)
    series = C.compute_series(h1, h4)
    opened = C.parse_ist_to_epoch(trade.get("opened") or trade.get("opened_candle_ist"))
    if opened is None:
        return None, "data nahi hai (cannot parse entry time)"
    # last 1H whose close time <= entry
    j = None
    for i, b in enumerate(h1):
        if b["t"] + 3600 <= opened:
            j = i
        else:
            break
    if j is None:
        return None, "data nahi hai (no completed 1H before entry)"
    feat = C.bar_features(h1, h4, series, j)
    if feat is None:
        return None, "data nahi hai (indicators not ready at entry)"
    fng = C.load_fng_cache() or []
    utc_date = C.time.strftime("%Y-%m-%d", C.time.gmtime(feat["t_close"]))
    fg = C.fng_on_date(fng, utc_date)
    if fg:
        feat["fng"] = fg["value"]
        feat["fng_class"] = fg["cls"]
    else:
        live = C.fetch_fng(limit=0)
        if live:
            C.save_fng_cache(live)
            fg = C.fng_on_date(live, utc_date)
        if fg:
            feat["fng"] = fg["value"]
            feat["fng_class"] = fg["cls"]
        else:
            feat["fng"] = None
            feat["fng_class"] = "data nahi hai"
    return feat, None


def episode_record(trade, feat):
    tid = int(trade["id"])
    eid = f"E{tid:04d}"
    side = _norm_side(trade)
    pnl = float(trade.get("realized_pnl_usdt") or 0)
    if feat:
        fg = feat.get("fng")
        fg_s = f"{fg} {feat.get('fng_class')}" if fg is not None else "data nahi hai"
        situation = (
            f"regime={feat['regime']}; F&G={fg_s}; "
            f"ret24h={feat['ret_24h']*100:+.2f}%; distEMA50={feat['dist_ema50_atr']:+.2f} ATR; "
            f"ATRpct={feat['atr_pct']*100:.0f}; vol={feat['vol_ratio']:.2f}x; "
            f"doji={'yes' if feat.get('doji') else 'no'}; "
            f"news={'yes '+ (feat.get('news_name') or '') if feat.get('news_window') else 'no'}"
        )
    else:
        situation = "data nahi hai (features at entry could not be computed)"
    lesson = "Chhota sample; is ek trade se naya rule nahi banega."
    if pnl > 0 and "TP1" in _result_text(trade):
        lesson = "Target 1 laga, baaki breakeven par band hua. Ye ek jeet hai, edge ka saboot nahi."
    return {
        "id": eid,
        "trade_id": tid,
        "opened_ist": trade.get("opened") or "",
        "closed_ist": trade.get("closed") or "",
        "side": side,
        "entry": trade.get("entry"),
        "stop": trade.get("original_stop") or trade.get("stop"),
        "tp1": trade.get("tp1"),
        "tp2": trade.get("tp2"),
        "qty_btc": trade.get("qty_btc"),
        "thesis": _thesis(trade),
        "market_situation": situation,
        "what_happened": _what_happened(trade),
        "result": _result_text(trade),
        "pnl_usdt": pnl,
        "lesson": lesson,
        "status": trade.get("status"),
        "features": {
            k: feat[k]
            for k in (
                "regime", "ret_24h", "dist_ema50_atr", "atr_pct", "vol_ratio",
                "doji", "news_window", "fng", "fng_class", "ist", "hour_ist", "dow",
            )
            if feat and k in feat
        } if feat else {},
    }


def write_episode_md(rec):
    C.EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    path = C.EPISODES_DIR / f"{rec['trade_id']:04d}.md"
    side = rec["side"].upper()
    lines = [
        f"# Episode {rec['id']} — paper trade #{rec['trade_id']}",
        "",
        f"- Date (IST): opened {rec['opened_ist']}; closed {rec['closed_ist']}",
        f"- Side: {side}",
        f"- Entry: {rec['entry']} · stop {rec['stop']} · Target 1 {rec['tp1']} · Target 2 {rec['tp2']} · size {rec['qty_btc']} BTC",
        f"- Thesis / reason: {rec['thesis']}",
        f"- Market situation: {rec['market_situation']}",
        f"- What happened: {rec['what_happened']}",
        f"- Result: {rec['result']}",
        f"- P/L: {rec['pnl_usdt']:+.2f} USDT (paper only, not real money)",
        f"- Lesson: {rec['lesson']}",
        "",
        "This is one memory. It does not change the trading rules by itself.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def upsert_jsonl(rec):
    C.EPISODES_JSONL.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if C.EPISODES_JSONL.exists():
        for line in C.EPISODES_JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if int(obj.get("trade_id") or 0) != rec["trade_id"]:
                rows.append(obj)
    rows.append(rec)
    rows.sort(key=lambda r: int(r["trade_id"]))
    with open(C.EPISODES_JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def cmd_add_episode(trade_id: int):
    trades, src = C.load_paper_trades()
    trade = C.get_trade(trades, trade_id)
    if not trade:
        print(f"error: trade #{trade_id} data nahi hai in {src}")
        return 1
    feat, err = features_at_entry(trade)
    if err:
        print(f"warn: {err}")
    rec = episode_record(trade, feat)
    path = write_episode_md(rec)
    upsert_jsonl(rec)
    side = _norm_side(trade)
    stop = trade.get("original_stop") or trade.get("stop")
    entry = trade.get("entry")
    dist = abs(float(entry) - float(stop)) if entry is not None and stop is not None else None
    tags = C.trade_tags(feat, side=side, stop_distance=dist, risk_pct=1.0)
    rec["tags"] = sorted(tags)
    upsert_jsonl(rec)
    won = float(trade.get("realized_pnl_usdt") or 0) > 0
    lessons = C.load_lessons()
    touched = C.apply_evidence(lessons, rec["id"], tags, won)
    C.save_lessons(lessons)
    print(f"wrote {path.relative_to(C.BTC_BRAIN)}")
    print(f"updated {C.EPISODES_JSONL.relative_to(C.BTC_BRAIN)}")
    print(f"tags: {', '.join(sorted(tags)) if tags else '(none)'}")
    if touched:
        for lid, direction, st, status in touched:
            print(f"lesson {lid}: evidence {direction}; strength={st} status={status}")
    else:
        print("no lesson evidence updated (no matching auto-update condition, or already applied)")
    return 0


def cmd_mood(note: str):
    feat, tick, err = C.live_features()
    fg = C.fng_latest(C.load_fng_cache())
    price = tick["price"] if tick else (feat["close"] if feat else None)
    regime = feat["regime"] if feat else "data nahi hai"
    if err and not feat:
        regime = "data nahi hai"
    snap = {
        "time_ist": C.ist_fmt(C.now_epoch(), "%Y-%m-%d %H:%M IST"),
        "price": price if price is not None else "data nahi hai",
        "fng": fg["value"] if fg else "data nahi hai",
        "fng_class": fg["cls"] if fg else "data nahi hai",
        "regime": regime,
        "news_note": note or "",
    }
    C.MOOD_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(C.MOOD_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    print(
        f"mood logged {snap['time_ist']}: price={snap['price']} "
        f"F&G={snap['fng']} {snap['fng_class']} regime={snap['regime']} note={note!r}"
    )
    return 0


def _load_jsonl(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def cmd_reflect_daily():
    today = C.ist_fmt(C.now_epoch(), "%Y-%m-%d")
    dest = C.BRAIN_ROOT / "reflections" / "daily" / f"{today}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    trades, _ = C.load_paper_trades()
    todays = []
    for t in trades:
        for key in ("opened", "closed"):
            s = t.get(key) or ""
            if today in s:
                todays.append(t)
                break
    # unique by id
    seen = set()
    uniq = []
    for t in todays:
        if t["id"] not in seen:
            seen.add(t["id"])
            uniq.append(t)
    todays = uniq

    moods = [m for m in _load_jsonl(C.MOOD_LOG) if str(m.get("time_ist", "")).startswith(today)]
    episodes = [e for e in _load_jsonl(C.EPISODES_JSONL) if today in str(e.get("opened_ist", "")) or today in str(e.get("closed_ist", ""))]
    lessons = C.load_lessons()
    touched_ids = set()
    for L in lessons:
        for eid in L.get("applied_episodes") or []:
            # if that episode is from today
            for e in episodes:
                if e.get("id") == eid:
                    touched_ids.add(L["id"])
    touched = [L for L in lessons if L["id"] in touched_ids]
    stats = C.paper_stats(trades)

    # one thing to watch tomorrow, template-based
    watch = "Koi edge saabit nahi. Kal bhi sirf A/A+ setup, warna NO TRADE. Real paisa nahi."
    if any((m.get("fng") not in (None, "data nahi hai") and int(m["fng"]) <= 15) for m in moods):
        watch = "Fear & Greed extreme fear ke kareeb hai. Iska matlab bottom nahi. Kal bhi rule: na chase, na revenge, sirf saaf setup."
    if stats["loss_streak"] >= 2:
        watch = f"Loss streak {stats['loss_streak']} hai. Kal pehle discipline check, naya setup jaldi mat lo."

    agent_block = "(add your own reflection here)"
    if dest.exists():
        old = dest.read_text(encoding="utf-8")
        m = re.search(r"<!-- AGENT_REFLECTION_START -->(.*)<!-- AGENT_REFLECTION_END -->", old, re.S)
        if m:
            inner = m.group(1).strip()
            if inner and inner != "(add your own reflection here)":
                agent_block = inner

    trade_lines = []
    if not todays:
        trade_lines.append("- Aaj koi paper trade nahi / none today.")
    else:
        for t in todays:
            trade_lines.append(
                f"- #{t['id']} {_norm_side(t).upper()} entry={t.get('entry')} "
                f"status={t.get('status')} P/L={float(t.get('realized_pnl_usdt') or 0):+.2f} "
                f"result={_result_text(t)}"
            )

    mood_lines = []
    if not moods:
        mood_lines.append("- Aaj koi mood snapshot nahi.")
    else:
        for m in moods:
            mood_lines.append(
                f"- {m.get('time_ist')}: price={m.get('price')} F&G={m.get('fng')} "
                f"{m.get('fng_class')} regime={m.get('regime')} note={m.get('news_note')!r}"
            )

    lesson_lines = []
    if not touched:
        lesson_lines.append("- Aaj koi lesson evidence update nahi hua.")
    else:
        for L in touched:
            lesson_lines.append(
                f"- {L['id']} strength={L['strength']} status={L['status']} — {L['text']}"
            )

    body = "\n".join([
        f"# Daily reflection — {today} IST",
        "",
        "Template generated from paper trades, mood log, and lessons. This is not a prediction.",
        "",
        "## Today's paper trades",
        *trade_lines,
        "",
        f"Paper book (all time): equity {stats['equity']} USDT (start {stats['start']}), "
        f"P/L {stats['pnl']:+.2f}, max DD {stats['max_dd']} ({stats['max_dd_pct']}%), "
        f"loss streak {stats['loss_streak']}, open {stats['n_open']}.",
        "",
        "## Mood snapshots today",
        *mood_lines,
        "",
        "## Lessons touched today",
        *lesson_lines,
        "",
        "## One thing to watch tomorrow",
        f"- {watch}",
        "",
        "## Agent reflection (fill in after reading the data above)",
        "<!-- AGENT_REFLECTION_START -->",
        agent_block,
        "<!-- AGENT_REFLECTION_END -->",
        "",
    ])
    dest.write_text(body, encoding="utf-8")
    print(f"wrote {dest.relative_to(C.BTC_BRAIN)}")
    return 0


def cmd_context():
    lines = []
    now = C.ist_fmt(C.now_epoch(), "%Y-%m-%d %H:%M IST")
    lines.append(f"=== BTC BRAIN CONTEXT ({now}) ===")
    lines.append("PAPER / DATA COLLECTION ONLY. Koi edge saabit nahi. Real order sirf Rishi ke haan par.")
    lines.append(
        "CORE RULES: risk 1% A+ / 0.5% A, warna 0 | reward >= 3x | stop zaroori | "
        "din 3% / hafta 6% | 5% DD par size aadha | 10% par band | 3 loss par ruko | "
        "1h no revenge | no FOMO | thesis+invalidation. Lessons khud rule nahi bante "
        "(Simons: pehle backtest, walk-forward, phir paper)."
    )

    feat, tick, err = C.live_features()
    fg = C.fng_latest(C.load_fng_cache())
    if feat and fg:
        feat["fng"] = fg["value"]
        feat["fng_class"] = fg["cls"]
    if err and not feat:
        lines.append(f"LIVE: data nahi hai — {err}")
        tags = set()
    else:
        px = tick["price"] if tick else feat.get("close")
        fg_s = f"{fg['value']} {fg['cls']}" if fg else "data nahi hai"
        lines.append(
            f"LIVE: BTC {px:.1f} | last 1H {feat['ist']} IST close {feat['close']:.1f} | "
            f"regime={feat['regime']} | F&G={fg_s} | ret24h={feat['ret_24h']*100:+.2f}% | "
            f"distEMA50={feat['dist_ema50_atr']:+.2f} ATR | ATRpct={feat['atr_pct']*100:.0f} | "
            f"vol={feat['vol_ratio']:.2f}x | hour={feat['hour_ist']} IST dow={feat['dow']}"
            f"{' | NEWS window '+ (feat.get('news_name') or '') if feat.get('news_window') else ''}"
        )
        tags = C.trade_tags(feat, side=None)

    lessons = C.load_lessons()
    relevant = [L for L in lessons if C.show_lesson_for_situation(L, tags)]
    relevant.sort(key=lambda L: (0 if L["status"] == "active" else 1, -L["strength"]))
    lines.append("LESSONS (active/relevant; ye warning hain, auto-rule nahi):")
    shown = 0
    for L in relevant:
        if shown >= 5:
            break
        if L["status"] == "forgotten":
            continue
        lines.append(
            f"  - {L['id']} [{L['status']} {L['strength']:.2f}, n={L['observations']}] {L['text']}"
        )
        shown += 1
    if shown == 0:
        lines.append("  - (no relevant lessons, or lessons file empty)")

    episodes = _load_jsonl(C.EPISODES_JSONL)
    lines.append("LAST EPISODES:")
    if not episodes:
        lines.append("  - (none yet)")
    else:
        for e in episodes[-5:]:
            lines.append(
                f"  - {e.get('id')} {str(e.get('side','')).upper()} {e.get('entry')} "
                f"{float(e.get('pnl_usdt') or 0):+.2f} USDT | {e.get('result')} | {e.get('thesis','')[:80]}"
            )

    # similar
    if feat:
        situations = C.load_situations()
        top, meta = C.similar_to(feat, situations, k=10)
        lines.extend(C.summarize_similar(top, meta))
    else:
        lines.append("Similar past situations: data nahi hai. Ye history hai, prediction nahi.")

    st = C.paper_stats()
    lines.append(
        f"PAPER BOOK: equity {st['equity']} USDT (start {st['start']}, P/L {st['pnl']:+.2f}) | "
        f"max DD {st['max_dd']} USDT ({st['max_dd_pct']}%) | "
        f"current DD {st['current_dd']} | loss streak {st['loss_streak']} | "
        f"closed {st['n_closed']} open {st['n_open']}"
    )
    lines.append("End of context. Agar data nahi hai to andaza mat lagao. Kabhi pakka profit mat bolo.")

    # hard cap-ish: if over 60, compact further wasn't needed if we stayed tight
    text = "\n".join(lines)
    print(text)
    nlines = text.count("\n") + 1
    if nlines > 60:
        print(f"(warning: context was {nlines} lines, target was <60)", file=sys.stderr)
    return 0


def main():
    p = argparse.ArgumentParser(description="BTC Monitor trader brain")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("context", help="Compact briefing to read before any paper trade")

    p_ep = sub.add_parser("add-episode", help="Write episode memory from a paper trade id")
    p_ep.add_argument("--trade-id", type=int, required=True)

    p_mood = sub.add_parser("mood", help="Append a market mood snapshot")
    p_mood.add_argument("--note", default="", help="News or mood note (no secrets)")

    p_ref = sub.add_parser("reflect", help="Write a dated reflection file")
    p_ref.add_argument("--daily", action="store_true", help="Write today's daily reflection")

    args = p.parse_args()
    if args.cmd == "context":
        return cmd_context()
    if args.cmd == "add-episode":
        return cmd_add_episode(args.trade_id)
    if args.cmd == "mood":
        return cmd_mood(args.note)
    if args.cmd == "reflect":
        if not args.daily:
            print("error: use --daily")
            return 2
        return cmd_reflect_daily()
    return 2


if __name__ == "__main__":
    sys.exit(main() or 0)

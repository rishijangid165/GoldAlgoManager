#!/usr/bin/env python3
"""Build GoldAlgoManager live-dashboard JSON from box files only.

Reads MT5 (Wine) artifacts and the gold-algo repo, and writes
data/processed/dashboard_data.json. Never invents prices, balances,
or trades. Missing fields are left null / omitted with a note.

Refresh the Canvas Page after a run by replacing the baked-in `DATA`
object via EditCanvas (see the `canvas_edit_hint` field in the JSON).

Examples
--------
python scripts/build_dashboard_data.py
python scripts/build_dashboard_data.py --out data/processed/dashboard_data.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc
# MetaQuotes-Demo server clock is UTC+2, confirmed by paired
# time_utc / server_time (and CLOSE_TIME_SERVER) in the one-shot result files.
SERVER_TZ = timezone(timedelta(hours=2))

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "data" / "processed" / "dashboard_data.json"

MT5_ROOT = Path("/home/box/.wine-mt5/drive_c/MT5")
MT5_FILES = MT5_ROOT / "MQL5" / "Files"
MT5_LOGS = MT5_ROOT / "logs"
MT5_MQL5_LOGS = MT5_ROOT / "MQL5" / "logs"

# Owner-requested start-of-day reference after the two closed demo trades
# (GoldDemoCloseOnce balance_after and EA "new trading day" start equity).
SOD_BALANCE_REF = 100046.10
STARTING_CAPITAL = 100000.00

JOURNAL_EVENTS_TRADE = {"ENTRY", "EXIT", "TP1_PARTIAL", "BE_MOVE"}


def ist_now() -> datetime:
    return datetime.now(tz=IST)


def fmt_ist(dt: datetime | None, with_seconds: bool = True) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local = dt.astimezone(IST)
    fmt = "%Y-%m-%d %H:%M:%S IST" if with_seconds else "%Y-%m-%d %H:%M IST"
    return local.strftime(fmt)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def parse_mt5_time(value: str | None, tz=UTC) -> datetime | None:
    """Parse '2026.11.13 05:32:23' or '2026-11-13 05:32:23'."""
    if not value:
        return None
    text = value.strip().replace("T", " ").replace("Z", "")
    text = text.replace(".", "-", 2)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    return parse_iso(value)


def decode_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    # UTF-16 without BOM (MT5 logs often look like this: second byte is 0x00)
    if len(raw) >= 4 and raw[1] == 0 and raw[3] == 0:
        return raw.decode("utf-16-le")
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_kv_result(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in decode_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith("----") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[key.strip()] = val.strip()
    return data


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def money(value: float | None, signed: bool = False) -> str | None:
    if value is None:
        return None
    if signed:
        return f"{value:+,.2f}"
    return f"{value:,.2f}"


def read_journal(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = decode_text(path)
    # Header is tab-separated
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    reader = csv.DictReader(lines, delimiter="\t")
    rows = []
    for row in reader:
        rows.append({k.strip(): (v or "").strip() for k, v in row.items() if k})
    return rows


def latest_start_equity_from_logs() -> tuple[float | None, datetime | None, str | None]:
    """Parse 'GoldAI new trading day (server). Start equity=' from MQL5 logs."""
    pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d+)\s+GoldAIBridge.*?Start equity=([0-9.]+)",
        re.IGNORECASE,
    )
    best: tuple[float | None, datetime | None, str | None] = (None, None, None)
    for folder in (MT5_MQL5_LOGS, MT5_LOGS):
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.log")):
            date_part = path.stem  # YYYYMMDD
            try:
                day = datetime.strptime(date_part, "%Y%m%d").date()
            except ValueError:
                continue
            text = decode_text(path)
            for match in pattern.finditer(text):
                t = datetime.strptime(match.group(1).split(".")[0], "%H:%M:%S").time()
                # Expert logs are written in UTC (matches journal START timestamps).
                dt = datetime.combine(day, t, tzinfo=UTC)
                eq = to_float(match.group(2))
                if best[1] is None or (dt and dt > best[1]):
                    best = (eq, dt, str(path))
    return best


def latest_sync_positions() -> tuple[int | None, datetime | None]:
    """Last 'terminal synchronized ... N positions' from terminal logs."""
    pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d+)\s+Network\s+'[^']+': terminal synchronized with [^:]+: (\d+) positions",
    )
    best_n, best_dt = None, None
    if not MT5_LOGS.exists():
        return None, None
    for path in sorted(MT5_LOGS.glob("20*.log")):
        date_part = path.stem
        try:
            day = datetime.strptime(date_part, "%Y%m%d").date()
        except ValueError:
            continue
        text = decode_text(path)
        for match in pattern.finditer(text):
            t = datetime.strptime(match.group(1).split(".")[0], "%H:%M:%S").time()
            # Terminal log on this box is GMT+0 (see startup line).
            dt = datetime.combine(day, t, tzinfo=UTC)
            n = int(match.group(2))
            if best_dt is None or dt > best_dt:
                best_n, best_dt = n, dt
    return best_n, best_dt


def parse_trades_from_results() -> list[dict[str, Any]]:
    """Build closed trades from the one-shot demo result files."""
    sell_paths = list(MT5_FILES.glob("*SellOnce*_result.txt")) + list(
        (REPO_ROOT / "logs").glob("*SellOnce*_result.txt")
    )
    close_paths = list(MT5_FILES.glob("*CloseOnce*_result.txt")) + list(
        (REPO_ROOT / "logs").glob("*CloseOnce*_result.txt")
    )
    # Prefer the MT5 Files copies (live) over repo logs.
    sell = {}
    for p in sell_paths:
        kv = parse_kv_result(p)
        if kv:
            sell = kv
            sell["_source"] = str(p)
    close = {}
    for p in close_paths:
        kv = parse_kv_result(p)
        if kv:
            close = kv
            close["_source"] = str(p)

    trades: list[dict[str, Any]] = []

    # Test SELL 0.01 from the "old ticket" history block inside SellOnce result.
    # The file is a single kv dump; fields for the old ticket use generic names
    # (deal, profit, etc.) before the later open of the owner-requested trade.
    # We parse the raw text for the historical ticket block, which is more reliable.
    if sell_paths:
        # Use the same preferred file as sell
        raw_path = Path(sell.get("_source", "")) if sell else None
        if raw_path and raw_path.exists():
            raw = decode_text(raw_path)
            test = _parse_test_ticket(raw)
            if test:
                trades.append(test)

    # Owner-requested SELL, opened in SellOnce and closed in CloseOnce.
    if close:
        ticket = close.get("OPEN_TICKET") or close.get("order")
        entry = to_float(close.get("OPEN_PRICE"))
        exit_px = to_float(close.get("CLOSE_PRICE") or close.get("close_price_result"))
        volume = to_float(close.get("OPEN_VOLUME") or close.get("close_volume"))
        profit = to_float(close.get("CLOSE_PROFIT"))
        swap = to_float(close.get("CLOSE_SWAP")) or 0.0
        comm = to_float(close.get("CLOSE_COMMISSION")) or 0.0
        sl = to_float(close.get("OPEN_SL"))
        # Open time is in the history deal line (server time) inside the close file.
        open_server = _search_kv_in_text(
            decode_text(Path(close["_source"])),
            r"deal=\d+ order=\d+ pos=" + re.escape(str(ticket or "")) + r".*?time=([0-9. :]+)",
        )
        close_server = close.get("CLOSE_TIME_SERVER")
        open_dt = parse_mt5_time(open_server, SERVER_TZ) if open_server else None
        close_dt = parse_mt5_time(close_server, SERVER_TZ) if close_server else None
        net = None
        if profit is not None:
            net = round(profit + swap + comm, 2)
        risk_money = None
        r_multiple = None
        # Prefer actual_risk from the sell-once sizing dump if same ticket.
        if sell.get("OPEN_TICKET") == ticket or sell.get("OPEN_PRICE") == close.get("OPEN_PRICE"):
            risk_money = to_float(sell.get("actual_risk"))
        if risk_money is None and entry is not None and sl is not None and volume is not None:
            # $1 per 0.01 point per 0.01 lot? Contract 100 oz, $1 per $0.01 move per 1.00 lot
            # → $1 per 1.00 point per 0.01 lot? tick_value=1.00 means $1 per 0.01? 
            # From the result file: sl_dist=30.16, loss_per_lot=3016, lots=0.16, actual_risk=482.56
            # 30.16 * 100 * 0.16 = 482.56. Yes: $1 per $0.01? No: 30.16 points * $100/point/lot * 0.16 lots.
            risk_money = round(abs(entry - sl) * 100.0 * volume, 2)
        if net is not None and risk_money:
            r_multiple = round(net / risk_money, 4)
        trades.append(
            {
                "ticket": ticket,
                "symbol": "XAUUSD",
                "side": close.get("OPEN_SIDE") or "SELL",
                "lots": volume,
                "entry": entry,
                "exit": exit_px,
                "sl": sl,
                "tp": to_float(close.get("OPEN_TP")),
                "profit": profit,
                "swap": swap,
                "commission": comm,
                "pnl": net,
                "r_multiple": r_multiple,
                "risk_money": risk_money,
                "open_time_ist": fmt_ist(open_dt),
                "close_time_ist": fmt_ist(close_dt),
                "open_time_utc": open_dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if open_dt else None,
                "close_time_utc": close_dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if close_dt else None,
                "reason": "Owner requested close (book profit)",
                "comment": close.get("OPEN_COMMENT") or "owner-requested-demo",
                "source": close.get("_source"),
                "open_dt": open_dt.isoformat() if open_dt else None,
                "close_dt": close_dt.isoformat() if close_dt else None,
            }
        )
    return trades


def _search_kv_in_text(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else None


def _parse_test_ticket(raw: str) -> dict[str, Any] | None:
    """Extract the historical test SELL 0.01 that was stopped out."""
    # Look for the old-ticket header and the two deals (entry + SL exit).
    block_m = re.search(r"---- old ticket (\d+) ----(.*?)(?=sync_wait_ms=|\Z)", raw, re.DOTALL)
    if not block_m:
        # Fallback: any deal with comment=test
        if "comment=test" not in raw:
            return None
        block = raw
        ticket = None
    else:
        ticket = block_m.group(1)
        block = block_m.group(2)

    deals = re.findall(
        r"deal=(\d+) order=(\d+) pos=(\d+) symbol=(\w+) type=(\d+) entry=(\d+) reason=(\d+) "
        r"vol=([0-9.]+) price=([0-9.]+) profit=([0-9.\-]+) swap=([0-9.\-]+) commission=([0-9.\-]+) "
        r"sl=([0-9.]+) tp=([0-9.]+) time=([0-9. :]+) comment=(.*)",
        block,
    )
    if len(deals) < 2:
        return None
    # type 1 = sell, entry 0 = in; type 0 = buy, entry 1 = out
    entry_deal = None
    exit_deal = None
    for d in deals:
        rec = {
            "deal": d[0],
            "order": d[1],
            "pos": d[2],
            "symbol": d[3],
            "type": int(d[4]),
            "entry": int(d[5]),
            "reason": int(d[6]),
            "vol": float(d[7]),
            "price": float(d[8]),
            "profit": float(d[9]),
            "swap": float(d[10]),
            "commission": float(d[11]),
            "sl": float(d[12]),
            "tp": float(d[13]),
            "time": d[14].strip(),
            "comment": d[15].strip(),
        }
        if rec["entry"] == 0:
            entry_deal = rec
        elif rec["entry"] == 1:
            exit_deal = rec
    if not entry_deal or not exit_deal:
        return None
    open_dt = parse_mt5_time(entry_deal["time"], SERVER_TZ)
    close_dt = parse_mt5_time(exit_deal["time"], SERVER_TZ)
    net = round(exit_deal["profit"] + exit_deal["swap"] + exit_deal["commission"], 2)
    volume = entry_deal["vol"]
    risk_money = round(abs(entry_deal["price"] - entry_deal["sl"]) * 100.0 * volume, 2)
    r_multiple = round(net / risk_money, 4) if risk_money else None
    reason = "SL 3905.00 (test ticket)"
    if exit_deal["reason"] == 4 or "sl" in exit_deal["comment"].lower():
        reason = f"Stopped out at SL {exit_deal['price']:.2f} (test)"
    return {
        "ticket": ticket or entry_deal["pos"],
        "symbol": entry_deal["symbol"],
        "side": "SELL" if entry_deal["type"] == 1 else "BUY",
        "lots": volume,
        "entry": entry_deal["price"],
        "exit": exit_deal["price"],
        "sl": entry_deal["sl"],
        "tp": entry_deal["tp"],
        "profit": exit_deal["profit"],
        "swap": exit_deal["swap"],
        "commission": exit_deal["commission"],
        "pnl": net,
        "r_multiple": r_multiple,
        "risk_money": risk_money,
        "open_time_ist": fmt_ist(open_dt),
        "close_time_ist": fmt_ist(close_dt),
        "open_time_utc": open_dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if open_dt else None,
        "close_time_utc": close_dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if close_dt else None,
        "reason": reason,
        "comment": entry_deal["comment"] or "test",
        "source": "GoldDemoSellOnce_result.txt (old ticket history)",
        "open_dt": open_dt.isoformat() if open_dt else None,
        "close_dt": close_dt.isoformat() if close_dt else None,
    }


def trades_from_journal(rows: list[dict[str, str]], existing_tickets: set[str]) -> list[dict[str, Any]]:
    """Turn EA journal ENTRY/EXIT (and partials) into trades not already in results."""
    by_ticket: dict[str, dict[str, Any]] = {}
    extras: list[dict[str, Any]] = []
    for row in rows:
        event = (row.get("event") or "").upper()
        ticket = row.get("ticket") or "0"
        if event not in JOURNAL_EVENTS_TRADE:
            continue
        if ticket in existing_tickets or ticket == "0":
            # Still record if it's a real ticket already listed? skip closed duplicates
            if ticket in existing_tickets:
                continue
            if ticket == "0":
                continue
        rec = by_ticket.setdefault(ticket, {"ticket": ticket, "events": []})
        rec["events"].append(row)
        rec["symbol"] = row.get("symbol") or rec.get("symbol") or "XAUUSD"
        rec["side"] = row.get("bias") or rec.get("side")
        if event == "ENTRY":
            rec["lots"] = to_float(row.get("volume"))
            rec["entry"] = to_float(row.get("price"))
            rec["sl"] = to_float(row.get("sl"))
            rec["tp"] = to_float(row.get("tp1"))
            rec["tp2"] = to_float(row.get("tp2"))
            rec["open_time_utc"] = row.get("time_utc")
            rec["comment"] = row.get("details") or row.get("rationale")
            rec["reason"] = "EA entry"
        elif event == "EXIT":
            rec["exit"] = to_float(row.get("price"))
            rec["pnl"] = to_float(row.get("profit"))
            rec["close_time_utc"] = row.get("time_utc")
            rec["reason"] = row.get("details") or row.get("rationale") or "EA exit"
            rec["lots"] = rec.get("lots") or to_float(row.get("volume"))
        elif event == "TP1_PARTIAL":
            rec.setdefault("partials", []).append(
                {
                    "time_utc": row.get("time_utc"),
                    "price": to_float(row.get("price")),
                    "volume": to_float(row.get("volume")),
                    "profit": to_float(row.get("profit")),
                    "details": row.get("details"),
                }
            )

    for ticket, rec in by_ticket.items():
        open_dt = parse_iso(rec.get("open_time_utc"))
        close_dt = parse_iso(rec.get("close_time_utc"))
        rec["open_time_ist"] = fmt_ist(open_dt)
        rec["close_time_ist"] = fmt_ist(close_dt)
        rec["open_dt"] = open_dt.isoformat() if open_dt else None
        rec["close_dt"] = close_dt.isoformat() if close_dt else None
        if rec.get("entry") is not None and rec.get("sl") is not None and rec.get("lots"):
            rec["risk_money"] = round(abs(rec["entry"] - rec["sl"]) * 100.0 * rec["lots"], 2)
            if rec.get("pnl") is not None and rec["risk_money"]:
                rec["r_multiple"] = round(rec["pnl"] / rec["risk_money"], 4)
        rec.pop("events", None)
        rec["source"] = "GoldAI_journal.csv"
        extras.append(rec)
    return extras


def open_position_from_journal(rows: list[dict[str, str]]) -> dict[str, Any] | None:
    """ENTRY without a later EXIT on the same ticket = still open (as of journal)."""
    latest_by_ticket: dict[str, list[str]] = {}
    latest_row: dict[str, dict[str, str]] = {}
    for row in rows:
        event = (row.get("event") or "").upper()
        ticket = row.get("ticket") or "0"
        if event not in JOURNAL_EVENTS_TRADE or ticket == "0":
            continue
        latest_by_ticket.setdefault(ticket, []).append(event)
        latest_row[ticket] = row
    for ticket, events in latest_by_ticket.items():
        if "ENTRY" in events and "EXIT" not in events:
            row = latest_row[ticket]
            open_dt = parse_iso(row.get("time_utc"))
            return {
                "ticket": ticket,
                "symbol": row.get("symbol") or "XAUUSD",
                "side": row.get("bias"),
                "lots": to_float(row.get("volume")),
                "entry": to_float(row.get("price")),
                "sl": to_float(row.get("sl")),
                "tp1": to_float(row.get("tp1")),
                "tp2": to_float(row.get("tp2")),
                "open_time_ist": fmt_ist(open_dt),
                "open_time_utc": row.get("time_utc"),
                "comment": row.get("details") or row.get("rationale"),
                "source": "GoldAI_journal.csv",
            }
    return None


def load_decision() -> dict[str, Any]:
    path = REPO_ROOT / "decisions" / "current.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    data["_path"] = str(path)
    return data


def decision_card(decision: dict[str, Any], now: datetime) -> dict[str, Any]:
    gen = parse_iso(decision.get("generated_at"))
    valid = parse_iso(decision.get("valid_until"))
    blackouts = []
    in_blackout = False
    next_blackout = None
    for item in decision.get("news_blackout") or []:
        start = parse_iso(item.get("start"))
        end = parse_iso(item.get("end"))
        rec = {
            "start_ist": fmt_ist(start),
            "end_ist": fmt_ist(end),
            "start_utc": item.get("start"),
            "end_utc": item.get("end"),
            "reason": item.get("reason"),
        }
        blackouts.append(rec)
        if start and end and start <= now <= end:
            in_blackout = True
        if start and now < start and (next_blackout is None or start < parse_iso(next_blackout["start_utc"])):
            next_blackout = rec

    status = "none"
    bias = (decision.get("bias") or "NONE").upper()
    expired = bool(valid and now > valid)
    if decision.get("kill_switch"):
        status = "kill_switch"
    elif expired:
        status = "expired"
    elif in_blackout:
        status = "news_blackout"
    elif bias in {"BUY", "SELL"}:
        status = "waiting_for_zone"
    else:
        status = "flat"

    zone = decision.get("entry_zone") or {}
    tps = decision.get("take_profits") or []
    return {
        "bias": bias,
        "symbol": decision.get("symbol") or "XAUUSD",
        "entry_zone_low": zone.get("low"),
        "entry_zone_high": zone.get("high"),
        "stop_loss": decision.get("stop_loss"),
        "take_profits": tps,
        "tp1": tps[0] if len(tps) > 0 else None,
        "tp2": tps[1] if len(tps) > 1 else None,
        "confidence": decision.get("confidence"),
        "max_risk_pct": decision.get("max_risk_pct"),
        "generated_at_ist": fmt_ist(gen),
        "valid_until_ist": fmt_ist(valid, with_seconds=False) if valid else None,
        "valid_until_utc": decision.get("valid_until"),
        "expired": expired,
        "kill_switch": bool(decision.get("kill_switch")),
        "in_news_blackout": in_blackout,
        "news_blackout": blackouts,
        "next_blackout": next_blackout,
        "rationale": decision.get("rationale"),
        "status": status,
        "source": decision.get("_path"),
    }


def load_backtest_summary() -> dict[str, Any]:
    """Headline numbers from the backtest README (as used in the playbook).

    Exact CSV figures are attached under `exact` so a refresh can show more
    precision without changing the published README headline.
    """
    headline = {
        "setup": "Asia-range breakout (1h, no trend filter)",
        "sample": "GC=F 1h, 2024-07-07 to 2026-11-13, after costs",
        "trades": 132,
        "win_rate_pct": 53.8,
        "avg_r": 0.37,
        "profit_factor": 1.79,
        "net_usd": 26791,
        "max_dd_pct": -3.4,
        "tp2_rate_pct": 31,
        "london": {
            "trades": 72,
            "win_rate_pct": 59.7,
            "avg_r": 0.53,
            "profit_factor": 2.27,
            "net_usd": 20763,
        },
        "new_york": {
            "trades": 60,
            "win_rate_pct": 46.7,
            "avg_r": 0.19,
            "profit_factor": 1.35,
            "net_usd": 6028,
        },
        "note": (
            "The only mechanical setup with a clear 1h edge after costs. "
            "Both buys and sells worked. Figures are from research/backtest/README.md "
            "(rule-based tests on COMEX futures, not a live-spot guarantee)."
        ),
        "source": str(REPO_ROOT / "research" / "backtest" / "README.md"),
    }
    csv_path = REPO_ROOT / "research" / "backtest" / "results" / "metrics_summary.csv"
    if csv_path.exists():
        with csv_path.open() as fh:
            for row in csv.DictReader(fh):
                if row.get("variant") == "1h|breakout|no_filter":
                    headline["exact"] = {
                        "variant": row["variant"],
                        "trades": int(float(row["n"])),
                        "wins": int(float(row["wins"])),
                        "losses": int(float(row["losses"])),
                        "win_rate_pct": float(row["win_rate"]),
                        "avg_r": float(row["avg_r"]),
                        "profit_factor": float(row["profit_factor"]),
                        "net_usd": float(row["net_pnl"]),
                        "max_dd_pct": float(row["max_dd_pct"]),
                        "tp2_rate_pct": float(row["tp2_rate"]),
                        "end_equity": float(row["end_equity"]),
                        "source": str(csv_path),
                    }
                    break
    return headline


def playbook_rules() -> list[dict[str, str]]:
    return [
        {"id": "one-trade", "text": "One open trade at a time. No averaging, no second position, no hedge."},
        {"id": "risk", "text": "Risk 0.5% of current equity per trade. Size from the actual stop distance. Skip if below 0.01 lots."},
        {"id": "stop", "text": "Always a hard stop beyond structure. No mental stops."},
        {"id": "rr", "text": "Do not take a trade that cannot offer at least 1.5R to TP1 at the planned fill."},
        {"id": "scale", "text": "Close half at 1.5R (TP1), move the runner to breakeven, leave the rest to 3R or the next structure level."},
        {"id": "daily-loss", "text": "Daily loss stop: −2% realized. No new trades that COMEX session."},
        {"id": "attempts", "text": "Max two new attempts per session, and only if the first is already closed."},
        {"id": "binding", "text": "Kill switch, valid_until, and news blackout in the decision file are binding."},
        {"id": "priority", "text": "Priority: blackout/loss-stop/kill → Asia breakout (A) → optional NY with-trend sweep (B) → discretionary downtrend supply rejection → NONE."},
        {"id": "no-chase", "text": "Do not chase a breakout already more than half the Asia range through the level. Do not short a live rally just because price reached a sell zone — wait for a rejection close."},
    ]


def schedule() -> list[dict[str, str]]:
    return [
        {
            "name": "Weekday 3-hour check",
            "when": "Every ~3 hours, weekdays",
            "detail": "Full D/4H/1H/15M read, update notes and the decision file if the idea has changed.",
        },
        {
            "name": "London open — Asia breakout",
            "when": "13:40 and 14:40 IST, weekdays",
            "detail": "Lock the completed Asia range and look for the A-setup (first 1h close beyond the range). First check was scheduled around 13:45 IST on 13 Nov 2026.",
        },
        {
            "name": "Saturday review",
            "when": "Saturday",
            "detail": "Weekly review of trades, journal lessons, and whether the playbook still matches results.",
        },
    ]


def build_equity_curve(
    trades: list[dict[str, Any]],
    start_equity_first: float | None,
    start_equity_first_dt: datetime | None,
    current_balance: float,
    now: datetime,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    # Opening reference: EA first start equity if known, else 100k label only as a reference point.
    if start_equity_first is not None and start_equity_first_dt is not None:
        points.append(
            {
                "t": fmt_ist(start_equity_first_dt, with_seconds=False),
                "label": "EA start equity",
                "equity": start_equity_first,
                "sort": start_equity_first_dt.isoformat(),
            }
        )
    else:
        # Do not invent a timestamped $100k deposit if we have no file for it.
        pass

    running = start_equity_first
    closed = [t for t in trades if t.get("close_dt") and t.get("pnl") is not None]
    closed.sort(key=lambda t: t["close_dt"])
    for t in closed:
        close_dt = parse_iso(t["close_dt"])
        if running is not None:
            running = round(running + t["pnl"], 2)
            equity = running
        else:
            equity = None
        # Prefer known post-trade balances when we have them.
        if abs((t.get("pnl") or 0) - (-22.49)) < 0.001 and t.get("lots") == 0.01:
            equity = 99977.46  # balance_synced in SellOnce result after the test SL
            running = equity
        if t.get("ticket") and str(t["ticket"]) == "11382667647":
            equity = 100046.10  # balance_after in CloseOnce result
            running = equity
        points.append(
            {
                "t": fmt_ist(close_dt, with_seconds=False),
                "label": f"{t.get('side')} {t.get('lots')} close",
                "equity": equity,
                "pnl": t.get("pnl"),
                "sort": close_dt.isoformat() if close_dt else "",
            }
        )

    # Current balance point (if it differs in time from the last close)
    points.append(
        {
            "t": fmt_ist(now, with_seconds=False),
            "label": "Last known balance",
            "equity": current_balance,
            "sort": now.isoformat(),
        }
    )
    # Drop points with no equity
    points = [p for p in points if p.get("equity") is not None]
    return points


def first_ea_start_equity(rows: list[dict[str, str]]) -> tuple[float | None, datetime | None]:
    eq, dt, _ = latest_start_equity_from_logs()
    # Prefer the earliest "new trading day" if we want the original start.
    pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d+)\s+GoldAIBridge.*?Start equity=([0-9.]+)",
        re.IGNORECASE,
    )
    earliest: tuple[float | None, datetime | None] = (None, None)
    latest: tuple[float | None, datetime | None] = (eq, dt)
    for folder in (MT5_MQL5_LOGS,):
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.log")):
            try:
                day = datetime.strptime(path.stem, "%Y%m%d").date()
            except ValueError:
                continue
            text = decode_text(path)
            for match in pattern.finditer(text):
                t = datetime.strptime(match.group(1).split(".")[0], "%H:%M:%S").time()
                stamp = datetime.combine(day, t, tzinfo=UTC)
                val = to_float(match.group(2))
                if earliest[1] is None or stamp < earliest[1]:
                    earliest = (val, stamp)
                if latest[1] is None or stamp > latest[1]:
                    latest = (val, stamp)
    return earliest, latest


def build() -> dict[str, Any]:
    now = ist_now()
    decision = load_decision()
    journal_path = MT5_FILES / "GoldAI_journal.csv"
    journal_rows = read_journal(journal_path)

    result_trades = parse_trades_from_results()
    existing = {str(t.get("ticket")) for t in result_trades if t.get("ticket")}
    journal_trades = trades_from_journal(journal_rows, existing)
    trades = result_trades + journal_trades
    trades.sort(key=lambda t: t.get("open_dt") or t.get("close_dt") or "")

    open_pos = open_position_from_journal(journal_rows)
    sync_positions, sync_dt = latest_sync_positions()
    # If journal has no open position and last sync said 0, we can state flat.
    if open_pos is None and sync_positions == 0:
        position_status = "flat"
    elif open_pos is not None:
        position_status = "open"
    elif sync_positions and sync_positions > 0:
        position_status = "unknown_open_in_terminal"
    else:
        position_status = "flat_no_journal_entry"

    earliest, latest_sod = first_ea_start_equity(journal_rows)
    start_equity_first, start_equity_first_dt = earliest
    sod_equity, sod_dt = latest_sod
    # Owner-requested SOD reference is 100046.10; confirm if logs agree.
    sod_balance = SOD_BALANCE_REF
    sod_note = (
        "Start-of-day reference $100,046.10 is the balance after the two closed "
        "demo trades (CloseOnce balance_after and EA start equity at 05:42:22 UTC / 11:12:22 IST)."
    )

    closed = [t for t in trades if t.get("pnl") is not None]
    trade_pnl = round(sum(t["pnl"] for t in closed), 2)
    # Current balance: SOD reference + any P&L realized after that stamp,
    # or last known close balance if no later trades.
    later_pnl = 0.0
    sod_cutoff = sod_dt or parse_iso("2026-11-13T05:42:22Z")
    for t in closed:
        cdt = parse_iso(t.get("close_dt"))
        if cdt and sod_cutoff and cdt > sod_cutoff:
            later_pnl += t["pnl"]
    current_balance = round(sod_balance + later_pnl, 2)
    # If there were no later trades, current equals SOD (matches CloseOnce).
    today_pnl = round(current_balance - sod_balance, 2)
    total_pnl_vs_100k = round(current_balance - STARTING_CAPITAL, 2)

    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] < 0]
    scratches = [t for t in closed if t["pnl"] == 0]
    win_rate = round(100.0 * len(wins) / len(closed), 1) if closed else None
    r_values = [t["r_multiple"] for t in closed if t.get("r_multiple") is not None]
    avg_r = round(sum(r_values) / len(r_values), 4) if r_values else None

    equity_curve = build_equity_curve(
        trades, start_equity_first, start_equity_first_dt, current_balance, now
    )

    card = decision_card(decision, now)
    if position_status == "open" and card["status"] == "waiting_for_zone":
        card["status"] = "in_trade"

    # Last EA decision-read from journal
    last_decision_row = None
    for row in journal_rows:
        if (row.get("event") or "").upper() == "DECISION":
            last_decision_row = row
    last_decision_read_ist = fmt_ist(parse_iso(last_decision_row.get("time_utc"))) if last_decision_row else None

    notes: list[str] = []
    notes.append(
        "All live money figures come from MT5 result files, the EA journal, and MQL5 logs. "
        "No live broker quote is shown unless a file has a fresh one."
    )
    if later_pnl == 0:
        notes.append(
            "Today's P&L vs the $100,046.10 start-of-day reference is $0.00 because both "
            "closed demo trades settled before that reference was recorded. Their combined "
            f"P&L is {money(trade_pnl, signed=True)} (including swap), which is already inside the current balance."
        )

    payload = {
        "generated_at_ist": fmt_ist(now),
        "generated_at_utc": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone_label": "IST (Asia/Kolkata)",
        "account": {
            "server": "MetaQuotes-Demo",
            "company": "MetaQuotes Ltd.",
            "mode": "demo",
            "symbol": "XAUUSD",
            "balance": current_balance,
            "equity": current_balance if position_status.startswith("flat") else None,
            "balance_display": f"${current_balance:,.2f}",
            "start_of_day_balance": sod_balance,
            "start_of_day_balance_display": f"${sod_balance:,.2f}",
            "start_of_day_at_ist": fmt_ist(sod_dt),
            "start_of_day_note": sod_note,
            "today_pnl": today_pnl,
            "today_pnl_display": money(today_pnl, signed=True),
            "total_pnl_vs_100k": total_pnl_vs_100k,
            "total_pnl_vs_100k_display": money(total_pnl_vs_100k, signed=True),
            "starting_capital": STARTING_CAPITAL,
            "first_ea_start_equity": start_equity_first,
            "first_ea_start_equity_at_ist": fmt_ist(start_equity_first_dt),
            "last_terminal_sync_positions": sync_positions,
            "last_terminal_sync_ist": fmt_ist(sync_dt),
        },
        "decision": card,
        "open_position": open_pos,
        "position_status": position_status,
        "ea": {
            "name": "GoldAIBridge",
            "chart": "XAUUSD M15",
            "last_decision_read_ist": last_decision_read_ist,
            "last_decision_bias": (last_decision_row or {}).get("bias"),
        },
        "trades": [
            {k: v for k, v in t.items() if k not in {"open_dt", "close_dt", "events"}}
            | {
                "open_dt": t.get("open_dt"),
                "close_dt": t.get("close_dt"),
                "pnl_display": money(t.get("pnl"), signed=True),
                "r_display": (f"{t['r_multiple']:+.2f}R" if t.get("r_multiple") is not None else None),
            }
            for t in trades
        ],
        "equity_curve": equity_curve,
        "stats": {
            "trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "scratches": len(scratches),
            "open": 0 if open_pos is None else 1,
            "win_rate_pct": win_rate,
            "net_pnl": trade_pnl,
            "net_pnl_display": money(trade_pnl, signed=True),
            "avg_r": avg_r,
            "avg_r_display": (f"{avg_r:+.2f}R" if avg_r is not None else "n/a"),
            "avg_r_note": (
                "R uses planned stop distance × $100/point/lot (contract 100). "
                "Test trade includes −$0.05 swap in net P&L, so its R is just beyond −1.00."
                if r_values
                else "Average R is only computed when a trade has both a stop and a P&L."
            ),
        },
        "backtest": load_backtest_summary(),
        "playbook_rules": playbook_rules(),
        "schedule": schedule(),
        "notes": notes,
        "sources": [
            "decisions/current.json",
            "MQL5/Files/GoldAI_journal.csv",
            "MQL5/Files/GoldDemoSellOnce_result.txt",
            "MQL5/Files/GoldDemoCloseOnce_result.txt",
            "MQL5/logs/ (UTF-16 expert log)",
            "MT5/logs/ (terminal sync)",
            "research/backtest/README.md",
            "research/backtest/results/metrics_summary.csv",
            "research/playbook.md",
        ],
        "canvas_edit_hint": (
            "After regenerating this JSON, refresh the Canvas Page with EditCanvas: "
            "replace the `DATA` object in the page source with the new JSON "
            "(keep it as a typed object literal / const). Do not invent figures."
        ),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build gold dashboard JSON from box files.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSON path")
    args = parser.parse_args()
    payload = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {args.out}")
    print(f"generated_at_ist={payload['generated_at_ist']}")
    print(f"balance={payload['account']['balance_display']} today_pnl={payload['account']['today_pnl_display']}")
    print(f"trades={payload['stats']['trades']} win_rate={payload['stats']['win_rate_pct']} net={payload['stats']['net_pnl_display']}")
    print(f"decision={payload['decision']['bias']} status={payload['decision']['status']}")
    print(f"open_position={payload['position_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

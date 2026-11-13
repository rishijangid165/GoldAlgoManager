#!/usr/bin/env python3
"""Validate and write a GoldAI decision file (decisions/current.json).

The MT5 EA polls this JSON and will only open a trade when price is inside
the entry zone and every hard risk rule still passes.

Examples
--------
# Flat / no-trade (safe default)
python scripts/write_decision.py --bias NONE --rationale "Waiting for PPI" --valid-hours 6

# A researched long
python scripts/write_decision.py \\
  --bias BUY \\
  --zone-low 3875 --zone-high 3892 \\
  --stop-loss 3848 --tp1 3920 --tp2 3965 \\
  --confidence 72 \\
  --rationale "Bounce attempt after CPI washout; invalid under 3848" \\
  --valid-hours 8 \\
  --news-blackout "2026-11-13T13:25:00Z,2026-11-13T14:15:00Z,US October PPI"

# Emergency flatten
python scripts/write_decision.py --bias NONE --kill-switch --rationale "Kill switch" --valid-hours 24
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "decisions" / "current.json"
VALID_BIAS = {"BUY", "SELL", "NONE"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_iso_utc(value: str, field: str) -> datetime:
    raw = (value or "").strip()
    if not raw:
        raise ValueError(f"{field} is empty")
    # Allow a space instead of T, and a missing Z
    text = raw.replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is not valid ISO-8601 UTC: {raw}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_blackout(item: str) -> dict[str, str]:
    # start,end,reason  — reason may itself contain commas
    parts = [p.strip() for p in item.split(",", 2)]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(
            "news blackout must be 'START,END' or 'START,END,REASON' "
            f"in UTC ISO, got: {item}"
        )
    start = parse_iso_utc(parts[0], "news_blackout.start")
    end = parse_iso_utc(parts[1], "news_blackout.end")
    if end <= start:
        raise ValueError(f"news_blackout end must be after start: {item}")
    reason = parts[2] if len(parts) > 2 else ""
    return {"start": to_iso_z(start), "end": to_iso_z(end), "reason": reason}


def validate_decision(d: dict[str, Any]) -> list[str]:
    """Return a list of error strings; empty means valid."""
    errors: list[str] = []

    version = d.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("version must be an integer >= 1")

    try:
        generated = parse_iso_utc(str(d.get("generated_at", "")), "generated_at")
    except ValueError as exc:
        generated = None
        errors.append(str(exc))

    try:
        valid_until = parse_iso_utc(str(d.get("valid_until", "")), "valid_until")
    except ValueError as exc:
        valid_until = None
        errors.append(str(exc))

    if generated is not None and valid_until is not None and valid_until <= generated:
        errors.append("valid_until must be after generated_at")

    symbol = d.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        errors.append("symbol must be a non-empty string")

    bias = d.get("bias")
    if bias not in VALID_BIAS:
        errors.append("bias must be BUY, SELL, or NONE")

    zone = d.get("entry_zone")
    if not isinstance(zone, dict):
        errors.append("entry_zone must be an object with low and high")
        zone_low = zone_high = None
    else:
        try:
            zone_low = float(zone["low"])
            zone_high = float(zone["high"])
        except (KeyError, TypeError, ValueError):
            zone_low = zone_high = None
            errors.append("entry_zone.low and entry_zone.high must be numbers")

    try:
        stop = float(d.get("stop_loss"))
    except (TypeError, ValueError):
        stop = None
        errors.append("stop_loss must be a number")

    tps = d.get("take_profits")
    tp_values: list[float] = []
    if not isinstance(tps, list) or len(tps) < 1:
        errors.append("take_profits must be an array with 1 or 2 numbers [tp1, tp2]")
    else:
        if len(tps) > 2:
            errors.append("take_profits may have at most two levels [tp1, tp2]")
        for i, item in enumerate(tps[:2]):
            try:
                tp_values.append(float(item))
            except (TypeError, ValueError):
                errors.append(f"take_profits[{i}] must be a number")

    conf = d.get("confidence")
    if not isinstance(conf, int) or isinstance(conf, bool) or not 0 <= conf <= 100:
        errors.append("confidence must be an integer 0-100")

    if "max_risk_pct" in d and d["max_risk_pct"] is not None:
        try:
            risk = float(d["max_risk_pct"])
            if risk < 0:
                errors.append("max_risk_pct cannot be negative")
        except (TypeError, ValueError):
            errors.append("max_risk_pct must be a number")

    if not isinstance(d.get("rationale"), str):
        errors.append("rationale must be a string")

    if not isinstance(d.get("kill_switch"), bool):
        errors.append("kill_switch must be a boolean")

    blackouts = d.get("news_blackout")
    if not isinstance(blackouts, list):
        errors.append("news_blackout must be an array")
    else:
        for i, window in enumerate(blackouts):
            if not isinstance(window, dict):
                errors.append(f"news_blackout[{i}] must be an object")
                continue
            try:
                start = parse_iso_utc(str(window.get("start", "")), f"news_blackout[{i}].start")
                end = parse_iso_utc(str(window.get("end", "")), f"news_blackout[{i}].end")
                if end <= start:
                    errors.append(f"news_blackout[{i}] end must be after start")
            except ValueError as exc:
                errors.append(str(exc))
            if "reason" in window and not isinstance(window.get("reason"), str):
                errors.append(f"news_blackout[{i}].reason must be a string")

    # Side-specific geometry — only enforced when we actually want a trade
    if bias in {"BUY", "SELL"}:
        if zone_low is not None and zone_high is not None:
            if zone_low >= zone_high:
                errors.append("entry_zone.low must be < entry_zone.high when bias is BUY or SELL")
            if stop is not None:
                if bias == "BUY" and not (stop < zone_low):
                    errors.append("BUY stop_loss must be strictly below entry_zone.low")
                if bias == "SELL" and not (stop > zone_high):
                    errors.append("SELL stop_loss must be strictly above entry_zone.high")
            if len(tp_values) >= 1 and zone_high is not None and zone_low is not None:
                tp1 = tp_values[0]
                if bias == "BUY" and not (tp1 > zone_high):
                    errors.append("BUY tp1 must be strictly above entry_zone.high")
                if bias == "SELL" and not (tp1 < zone_low):
                    errors.append("SELL tp1 must be strictly below entry_zone.low")
            if len(tp_values) >= 2:
                tp1, tp2 = tp_values[0], tp_values[1]
                # Allow tp2 == 0 as "not set"
                if tp2 != 0:
                    if bias == "BUY" and not (tp2 > tp1):
                        errors.append("BUY tp2 must be greater than tp1")
                    if bias == "SELL" and not (tp2 < tp1):
                        errors.append("SELL tp2 must be less than tp1")

        if isinstance(conf, int) and not isinstance(conf, bool) and conf <= 0:
            errors.append("confidence should be > 0 when bias is BUY or SELL")

    return errors


def build_decision(args: argparse.Namespace) -> dict[str, Any]:
    generated = (
        parse_iso_utc(args.generated_at, "generated_at") if args.generated_at else utc_now()
    )
    if args.valid_until:
        valid_until = parse_iso_utc(args.valid_until, "valid_until")
    else:
        valid_until = generated + timedelta(hours=args.valid_hours)

    tps: list[float] = []
    if args.tp1 is not None:
        tps.append(float(args.tp1))
    if args.tp2 is not None:
        if args.tp1 is None:
            raise ValueError("--tp2 requires --tp1")
        tps.append(float(args.tp2))
    if not tps:
        tps = [0.0, 0.0]

    zone_low = 0.0 if args.zone_low is None else float(args.zone_low)
    zone_high = 0.0 if args.zone_high is None else float(args.zone_high)
    stop = 0.0 if args.stop_loss is None else float(args.stop_loss)

    blackouts = [parse_blackout(item) for item in (args.news_blackout or [])]

    decision: dict[str, Any] = {
        "version": int(args.version),
        "generated_at": to_iso_z(generated),
        "valid_until": to_iso_z(valid_until),
        "symbol": args.symbol.strip(),
        "bias": args.bias.upper(),
        "entry_zone": {"low": zone_low, "high": zone_high},
        "stop_loss": stop,
        "take_profits": tps,
        "confidence": int(args.confidence),
        "max_risk_pct": float(args.max_risk_pct),
        "rationale": args.rationale,
        "news_blackout": blackouts,
        "kill_switch": bool(args.kill_switch),
    }
    return decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Validate and write decisions/current.json for the GoldAIBridge EA.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--bias", required=True, choices=["BUY", "SELL", "NONE", "buy", "sell", "none"])
    p.add_argument("--symbol", default="XAUUSD", help="Logical symbol (default XAUUSD)")
    p.add_argument("--zone-low", type=float, default=None, help="Entry zone low price")
    p.add_argument("--zone-high", type=float, default=None, help="Entry zone high price")
    p.add_argument("--stop-loss", type=float, default=None, help="Stop-loss price")
    p.add_argument("--tp1", type=float, default=None, help="Take-profit 1 (partial close)")
    p.add_argument("--tp2", type=float, default=None, help="Take-profit 2 (runner)")
    p.add_argument("--confidence", type=int, default=0, help="0-100 (EA default min is 60)")
    p.add_argument(
        "--max-risk-pct",
        type=float,
        default=0.5,
        help="Requested risk percent; EA will cap this at its own input",
    )
    p.add_argument("--rationale", default="", help="Short reason for the journal and chart panel")
    p.add_argument("--generated-at", default=None, help="UTC ISO timestamp; default is now")
    p.add_argument("--valid-until", default=None, help="UTC ISO expiry; overrides --valid-hours")
    p.add_argument("--valid-hours", type=float, default=6.0, help="Hours the decision stays valid")
    p.add_argument(
        "--news-blackout",
        action="append",
        default=[],
        help='UTC window "START,END,REASON" (repeatable)',
    )
    p.add_argument("--kill-switch", action="store_true", help="Force the EA to flatten and stand down")
    p.add_argument("--schema-version", type=int, default=1, dest="version", help="Schema version (default 1)")
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output path (default: {DEFAULT_OUT})",
    )
    p.add_argument("--stdout", action="store_true", help="Print JSON to stdout as well")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print, but do not write the file",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        decision = build_decision(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_decision(decision)
    text = json.dumps(decision, indent=2, ensure_ascii=False) + "\n"

    if errors:
        print("ERROR: decision failed validation:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        if args.stdout or args.dry_run:
            sys.stderr.write(text)
        return 2

    if args.stdout or args.dry_run:
        sys.stdout.write(text)
        sys.stdout.flush()

    if args.dry_run:
        print("Dry run: file not written.", file=sys.stderr)
        return 0

    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)
    print(
        f"bias={decision['bias']} valid_until={decision['valid_until']} "
        f"confidence={decision['confidence']} kill_switch={decision['kill_switch']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Summarize an exported GoldAIBridge trade journal CSV.

The EA writes this file to the terminal's MQL5/Files folder, usually:
  <Terminal Data Folder>/MQL5/Files/GoldAI_journal.csv

Copy it into this workspace (for example journal/GoldAI_journal.csv) and run:

  python scripts/review_journal.py journal/GoldAI_journal.csv

If no path is given, the script looks in a few common places under the repo.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FIELDS = [
    "time_utc",
    "event",
    "ticket",
    "symbol",
    "bias",
    "volume",
    "price",
    "sl",
    "tp1",
    "tp2",
    "profit",
    "confidence",
    "decision_generated_at",
    "rationale",
    "details",
]

SEARCH_PATHS = [
    REPO_ROOT / "journal" / "GoldAI_journal.csv",
    REPO_ROOT / "logs" / "GoldAI_journal.csv",
    REPO_ROOT / "GoldAI_journal.csv",
]


def to_float(value: str) -> float | None:
    text = (value or "").strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_rows(path: Path) -> list[dict[str, str]]:
    # utf-8-sig strips a BOM if MetaTrader wrote one
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no header row")
        rows: list[dict[str, str]] = []
        for raw in reader:
            row = {(k or "").strip(): (v if v is not None else "") for k, v in raw.items()}
            rows.append(row)
        return rows


def fmt_money(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}"


def summarize(rows: list[dict[str, str]]) -> str:
    lines: list[str] = []
    if not rows:
        return "Journal is empty. No events to review yet."

    events = Counter((r.get("event") or "").strip() or "(blank)" for r in rows)
    times = [r.get("time_utc", "").strip() for r in rows if r.get("time_utc", "").strip()]
    symbols = Counter((r.get("symbol") or "").strip() for r in rows if r.get("symbol", "").strip())

    lines.append("GoldAI journal review")
    lines.append("=" * 60)
    if times:
        lines.append(f"Period:     {times[0]}  ->  {times[-1]}")
    lines.append(f"Rows:       {len(rows)}")
    if symbols:
        symbol_txt = ", ".join(f"{name} ({count})" for name, count in symbols.most_common())
        lines.append(f"Symbols:    {symbol_txt}")
    lines.append("")
    lines.append("Events")
    lines.append("-" * 60)
    for name, count in events.most_common():
        lines.append(f"  {name:<22} {count}")

    exits = [r for r in rows if (r.get("event") or "").upper() in {"EXIT", "CLOSE", "KILL_CLOSE", "BIAS_FLIP_CLOSE"}]
    # Some journals may log DEAL_OUT as EXIT; also count PARTIAL profits
    partials = [r for r in rows if (r.get("event") or "").upper() in {"TP1_PARTIAL", "PARTIAL"}]
    entries = [r for r in rows if (r.get("event") or "").upper() in {"ENTRY", "OPEN"}]

    def profits(group: list[dict[str, str]]) -> list[float]:
        values = []
        for r in group:
            p = to_float(r.get("profit", ""))
            if p is not None:
                values.append(p)
        return values

    exit_pnl = profits(exits)
    partial_pnl = profits(partials)
    realized = exit_pnl + partial_pnl

    lines.append("")
    lines.append("Trades")
    lines.append("-" * 60)
    lines.append(f"  Entries:            {len(entries)}")
    lines.append(f"  Partial closes:     {len(partials)}")
    lines.append(f"  Full exits:         {len(exits)}")

    if realized:
        wins = [p for p in realized if p > 0]
        losses = [p for p in realized if p < 0]
        flats = [p for p in realized if p == 0]
        total = sum(realized)
        lines.append(f"  Realized P/L:       {fmt_money(total)}  (exits + partials)")
        denom = len(wins) + len(losses)
        win_rate = (100.0 * len(wins) / denom) if denom else 0.0
        lines.append(f"  Winners / losers:   {len(wins)} / {len(losses)}  (flat {len(flats)})")
        lines.append(f"  Win rate:           {win_rate:.1f}%  (of non-flat realized events)")
        if wins:
            lines.append(f"  Avg win:            {fmt_money(sum(wins) / len(wins))}")
        if losses:
            lines.append(f"  Avg loss:           {fmt_money(sum(losses) / len(losses))}")
        # Gross profit / gross loss
        gp = sum(wins)
        gl = abs(sum(losses))
        if gl > 0:
            lines.append(f"  Profit factor:      {gp / gl:.2f}")
        by_bias: dict[str, float] = defaultdict(float)
        bias_count: dict[str, int] = defaultdict(int)
        for r in exits + partials:
            p = to_float(r.get("profit", ""))
            if p is None:
                continue
            bias = (r.get("bias") or "").upper() or "?"
            by_bias[bias] += p
            bias_count[bias] += 1
        if by_bias:
            lines.append("  By bias:")
            for bias, pnl in sorted(by_bias.items()):
                lines.append(f"    {bias:<6} {fmt_money(pnl):>10}   ({bias_count[bias]} events)")
    else:
        lines.append("  No realized profit fields found on EXIT / TP1_PARTIAL rows yet.")

    # Rejects and blocks — useful for the AI review loop
    reject_like = [
        r
        for r in rows
        if (r.get("event") or "").upper()
        in {
            "REJECT",
            "STALE",
            "BLACKOUT",
            "KILL",
            "DAILY_LOSS",
            "SPREAD",
            "LOW_CONFIDENCE",
            "SYMBOL_MISMATCH",
            "POLL_ERROR",
            "PARSE_ERROR",
        }
    ]
    if reject_like:
        lines.append("")
        lines.append("Blocks / rejects")
        lines.append("-" * 60)
        reasons = Counter()
        for r in reject_like:
            ev = (r.get("event") or "").upper()
            details = (r.get("details") or r.get("rationale") or "").strip()
            key = ev if not details else f"{ev}: {details}"
            reasons[key] += 1
        for key, count in reasons.most_common(15):
            lines.append(f"  {count:>3}  {key}")
        if len(reasons) > 15:
            lines.append(f"  ... {len(reasons) - 15} more reason(s)")

    # Last few trade-related rows, so a human can skim
    interesting = [
        r
        for r in rows
        if (r.get("event") or "").upper()
        in {
            "ENTRY",
            "OPEN",
            "TP1_PARTIAL",
            "PARTIAL",
            "BE_MOVE",
            "EXIT",
            "CLOSE",
            "KILL_CLOSE",
            "BIAS_FLIP_CLOSE",
            "DECISION",
            "KILL",
        }
    ]
    tail = interesting[-10:]
    if tail:
        lines.append("")
        lines.append("Latest trade-related events")
        lines.append("-" * 60)
        for r in tail:
            profit = to_float(r.get("profit", ""))
            profit_txt = f"  pnl={fmt_money(profit)}" if profit is not None else ""
            rationale = (r.get("rationale") or r.get("details") or "").replace("\n", " ").strip()
            if len(rationale) > 80:
                rationale = rationale[:77] + "..."
            extra = f"  {rationale}" if rationale else ""
            lines.append(
                f"  {r.get('time_utc', ''):<22} {r.get('event', ''):<16} "
                f"{r.get('bias', ''):<5} {r.get('volume', ''):>8} @ {r.get('price', '')}"
                f"{profit_txt}{extra}"
            )

    lines.append("")
    lines.append("Note: this is a journal summary, not a full backtest. Copy the CSV")
    lines.append("out of MT5 (File > Open Data Folder > MQL5/Files) after each session.")
    return "\n".join(lines) + "\n"


def resolve_path(cli_path: str | None) -> Path:
    if cli_path:
        path = Path(cli_path).expanduser()
        if not path.is_absolute():
            # try as given, then relative to repo
            if not path.exists() and (REPO_ROOT / path).exists():
                path = REPO_ROOT / path
        return path
    for candidate in SEARCH_PATHS:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No journal CSV found. Pass the path explicitly, or copy "
        "GoldAI_journal.csv into gold-algo/journal/."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize a GoldAIBridge journal CSV.")
    p.add_argument("csv_path", nargs="?", help="Path to GoldAI_journal.csv")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        path = resolve_path(args.csv_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2
    try:
        rows = load_rows(path)
    except Exception as exc:  # noqa: BLE001 — show a clean CLI error
        print(f"ERROR: could not read {path}: {exc}", file=sys.stderr)
        return 2
    print(f"File: {path}  ({len(rows)} rows)")
    sys.stdout.write(summarize(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())

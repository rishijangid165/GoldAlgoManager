"""Pull the longest GC=F / DXY history Yahoo Finance will serve and write data/raw/.

yfinance limits (as of this pull): daily period=max; 1h ~730d; 15m ~60d.
Raw CSVs are replaced in full, never edited in place. A pull log is written
under logs/. The last daily bar may still be an in-progress session.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
LOGS = ROOT / "logs"

PULLS = [
    ("GC=F", "max", "1d", "GC=F_daily.csv", "Date"),
    ("GC=F", "730d", "1h", "GC=F_1h.csv", "Datetime"),
    ("GC=F", "60d", "15m", "GC=F_15m.csv", "Datetime"),
    ("DX-Y.NYB", "max", "1d", "DX-Y.NYB_daily.csv", "Date"),
]


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def download_one(ticker: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
        group_by="column",
    )
    if df is None or df.empty:
        raise RuntimeError(f"empty download: {ticker} {interval} {period}")
    df = _flatten(df)
    df = df.rename(columns={c: str(c) for c in df.columns})
    # Keep a stable column order
    cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in df.columns]
    df = df[cols].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def save_csv(df: pd.DataFrame, path: Path, index_name: str) -> None:
    out = df.copy()
    out.index.name = index_name
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, date_format="%Y-%m-%d %H:%M:%S%z" if index_name == "Datetime" else None)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    report = {
        "pulled_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "yfinance",
        "note": "GC=F is COMEX gold futures, not broker spot XAUUSD. Last daily bar may be in-progress.",
        "series": [],
    }
    for ticker, period, interval, filename, index_name in PULLS:
        df = download_one(ticker, period, interval)
        path = RAW / filename
        save_csv(df, path, index_name)
        start = df.index.min()
        end = df.index.max()
        entry = {
            "ticker": ticker,
            "interval": interval,
            "period_requested": period,
            "file": str(path.relative_to(ROOT)),
            "rows": int(len(df)),
            "start": str(start),
            "end": str(end),
            "columns": list(df.columns),
        }
        report["series"].append(entry)
        print(f"wrote {path}  rows={len(df)}  {start} -> {end}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    log_path = LOGS / f"data-pull-{stamp}.json"
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"log {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

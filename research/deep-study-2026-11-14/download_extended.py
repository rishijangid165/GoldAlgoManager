#!/usr/bin/env python3
"""Download the longest free gold history we can get without a login.

Sources attempted
-----------------
1. Yahoo Finance / yfinance — COMEX GC=F daily (period=max, from 2000),
   1h (~730d cap), 15m and 5m (~60d cap); DXY daily. Already pulled by
   research/backtest/download_data.py; this script can refresh them.
2. HistData.com — spot XAUUSD 1-minute ASCII bars, annual zips 2006–2025
   and monthly zips for the current year. Public POST to /get.php after
   fetching a one-time token from the download page. No account required.
3. Dukascopy public datafeed — XAUUSD tick / candle .bi5 (from ~2003).
   Attempted; recorded if the feed is up. Not required if HistData works.
4. Stooq — gold futures daily. Attempted; often blocked by a JS challenge.

Timezone (HistData): wall-clock timestamps with the COMEX daily break at
17:00–18:00 in both January and July, so they are America/New_York (DST
aware), not fixed EST. We localize them that way after download.

Raw zips stay in data/raw/histdata/zips/. Resampled bars are written by
dataset.py. Do not edit vendor files in place.
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
LOGS = ROOT / "logs"
HD_ZIPS = RAW / "histdata" / "zips"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HISTDATA_PAGE = (
    "https://www.histdata.com/download-free-forex-historical-data/"
    "?/ascii/1-minute-bar-quotes/xauusd/{suffix}"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def histdata_targets() -> list[tuple[str, str, Path]]:
    """(label, page suffix, zip path) for 2003–current year."""
    out: list[tuple[str, str, Path]] = []
    this_year = datetime.now(timezone.utc).year
    this_month = datetime.now(timezone.utc).month
    # Probe early years; 2003–2005 may 404/empty and are skipped if no form.
    for year in range(2003, this_year):
        out.append((f"{year}", str(year), HD_ZIPS / f"HISTDATA_COM_ASCII_XAUUSD_M1_{year}.zip"))
    # Current year: monthly files, more up to date than a partial annual zip.
    for month in range(1, this_month + 1):
        suffix = f"{this_year}/{month:02d}"
        stamp = f"{this_year}{month:02d}"
        out.append((stamp, suffix, HD_ZIPS / f"HISTDATA_COM_ASCII_XAUUSD_M1_{stamp}.zip"))
    return out


def _parse_form(html: str) -> dict[str, str] | None:
    m = re.search(r'<form id="file_down".*?</form>', html, re.S | re.I)
    if not m:
        return None
    fields: dict[str, str] = {}
    for name, val in re.findall(r'name="([^"]+)"[^>]*value="([^"]*)"', m.group(0)):
        fields[name] = val
    for val, name in re.findall(r'value="([^"]*)"[^>]*name="([^"]+)"', m.group(0)):
        fields.setdefault(name, val)
    if "tk" not in fields or "fxpair" not in fields:
        return None
    return fields


def download_histdata_one(suffix: str, dest: Path, timeout: int = 120) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    page_url = HISTDATA_PAGE.format(suffix=suffix)
    if dest.exists() and dest.stat().st_size > 1000:
        # Re-download current-year monthly files so we pick up new days.
        is_current_month = "/2026/" in f"/{suffix}" or suffix.count("/") == 1 and suffix.startswith("2026")
        if not is_current_month:
            return {"status": "cached", "path": str(dest.relative_to(ROOT)), "bytes": dest.stat().st_size}

    r = SESSION.get(page_url, timeout=30)
    r.raise_for_status()
    fields = _parse_form(r.text)
    if not fields:
        return {"status": "no_form", "url": page_url, "http": r.status_code, "bytes": len(r.content)}

    headers = {"Referer": page_url, "Content-Type": "application/x-www-form-urlencoded"}
    post = SESSION.post(
        "https://www.histdata.com/get.php",
        data=urlencode(fields),
        headers=headers,
        timeout=timeout,
    )
    post.raise_for_status()
    body = post.content
    if len(body) < 1000 or body[:2] != b"PK":
        return {
            "status": "not_zip",
            "http": post.status_code,
            "ctype": post.headers.get("Content-Type"),
            "bytes": len(body),
            "head": body[:80].decode("latin1", "replace"),
        }
    tmp = dest.with_suffix(".zip.part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return {"status": "ok", "path": str(dest.relative_to(ROOT)), "bytes": len(body), "fields": {k: fields[k] for k in fields if k != "tk"}}


def download_all_histdata(pause: float = 1.8) -> list[dict]:
    results = []
    for label, suffix, dest in histdata_targets():
        entry: dict = {"label": label, "suffix": suffix, "pulled_at": _now()}
        try:
            entry.update(download_histdata_one(suffix, dest))
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
        print(f"histdata {label}: {entry.get('status')} {entry.get('bytes', '')} {entry.get('error', '')}")
        results.append(entry)
        time.sleep(pause + random.uniform(0, 0.6))
    return results


def probe_dukascopy() -> dict:
    """Single polite probe of the public datafeed (candles + ticks)."""
    urls = {
        "m1_candle_2023-06-01": "https://datafeed.dukascopy.com/datafeed/XAUUSD/2023/05/01/BID_candles_min_1.bi5",
        "tick_2023-06-01-12h": "https://datafeed.dukascopy.com/datafeed/XAUUSD/2023/05/01/12h_ticks.bi5",
    }
    out = {"status": "down", "urls": {}}
    for name, url in urls.items():
        try:
            r = SESSION.get(url, timeout=25)
            entry = {"http": r.status_code, "bytes": len(r.content), "ctype": r.headers.get("Content-Type")}
            if r.status_code == 200 and len(r.content) > 100 and not r.content.startswith(b"<html"):
                entry["looks_binary"] = True
                out["status"] = "up"
            else:
                entry["head"] = r.content[:120].decode("latin1", "replace")
            out["urls"][name] = entry
        except Exception as exc:
            out["urls"][name] = {"error": f"{type(exc).__name__}: {exc}"}
        time.sleep(1.0)
    return out


def probe_stooq() -> dict:
    url = "https://stooq.com/q/d/l/?s=gc.f&i=d"
    try:
        r = SESSION.get(url, timeout=20)
        text = r.text[:200]
        csv = r.status_code == 200 and ("Date" in r.text or "date" in r.text[:50]) and "<html" not in r.text.lower()
        return {"http": r.status_code, "bytes": len(r.content), "csv": csv, "head": text}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def maybe_refresh_yahoo() -> dict:
    """Refresh Yahoo series if the official downloader is present."""
    try:
        from research.backtest import download_data as yd

        # Only refresh if daily history looks truncated (< 1000 rows).
        daily = RAW / "GC=F_daily.csv"
        need = True
        if daily.exists():
            n = sum(1 for _ in daily.open()) - 1
            need = n < 1000
        if not need:
            return {"status": "skipped_already_full"}
        yd.main()
        return {"status": "refreshed"}
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    HD_ZIPS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    report = {
        "pulled_at_utc": _now(),
        "note": (
            "GC=F is COMEX futures (Yahoo). XAUUSD M1 is HistData spot ASCII. "
            "Dukascopy/Stooq are probed only. Tokens from HistData pages are not stored."
        ),
        "histdata": download_all_histdata(),
        "dukascopy_probe": probe_dukascopy(),
        "stooq_probe": probe_stooq(),
        "yahoo_refresh": maybe_refresh_yahoo(),
    }
    ok = [e for e in report["histdata"] if e.get("status") in {"ok", "cached"}]
    fail = [e for e in report["histdata"] if e.get("status") not in {"ok", "cached"}]
    report["histdata_ok"] = len(ok)
    report["histdata_failed"] = [{"label": e["label"], "status": e.get("status"), "error": e.get("error")} for e in fail]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    path = LOGS / f"data-pull-extended-{stamp}.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"histdata ok={len(ok)} failed={len(fail)}")
    print(f"dukascopy {report['dukascopy_probe'].get('status')}")
    print(f"log {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

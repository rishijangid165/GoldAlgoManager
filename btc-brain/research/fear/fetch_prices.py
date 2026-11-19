#!/usr/bin/env python3
"""Fetch Binance BTCUSDT daily klines (public, no auth) from 2018 and save btc_daily.csv."""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "btc_daily.csv"
START_MS = 1514764800000  # 2018-01-01 00:00 UTC
URL = "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime={s}&limit=1000"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "btc-brain-fear-study/1.0 (research; no-auth)"})
    err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"binance fetch failed: {err}")


def main():
    rows = []
    s = START_MS
    now_ms = int(time.time() * 1000)
    while s < now_ms:
        batch = fetch(URL.format(s=s))
        if not batch:
            break
        rows.extend(batch)
        s = batch[-1][0] + 86400_000
        print(f"through {time.strftime('%Y-%m-%d', time.gmtime(batch[-1][0]/1000))} n={len(rows)}")
        time.sleep(0.2)
    completed = {}
    for r in rows:
        if r[6] < now_ms:
            completed[int(r[0])] = r
    ks = sorted(completed)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "open_time", "open", "high", "low", "close", "volume"])
        for k in ks:
            r = completed[k]
            w.writerow([
                time.strftime("%Y-%m-%d", time.gmtime(k / 1000)),
                k // 1000, r[1], r[2], r[3], r[4], r[5],
            ])
    print(f"wrote {OUT} n={len(ks)} {time.strftime('%Y-%m-%d', time.gmtime(ks[0]/1000))} -> {time.strftime('%Y-%m-%d', time.gmtime(ks[-1]/1000))}")


if __name__ == "__main__":
    main()

# Raw data

Do not edit these CSVs in place. Re-pull and replace, or write derivatives under `data/processed/`.

## Sources (pull 2026-11-13 / 14 IST)

| File | Source | Interval | Rows (approx.) | Range | Notes |
|------|--------|----------|----------------|-------|-------|
| `GC=F_daily.csv` | Yahoo Finance / yfinance, ticker `GC=F` | 1d | 6,578 | 2000-08-30 to 2026-11-13 | COMEX gold futures, `period=max`. Last daily bar may be in-progress. |
| `GC=F_1h.csv` | yfinance `GC=F` | 1h | 13,752 | 2024-06-24 to 2026-11-13 13:00 ET | Yahoo cap ~730d. |
| `GC=F_15m.csv` | yfinance `GC=F` | 15m | 4,542 | 2026-09-04 to 2026-11-13 13:15 ET | Yahoo cap ~60d. |
| `GC=F_5m.csv` | yfinance `GC=F` | 5m | 13,586 | 2026-09-04 to 2026-11-13 13:20 ET | Yahoo cap ~60d. Added 2026-11-13. |
| `DX-Y.NYB_daily.csv` | yfinance `DX-Y.NYB` | 1d | 14,186 | 1971-01-04 to 2026-11-13 | Dollar Index, context only. |
| `histdata/XAUUSD_{5m,15m,1h,daily}.csv.gz` | HistData.com ASCII M1, resampled | 5m–1d | see below | 2009-03-15 to 2026-11-06 | **Spot** XAUUSD. Primary long-history series for the 2026-11-14 deep study. |

HistData M1 zips (2009–2025 annual, 2026 monthly) live in `histdata/zips/` and are not committed (rebuild with `research/deep-study-2026-11-14/download_extended.py`). M1 starts 2009-03-15 17:00 ET; the 2026 November zip on HistData was only current through 2026-11-06. Resampled bars: 5m 1,246,151; 15m 416,465; 1h 104,989; session-daily 4,598.

Timestamps on HistData are America/New_York wall clocks (the COMEX daily break sits at 17:00–18:00 in both January and July). Session daily bars use the same COMEX session date as `research/backtest/data.py` (18:00 ET onward belongs to the next date).

**Not available without a login / at the time of this pull:**

- Yahoo `XAUUSD=X` — HTTP 404 / “possibly delisted.”
- HistData XAUUSD M1 for 2003–2008 — download pages show a form, but `/get.php` returned an empty body.
- Stooq `gc.f` daily — JS browser challenge, no CSV.
- Dukascopy public datafeed (`datafeed.dukascopy.com`) has M1 candle `.bi5` files for XAUUSD from at least 2003-05-05, which would fill 2003–2008 and 2026-11-07..13. The feed was intermittent (503 / TLS EOF) during this pull, so those years were **not** ingested. A later retry is worthwhile.
- BLS CPI/PPI release calendars — HTTP 403. The news study therefore uses FOMC (Fed pages) and NFP (first-Friday proxy) only.

`GC=F` is typically above broker spot, and the gap jumps around futures rolls (see the deep-study basis section). Do not treat a futures print as a Kitco / FX Street / broker spot print.

Re-pull Yahoo:

```bash
source /workspace/gold-algo/.venv/bin/activate
python /workspace/gold-algo/research/backtest/download_data.py
```

Re-pull HistData zips and rebuild resampled bars:

```bash
python /workspace/gold-algo/research/deep-study-2026-11-14/download_extended.py
python /workspace/gold-algo/research/deep-study-2026-11-14/dataset.py
```

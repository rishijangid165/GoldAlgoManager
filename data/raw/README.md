# Raw data

Do not edit these CSVs in place. Re-pull and replace, or write derivatives under `data/processed/`.

Latest full pull: `logs/data-pull-2026-11-13T0604Z.json` (Yahoo Finance / yfinance).

| File | Source | Interval | Rows | Range | Notes |
|------|--------|----------|------|------:|-------|
| `GC=F_daily.csv` | yfinance, ticker `GC=F` | 1d | 6,578 | 2000-08-30 to 2026-11-13 | COMEX gold futures, `period=max`. The last daily bar may be an in-progress session. |
| `GC=F_1h.csv` | yfinance, ticker `GC=F` | 1h | 13,738 | 2024-06-24 00:00 ET to 2026-11-13 00:00 ET | Yahoo cap is about `730d`. |
| `GC=F_15m.csv` | yfinance, ticker `GC=F` | 15m | 4,487 | 2026-09-04 00:00 ET to 2026-11-13 00:45 ET | Yahoo cap is about `60d`. |
| `DX-Y.NYB_daily.csv` | yfinance, ticker `DX-Y.NYB` | 1d | 14,186 | 1971-01-04 to 2026-11-13 | US Dollar Index, context only. |

**Not available:** `XAUUSD=X` daily and intraday — Yahoo returns HTTP 404 / “possibly delisted.” `GC=F` is typically a few dollars above broker spot. Do not treat a futures print as a Kitco/FX Street/broker spot print.

Re-pull:

```bash
source /workspace/gold-algo/.venv/bin/activate
python /workspace/gold-algo/research/backtest/download_data.py
```

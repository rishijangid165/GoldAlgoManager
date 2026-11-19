# Candle data

Historical BTC candles used for training backtests. Files are **gzipped** because this GitHub repo is public and we want the tree to stay light.

## Layout

- `v1/btc_1h.csv.gz`, `v1/btc_4h.csv.gz` — Delta India `BTCUSD` perpetual, about 3 months, used by `research/v1/`.
- `advanced/delta_15m.csv.gz`, `delta_1h.csv.gz`, `delta_4h.csv.gz`, `delta_1d.csv.gz` — Delta India `BTCUSD`, about 12 months, used by `research/advanced/`.
- `advanced/binance_1h.csv.gz` — Binance `BTCUSDT` 1H, used only as a data-quality cross-check.

## Unpack before rerunning scripts

The Python scripts expect plain `.csv` files in their working directory (not in this `data/` folder).

```bash
# from the GoldAlgoManager repo root
gunzip -ck btc-brain/data/v1/btc_1h.csv.gz > /tmp/btc-v1/btc_1h.csv
# or:
cd btc-brain/research/v1
gunzip -ck ../../data/v1/btc_1h.csv.gz > btc_1h.csv
gunzip -ck ../../data/v1/btc_4h.csv.gz > btc_4h.csv
# then: python3 analyze.py
# do not commit the unpacked CSVs
```

Do the same for `research/advanced/` with the `data/advanced/*.csv.gz` files (`delta_15m.csv`, `delta_1h.csv`, `delta_4h.csv`, `delta_1d.csv`, `binance_1h.csv`).

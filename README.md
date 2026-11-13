# Gold Algo (XAU/USD)

A gold-only workspace for researching, backtesting, and (eventually) running an algorithmic trading indicator/bot on **XAU/USD** (and tightly related gold futures). No other asset classes belong here except supporting series used to explain gold (e.g. DXY, yields).

Owner: Rishi Jangid.

## Layout

```
gold-algo/
  README.md                 This file
  requirements.txt          Pinned Python dependencies
  .venv/                    Local virtualenv (not committed)
  data/
    raw/                    Immutable vendor pulls (Yahoo Finance CSVs)
    processed/              Cleaned/derived features for research & backtests
  research/
    daily-notes/            YYYY-MM-DD.md market snapshots
    strategy-ideas/         Written hypotheses before any code
  strategies/
    backtests/              Historical tests and reports
    live-candidates/        Strategies that cleared research gates
  indicators/               Indicator definitions and code
  news/                     Saved articles, clippings, or source PDFs
  logs/                     Pull reports, run logs
  journal/
    learning-log.md         Lessons, mistakes, and process notes
  mql5/
    Experts/GoldAIBridge.mq5   MT5 EA: polls the AI decision file and executes
    Include/                   JSON parser, decision helpers, journal
    docs/SETUP.md              How to install the EA on a DEMO account
  decisions/
    current.json            Living decision file the EA polls (starts at bias NONE)
  scripts/
    write_decision.py       Validate and write current.json
    review_journal.py       Summarize an exported GoldAI journal CSV
```


## MT5 AI-directed trading (v1.02)

The assistant researches gold and writes `decisions/current.json`. The MetaTrader 5 EA `mql5/Experts/GoldAIBridge.mq5` polls that file (WebRequest or a local file) and will only open a trade when price is inside the AI entry zone. Hard risk caps stay locked in the EA. Demo only by default.

v1.02 adds a Friday auto-close before the weekly gold close (and a no-entry cutoff ahead of it) plus a structure/ATR trailing stop on the remaining half after TP1. Both are described in `mql5/docs/SETUP.md`.

Install steps, inputs, and hosting notes: `mql5/docs/SETUP.md`.

Write a decision:

```bash
source /workspace/gold-algo/.venv/bin/activate
python /workspace/gold-algo/scripts/write_decision.py --bias NONE \
  --rationale "Waiting for the next window" --valid-hours 6
```

Review a journal CSV exported from `MQL5/Files/GoldAI_journal.csv`:

```bash
python /workspace/gold-algo/scripts/review_journal.py /path/to/GoldAI_journal.csv
```

The decision-file URL the EA polls is still a placeholder. A public GitHub raw URL or gist is the recommended host; this needs a decision before the EA can poll over the internet.

## Environment

Python 3.13 virtualenv at `.venv`. Activate with:

```bash
source /workspace/gold-algo/.venv/bin/activate
```

Installed (2026-11-12) and listed in `requirements.txt`:

| Package       | Version |
|---------------|---------|
| pandas        | 3.1.1   |
| numpy         | 2.5.4   |
| yfinance      | 1.8.0   |
| matplotlib    | 3.11.2  |
| backtesting   | 0.6.6   |

`backtesting` installed cleanly, so `vectorbt` was not needed.

## Data conventions

- **Raw is read-only.** Re-pull into `data/raw/` rather than editing a CSV by hand. Derived work goes in `data/processed/`.
- Primary gold series is COMEX gold futures **`GC=F`** via Yahoo Finance (`yfinance`). Filename pattern: `{SYMBOL}_{interval}.csv`.
- **`XAUUSD=X` was not available** on Yahoo Finance as of the 2026-11-12 pull (HTTP 404 / “possibly delisted”). Do not invent a substitute and label it `XAUUSD=X`. If a reliable spot series is added later, document the ticker and vendor in this README and in the pull log.
- `DX-Y.NYB_daily.csv` is an optional US Dollar Index series pulled for snapshot context, not a trading instrument for this project.
- Daily notes must compute prices, returns, moving averages, and ATR from files in `data/raw/` (or `processed/`). News-reported prints may be quoted only with a source link and must be labeled as news, not as our data.
- Never invent numbers. If a figure cannot be found or a series is missing, say so.

## Research and strategy conventions

- Daily notes live at `research/daily-notes/YYYY-MM-DD.md`.
- Write the idea in `research/strategy-ideas/` before implementing a backtest.
- The first structured backtest and the live playbook live at `research/backtest/` and `research/playbook.md` (playbook revised 2026-11-14 after a walk-forward on 2009–2026 spot data; see `research/deep-study-2026-11-14/REPORT.md`). Trade CSVs and equity curves are under `research/backtest/results/` and `figures/`.
- Older convention: backtests also belong in `strategies/backtests/`. Promote only after a written review into `strategies/live-candidates/`.
- Indicator code belongs in `indicators/`, not mixed into ad-hoc notebook cells that never get checked in.
- Record mistakes, regime notes, and process changes in `journal/learning-log.md`.

## First data pull (2026-11-12)

Original stand-up pull: `logs/data-pull-2026-11-12.json`. Expanded pull 2026-11-13 (`logs/data-pull-2026-11-13T0604Z.json`): `GC=F` daily 2000-08-30 to 2026-11-13 (`period=max`), 1-hour 2024-06-24 to 2026-11-13 (Yahoo `730d` cap), 15-minute 2026-09-04 to 2026-11-13 (`60d` cap). Failed then and now: `XAUUSD=X`. Details in `data/raw/README.md`.

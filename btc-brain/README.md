# btc-brain — BTC Monitor training memory

**English:** This folder is the long-term training brain for BTC Monitor. It stores trading rules, backtest research, candle data, the paper-trade journal, and weekly/monthly reviews.

**Hinglish:** Ye folder BTC Monitor ki training ka dimaag hai. Isme rules, purane test ke nateeje, chart data, paper trades ka journal, aur hafte/mahine ki reports rehti hain.

Ye folder `rishijangid165/GoldAlgoManager` ke andar hai, lekin **gold trading se alag** hai. Is folder ka kaam `btc/` (MT5 EA), `mql5/`, `decisions/`, ya koi gold file change karna nahi hai.

> **This GitHub repository is PUBLIC.** Never commit passwords, tokens, API keys, Telegram chat IDs, or account numbers. Is repo mein kabhi secret mat daalna.

## Current status / Abhi ki halat

- **No strategy has a proven edge. Koi strategy ka fayda abhi saabit nahi hua.**
- The 3-month v1 backtest and the 12-month advanced tests (with estimated XM costs) were **loss-making**. Details are in `research/`.
- **Live trading is on hold.** Real alerts and the XM EA stay off.
- **Paper trading is data collection only.** Telegram messages are marked so that real money should not be used on them.
- **Real orders only with Rishi's explicit "haan" / yes.** Never say "guaranteed" or "pakka profit".

## Folder map

| Path | What is here |
|---|---|
| `rules/` | Trading and discipline rules, training phases, and live pass criteria |
| `research/v1/` | First 3-month strategy, backtest report, trade list, and scripts |
| `research/advanced/` | 12-month three-strategy test, walk-forward, stress test, and risk engine |
| `data/` | Historical candle CSVs (gzipped). Unpack before rerunning scripts. |
| `paper/` | Paper trade log, journal, lessons, and synced alert levels (no secrets) |
| `reviews/weekly/` | Sunday reviews (empty until the first weekly report) |
| `reviews/monthly/` | Monthly exams (empty until the first month-end exam) |
| `sync.sh` | Copies the latest paper-trade file and alert levels into `paper/`, then commits and pushes if anything changed |

## How to sync

From this folder, with `GOLDALGO_GITHUB_TOKEN` already set in the environment (do not paste the token into a file or into chat):

```bash
./sync.sh
```

The script only touches files under `btc-brain/`. If nothing changed, it does not create an empty commit.

## Pass criteria before live or XM demo EA

All of these are required. If even one fails, do not go live:

- Positive expectancy
- Profit factor at least 1.3
- Max drawdown under 10%
- Test-window result similar to the training window
- Paper results close to the backtest
- At least 50 paper trades over 4 or more weeks
- Then ask Rishi: "XM demo EA par test shuru karein?" and wait for "haan"

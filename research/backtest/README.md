# Gold setup backtests (GC=F)

Rule-based approximations of the discretionary XAUUSD process: multi-timeframe structure, a hard 0.5% risk cap, one trade at a time, TP1 at 1.5R (half off, stop to breakeven) and TP2 at 3R or the next structure level.

This is **not** a full recreation of a human chart read. It measures whether the *shape* of each idea had a positive expectancy on COMEX gold futures after costs.

## How to rerun

From the repo root, with `.venv` active:

```bash
python research/backtest/download_data.py   # refreshes data/raw/ (Yahoo limits below)
python research/backtest/run_backtest.py    # writes results/ and figures/
```

| File | Role |
|------|------|
| `config.py` | Costs, risk, session hours, zone/stop parameters |
| `download_data.py` | Max-history Yahoo pull into `data/raw/` |
| `data.py` | Load, 4H resample, COMEX session tags |
| `features.py` | ATR, RSI, confirmed swings, no-lookahead higher-TF mapping |
| `setups.py` | Pullback, sweep, Asia breakout, RSI mean-reversion, combos |
| `engine.py` | Event-driven fills, costs, 2% daily loss stop |
| `metrics.py` / `run_backtest.py` | Summaries, trade CSVs, equity curves |

## Data (pull 2026-11-13 06:04 UTC)

Yahoo Finance does not serve `XAUUSD=X`. The series is COMEX **`GC=F`**, typically a few dollars above broker spot. Do not treat a futures print as a spot level.

| Series | Interval | Rows | Range | Limit |
|--------|----------|------|-------|-------|
| `GC=F` | daily | 6,578 | 2000-08-30 → 2026-11-13 | `period=max` (last daily bar is in-progress; dropped in the backtest) |
| `GC=F` | 1h | 13,738 | 2024-06-24 00:00 ET → 2026-11-13 00:00 ET | Yahoo cap ~730d |
| `GC=F` | 15m | 4,487 | 2026-09-04 00:00 ET → 2026-11-13 00:45 ET | Yahoo cap ~60d |
| `DX-Y.NYB` | daily | 14,186 | 1971-01-04 → 2026-11-13 | context only; not used in these tests |

4H bars are resampled from 1h, aligned to the COMEX session: **18:00, 22:00, 02:00, 06:00, 10:00, 14:00 ET** (`resample('4h', offset='2h')`). The 14:00 bar covers 14:00–17:00 ET only.

**Primary sample:** 1h bars after indicator warmup, 2024-07-07 18:00 ET → 2026-11-13 00:00 ET (13,556 bars, about 28 months). This window includes the 2024–early 2026 bull and the 2026 selloff (high near $5,586 in Jan 2026, later a 2026 low near $3,857). Trend-up bars outnumber trend-down bars, so with-trend **sell** samples are small.

**15m sample:** 2026-09-04 → 2026-11-13 only, and almost entirely a downtrend. It is a robustness check, not a second independent test. It must not override the 1h conclusions.

## Method (anti look-ahead)

- Daily and 4H features are mapped onto an execution bar only after that higher-TF bar has **closed**. Confirmed swings use a symmetric window and are stamped at the confirmation bar (`i+n`), then forward-filled.
- Signals fire at the execution bar's **close**. Entry is the **next bar's open**, plus half-spread and slippage.
- Stops and targets are managed on that bar's OHLC. If a stop and a target both sit inside the same bar, the engine assumes the **stop is hit first** (conservative). Open gaps through a level are filled at the gapped open, with costs.
- The last in-progress daily bar is dropped. The run does not use future bars to size, place, or exit a trade.

### Costs and risk

| Item | Value |
|------|-------|
| Spread | $0.25 / oz |
| Slippage | $0.10 / oz on every fill (entry and exit) |
| Risk | 0.5% of current equity, $100,000 start, 0.01 lot step, 100 oz per lot |
| Daily loss stop | no new entries after −2% realized P&L on the session |
| One position | at most one open trade |
| TP1 / TP2 | 1.5R half off, stop to entry; 3R (or a closer structure level beyond 1.5R) on the runner |

There is **no full news calendar** in the history. A first-Friday 08:00–10:30 ET NFP window was tested as a sensitivity only.

### Sessions (America/New_York)

Matches the daily notes: Asia 18:00–03:00 ET, London 03:00–08:00 ET, New York 08:00–17:00 ET, break 17:00–18:00 ET. IST is ET + 9.5 hours in US summer (EDT) or + 10.5 hours in US winter (EST).

### Setups

Rules were tightened to “clear setup” quality (major 4H/daily zones, ATR-scaled sweep excess, London/NY only for pullback/sweep/RSI) after looking at **signal counts**, not P&L.

1. **pullback** — 1h rejection close in a 4H or daily swing zone. With the trend filter, only sells in a D+4H downtrend and buys in a D+4H uptrend (close vs 50/200-day and 4H 50-SMA).
2. **sweep** — London/NY bar sweeps prior-day or Asia high/low by at least `max($0.50, 0.15×ATR)` and closes back inside; fade the sweep.
3. **breakout** — first 1h close beyond the completed Asia range during 03:00–13:00 ET, stop beyond the other side of the range. Skip if the Asia range is narrower than $5 or the stop is wider than 3× 1h ATR, and do not chase a close already more than half the Asia range through the level.
4. **rsi_mr** — control: 1h RSI ≤ 30 or ≥ 70 at a major daily/4H/prior-day level, fade.

`combo_core` (pullback + sweep, trend filter) and `combo_all` (all four) were registered **before** seeing P&L, with priority pullback > sweep > breakout > RSI. That priority turned out to be the wrong order (see results).

`trend_ma` = daily close vs 50- and 200-SMA and 4H close vs 50-SMA. `trend_strict` also requires daily/4H lower-highs or higher-lows.

## 1h results (primary)

Start equity $100,000. Expectancy is mean R after costs. Max drawdown is mark-to-market on the 1h equity curve.

| Variant | Trades | Win rate | Avg R | Profit factor | Net $ | Max DD | TP2 rate |
|---------|-------:|---------:|------:|--------------:|------:|-------:|---------:|
| **breakout, no filter** | 132 | 53.8% | **+0.37** | **1.79** | **+26,791** | **−3.4%** | 31% |
| **breakout, trend_ma** | 60 | 55.0% | **+0.44** | **1.91** | **+13,243** | **−2.8%** | 35% |
| breakout, trend_strict | 31 | 48.4% | +0.16 | 1.29 | +2,295 | −2.3% | 23% |
| sweep, trend_ma | 158 | 44.9% | +0.02 | 1.03 | +1,170 | −7.5% | 19% |
| sweep, trend_strict | 99 | 44.4% | +0.01 | 1.02 | +445 | −5.7% | 17% |
| sweep, no filter | 496 | 35.3% | −0.16 | 0.75 | −33,231 | −35.7% | 17% |
| pullback, trend_strict | 59 | 40.7% | −0.04 | 0.93 | −1,200 | −6.4% | 19% |
| pullback, trend_ma | 80 | 37.5% | −0.09 | 0.85 | −3,717 | −8.5% | 20% |
| pullback, no filter | 370 | 34.1% | −0.22 | 0.66 | −32,674 | −34.5% | 15% |
| rsi_mr, no filter | 58 | 34.5% | −0.21 | 0.68 | −5,961 | −9.5% | 14% |
| rsi_mr, trend_ma | 3 | 0.0% | −1.02 | 0.00 | −1,515 | −1.7% | 0% |
| combo_core, trend_ma | 172 | 43.0% | −0.01 | 0.98 | −952 | −9.8% | 19% |
| combo_all, trend_ma | 172 | 45.9% | +0.10 | 1.17 | +7,916 | −5.1% | 23% |
| combo_core + NFP window | 170 | 43.5% | −0.01 | 0.98 | −733 | −9.8% | 19% |

Equity curves: `figures/equity_1h_*.png`. Full trade lists: `results/trades_1h_*.csv`.

### What actually had positive expectancy

**Asia-range breakout is the only setup with a clear, repeatable 1h edge after costs.**

- Without a trend filter, both directions worked: BUY 78 trades, +0.39R, PF 1.81; SELL 54 trades, +0.34R, PF 1.77.
- Every calendar year in the sample was profitable (2024 +0.44R, 2025 +0.28R, 2026 +0.43R). Nine of ten quarters were positive; 2026Q4 was flat on five trades.
- The top five winners were only 11% of gross profit — not a one-trade story. Median R was +0.69. Average stop distance was about $35 (the far side of the Asia range). Average hold was ~60 hours.
- **London is the better session:** 72 trades, 59.7% win rate, **+0.53R**, PF **2.27**, +$20,763. New York (through 13:00 ET): 60 trades, +0.19R, PF 1.35.
- By entry hour (ET), 04:00–08:00 was consistently positive. 09:00 and 11:00 were weak or scratch. The 13:00 ET cutoff already blocks late-NY chases.

The D+4H trend filter raised average R on the remaining trades (+0.44R, PF 1.91, DD −2.8%) and improved **buys** (52 trades, +0.53R, PF 2.18). It left only **eight sells**, which lost −0.18R. Daily MAs lag a fresh downtrend, so a hard MA gate is a poor way to take shorts. A post-hoc 4H-only filter (not a primary test) landed in between: 93 trades, +0.25R, PF 1.48 — worse than “no filter,” still better than the losing setups.

**Liquidity sweep with a trend filter is roughly break-even** (+0.02R, PF 1.03): not a standalone book. The useful slice is small and specific: **NY, with trend**, +0.13R, PF 1.23, 112 trades. London sweeps with the same filter lost −0.32R (41 trades). With-trend **sells** were +0.17R (23 trades); with-trend **buys** were scratch (−0.01R, 135 trades). Without a trend filter the setup is a clear loser (−0.16R, DD −36%).

### What to drop or not automate

- **RSI mean reversion at levels:** −0.21R on 58 unfiltered trades. With the trend filter it almost never fires (n=3, all losers). Keep RSI as context, not as a trigger.
- **Mechanical trend pullbacks as coded:** overall negative, even with the trend filter (−0.09R). Unfiltered is worse (−0.22R). The one constructive slice is **with-trend sells** at 4H supply (15 trades, +0.35R, PF 1.65) plus a tiny 15m confirmation in the recent selloff. With-trend **buys** at 4H demand lost −0.19R on 65 trades. That is not enough to automate pullbacks; it is only a reason to still *consider* a clear downtrend supply rejection by hand.
- **combo_core** (pullback + sweep) was slightly negative. **combo_all** was modestly positive (+0.10R) only because some breakouts got through. The pre-registered priority (pullback first) blocked the better setup. Live priority should be the opposite: breakout first, then maybe a NY sweep, not a pullback.

The first-Friday NFP window barely changed combo_core (170 vs 172 trades). That is **not** evidence that news does not matter — it is evidence that our proxy is too thin.

### 1h breakout, no filter, by session and year

| Slice | Trades | Win rate | Avg R | PF | Net $ |
|-------|-------:|---------:|------:|---:|------:|
| London | 72 | 59.7% | +0.53 | 2.27 | +20,763 |
| New York | 60 | 46.7% | +0.19 | 1.35 | +6,028 |
| 2024 | 34 | 58.8% | +0.44 | 2.06 | +7,551 |
| 2025 | 54 | 48.1% | +0.28 | 1.52 | +8,216 |
| 2026 | 44 | 56.8% | +0.43 | 2.01 | +11,024 |

Weekend holds of *already-open* breakouts were profitable on average in this sample (42 trades, +1.11R). One stop was gapped through at −1.14R. Friday late entries are already blocked by the 13:00 ET cutoff. A blanket “flatten every Friday” would have *removed* some of the best Friday London/NY breaks — those were the strongest weekday in this file. Gap risk is real; a standing flatten-Friday rule is not supported here.

## 15m results (short window, treat lightly)

2026-09-04 to 2026-11-13, almost all with-trend **sells** in a washout:

| Variant | Trades | Win rate | Avg R | PF | Net $ |
|---------|-------:|---------:|------:|---:|------:|
| pullback, trend_ma | 15 | 66.7% | +0.65 | 2.90 | +4,850 |
| sweep, trend_ma | 23 | 52.2% | +0.41 | 1.83 | +4,710 |
| combo_core, trend_ma | 27 | 59.3% | +0.53 | 2.27 | +7,272 |
| breakout, no filter | 10 | 60.0% | +0.34 | 1.86 | +1,652 |
| breakout, trend_ma | 5 | 20.0% | −0.67 | 0.18 | −1,559 |
| rsi_mr, no filter | 18 | 27.8% | −0.29 | 0.60 | −2,605 |

The recent selloff is where a *discretionary* supply rejection / Asia-high sweep would have been in play, and the mechanical version made money — but 15–27 trades in one regime cannot overrule two years of 1h data. The 15m trend-filtered breakout losing on five trades is the same warning: too small to flip the 1h breakout result.

## Limitations (read these)

- **Futures, not spot.** Broker XAUUSD and `GC=F` can differ by several dollars and do not move tick-for-tick. The EA trades spot.
- **No real news filter.** NFP/CPI/PPI/FOMC were not replayed. Some winning and losing trades will have sat through 8:30 ET prints.
- **Yahoo 1h history is only ~28 months** after warmup, and 15m only ~10 weeks. We cannot see 2013, 2018, or 2020-style regimes.
- **Rule-based ≠ discretionary.** A human can skip a sloppy Asia range, wait for a second close, or stand aside into PPI. The engine cannot.
- **Conservative same-bar stops** slightly penalize setups that tag a target and a stop in one wide hour.
- **Small sell samples** under the daily MA trend filter. Gold spent most of this window in a bull market.
- **Costs are a model** ($0.25 + $0.10 per side). A wider retail gold spread would shrink, not flip, the breakout edge at these stop distances (~$30–35), but it would hurt tight pullback/sweep stops more.

The written playbook is `research/playbook.md`.

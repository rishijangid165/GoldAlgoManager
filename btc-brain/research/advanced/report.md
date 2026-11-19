# ADVANCED TRAINING MODE: Phases 1–6 Report (19 Nov 2026, ~23:15 IST)

Scripts: `fetch.py` (data) → `dq.py` (Phase 1 checks) → `phase2_3.py` → `phase4.py` → `phase5_6.py`; the engine is in `engine.py`, the risk engine in `risk.py`.
Every number here is printed by those scripts (also saved as `data_quality.json`, `phase3.json`, `phase4.json`, `phase5_6.json`, `trades_S*.csv`).

## VERDICT (short)
**None of the 3 strategies passed.** All three are loss-making after costs over 12 months, and even before costs the edge is roughly zero
(S1 −0.00R, S2 −0.22R, S3 +0.01R per trade). Walk-forward: 8 of 9 test windows failed. So there's **no final_strategy.md**, and nothing
goes to Phase 7 as a "live candidate". No profit is guaranteed, and here the data clearly shows no edge.

## Phase 1: Data
- Source: **Delta India BTCUSD perpetual** public API for all of 15m, 1H, 4H and 1D. The 12-month backtest is 19 Nov 2025 22:30 → 19 Nov 2026 22:30 IST.
  Fetched from 1 Oct 2025 (the extra ~7 weeks are indicator warm-up). Binance BTCUSDT 1H (public data-api.binance.vision) was used only as a cross-check.
- Candles: 15m 39,814 · 1H 9,953 · 4H 2,488 · 1D 414. **Gaps: 0** in every timeframe. OHLC errors: 0. Zero-volume candles: 15m 45, 1H 2.
- Spikes (range > 6× the median of the previous 100 candles): 15m 200, 1H 43, 4H 7, 1D 0. These are real market moves (e.g. 11 Oct 2025 crash, 19–21 Aug 2026, 5 Nov 2026):
  Delta vs Binance 1H close difference has a median of 0.038%, p99 0.066%, max 0.469%, and **0 hours > 0.5%**. Only 9 hourly highs/lows differed > 0.5% (single-exchange wicks),
  so they were kept in the data.
- Spread from data: candles have no bid/ask, so **data nahi hai** for a historical spread. Costs therefore come from XM's published figures:
  - XM Standard BTCUSD average spread **$40** per 1 BTC, no commission (fxrecap.com and mobilexm.com, quoting XM's published table; one BTCUSD quote on goodib.com showed 400,000 points = $40). KIWAMI ~$15. XM Zero has no crypto.
  - Swap (Standard): about **−$35/lot/night long, −$23/lot/night short** (fxfan.club, from XM's calculator, 5 Oct 2026; goodib showed −3452/−2301 points).
  - Not verified directly on xm.com (the calculator page needs JS), so this is labelled an estimate.
- **Cost assumption used (conservative):** spread **$50/BTC** per round trip + slippage **$15/BTC per fill** (entry and every exit) + swap **$35/BTC per night** held past 22:00 UTC.
  At 0.01 lot that's ≈ $0.80 per trade + $0.35/night. Stress test: spread and slippage doubled ($100 + $30/fill).

## Phase 2: Regime (each 1H candle, using past data only)
Priority order:
1. **HIGHVOL_NEWS** = within ±2h of CPI/NFP/FOMC, **or** ATR14(1H) ≥ 90th percentile of the previous 720 hours, **or** candle volume > 3× the previous-20 average.
2. **TREND_UP** = last completed 4H close > 4H EMA50, EMA50 higher than 3 candles ago, and 4H ADX14 ≥ 20.
3. **TREND_DOWN** = the mirror of TREND_UP.
4. **SIDEWAYS** = everything else.

| Regime | 1H candles | % of time |
|---|---|---|
| Trend Up | 2,286 | 26.1% |
| Trend Down | 2,804 | 32.0% |
| Sideways | 2,328 | 26.6% |
| High-Vol/News | 1,343 | 15.3% |
(HV/News triggers, which overlap: news ±2h 140 candles, ATR ≥ p90 776, volume > 3× 514.)

US events used (ET times converted to UTC). 2026 dates from the BLS 2026 schedule and federalreserve.gov:
- NFP: 9 Jan, 11 Feb, 6 Mar, 3 Apr, 8 May, 5 Jun, 2 Jul, 7 Aug, 4 Sep, 2 Oct, 6 Nov 2026.
- CPI: 13 Jan, 13 Feb, 11 Mar, 10 Apr, 12 May, 10 Jun, 14 Jul, 12 Aug, 11 Sep, 14 Oct, 10 Nov 2026.
- FOMC: 28 Jan, 18 Mar, 29 Apr, 17 Jun, 29 Jul, 16 Sep, 28 Oct 2026; 10 Dec 2025.
- **Unsure (from memory, shutdown-delayed releases):** NFP 20 Nov 2025, NFP 16 Dec 2025, CPI 18 Dec 2025.
- Not included: PCE, PPI, Fed speeches, crypto-specific news (ETF flows etc.).

## Phase 3: 3 strategies (same rules for all)
Common rules:
- Signal on a completed 1H candle. Trend = last completed 4H close vs EMA50 + EMA50 slope over 3 candles.
- Entry at the candle close. Risk 10 USDT (1% of 1,000) with fractional size (research mode). ATR-based stop.
- TP1 = 2R (half, stop → entry), TP2 = 3R.
- One trade at a time. No new trade within ±30 min of news. Daily −30 USDT stop.
- Trade path checked on **15m candles**: stop first if a 15m candle touches both; gap through the stop fills at the open; if price returns to entry in the TP1 candle → breakeven.

Strategies:
- **S1 Trend pullback:** trend UP and the 1H candle dips to EMA20(1H), closes above it, green candle → BUY; stop = candle low − 0.5×ATR14(1H). SELL is the mirror.
- **S2 S/R reversal (v1):** trend direction; touch of a valid 1H pivot (3 candles each side, last 120h) within 0.25×ATR, close back across, volume > 1.2× avg20; stop = beyond the candle/level + 0.3×ATR.
- **S3 Breakout + volume:** trend direction; 1H close above the 24-candle high (below the low for SELL), volume > 1.5× avg20; stop = 1.5×ATR.

Sharpe = daily P&L (by exit day, zero days included) ÷ 1,000, mean/stdev × √365.

| 12 months, base costs | Trades | Win % | Avg win | Avg loss | Expectancy | PF | Total | Max DD (% of 1,000) | Losing streak | Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 Pullback | 253 | 31.6% | +19.45 | −11.69 | −1.84 USDT (−0.18R) | 0.77 | −466.72 | 625.9 (62.6%) | 17 | −1.90 |
| S2 S/R reversal | 101 | 24.8% | +19.11 | −11.96 | −4.27 (−0.43R) | 0.53 | −431.16 | 467.2 (46.7%) | 10 | −3.03 |
| S3 Breakout | 151 | 35.8% | +16.44 | −11.54 | −1.53 (−0.15R) | 0.79 | −231.03 | 367.3 (36.7%) | 7 | −1.34 |
Before costs: S1 −7.56, S2 −227.22, S3 +20.00 USDT total. Costs paid: S1 459.16, S2 203.95, S3 251.03.
(Drawdown measured on a fixed 1,000 base without compounding, so it can exceed what a real account would survive.)

By regime (expectancy R / PF / trades):
| | Trend Up | Trend Down | Sideways | HV/News |
|---|---|---|---|---|
| S1 | +0.02R / 1.03 / 73 | −0.18R / 0.77 / 74 | −0.45R / 0.50 / 53 | −0.21R / 0.73 / 53 |
| S2 | −0.54R / 0.45 / 21 | −0.71R / 0.30 / 24 | −0.55R / 0.43 / 23 | −0.07R / 0.91 / 33 |
| S3 | −0.15R / 0.79 / 16 | −0.01R / 0.98 / 28 | −0.14R / 0.80 / 21 | −0.20R / 0.74 / 86 |
Only S1 in Trend Up is slightly positive (+0.02R, PF 1.03, DD 19%). That's essentially zero, not an edge. A regime-restricted version was
tested properly inside the walk-forward (regime choice made only on training data). See Phase 4.

## Phase 4: Walk-forward (70% train / 30% test, 3 rolling 6-month windows)
- Grid: 4 parameter combos per strategy (S1 EMA20/50 × stop buffer 0.5/1.0 ATR; S2 pivot 3/5 × volume 1.2/1.5; S3 N 24/48 × volume 1.5/2.0),
  each also tried restricted to the regimes that were positive on the training data. **46 combos evaluated in total, on training data only.**
- Pick = best training expectancy with ≥15 trades. Run unchanged on the test part. Pass = test expectancy > 0 and PF ≥ 1, and a strategy must pass all 3 windows.

| Strategy | Window (test period) | Chosen on train | Train | Test | Result |
|---|---|---|---|---|---|
| S1 | A (27 Mar–20 May 26) | EMA50, buf 1.0, Trend Down only | 17 tr, +0.13R, PF 1.18 | 5 tr, −1.13R, PF 0.00 | FAIL |
| S1 | B (26 Jun–19 Aug 26) | EMA20, buf 0.5, HV/News only | 18 tr, +0.17R, PF 1.27 | 13 tr, −0.63R, PF 0.30 | FAIL |
| S1 | C (26 Sep–19 Nov 26) | EMA50, buf 1.0, Trend Up only | 23 tr, −0.17R, PF 0.78 | 3 tr, −0.05R, PF 0.94 | FAIL |
| S2 | A | pivot 3, vol 1.5 | 22 tr, −0.42R, PF 0.53 | 20 tr, −0.33R, PF 0.63 | FAIL |
| S2 | B | pivot 5, vol 1.5 | 24 tr, +0.12R, PF 1.16 | 10 tr, −0.64R, PF 0.33 | FAIL |
| S2 | C | pivot 5, vol 1.5 | 24 tr, −0.50R, PF 0.44 | 6 tr, +0.23R, PF 1.37 | pass (6 trades only) |
| S3 | A | N24, vol 2.0 | 43 tr, −0.01R, PF 0.98 | 19 tr, −0.32R, PF 0.59 | FAIL |
| S3 | B | N24, vol 2.0 | 44 tr, −0.13R, PF 0.83 | 17 tr, −0.72R, PF 0.21 | FAIL |
| S3 | C | N48, vol 2.0 | 36 tr, +0.02R, PF 1.04 | 17 tr, −0.53R, PF 0.44 | FAIL |
**All 3 strategies rejected.** Training winners didn't hold up on test data (regime picks especially flipped from window to window), which is the classic overfitting signature.

## Phase 5: Stress (no survivors; run on the 12-month default versions for transparency only)
| | MC maxDD median / p95 / p99 (1,000 shuffles, USDT) | Worst week | Worst month | Positive months | Zero cost | Base cost | 2× spread+slip | KIWAMI-like ($15, no swap) |
|---|---|---|---|---|---|---|---|---|
| S1 | 548.9 / 666.9 / 732.7 | −89.64 (2026-W30) | −185.05 (Jul 26) | 4/13 | −7.56 (−0.00R, PF 1.00) | −466.72 | −901.82 (DD 98%) | −219.91 |
| S2 | 459.9 / 522.8 / 553.2 | −58.51 (W20) | −84.17 (Jul 26) | 3/13 | −227.22 (−0.22R) | −431.16 | −598.61 | −321.41 |
| S3 | 309.0 / 411.5 / 449.0 | −48.14 (W37) | −93.80 (Mar 26) | 5/13 | +20.00 (+0.01R, PF 1.02) | −231.03 | −428.89 | −91.30 |
None survive doubled costs. None is positive even with the cheaper KIWAMI-like cost.

## Phase 6: Risk engine (`risk_engine.md`, `risk.py`)
Shown as an illustration on the rejected defaults (compounding equity from 1,000, XM 0.01-lot steps, HV half size, 3%/6% limits, 3-loss pause):
| | Risk 1%: trades / exp / PF / final equity / max DD | Skipped (lot < 0.01) | Risk 0.5%: final equity / max DD |
|---|---|---|---|
| S1 | 267 / −0.17R / 0.78 / **697.90** / 34.1% | 155 (+47 skipped by 3-loss pause) | 823.94 / 21.9% (468 skipped) |
| S2 | 67 / −0.61R / 0.37 / **733.50** / 27.8% | 46 | 906.47 / 9.4% |
| S3 | 86 / −0.11R / 0.81 / **920.22** / 15.5% | 115 | 953.56 / 4.7% |
The risk engine cuts the losses (smaller drawdowns), but it can't create an edge. Important practical point: with **1,000 USDT on XM, the 0.01 minimum lot**
blocks most 1H setups (any stop > $1,000 at 1% risk, > $500 at 0.5%). Rounding down also makes the actual risk often smaller than planned.

## Live pass criteria (each strategy)
| Criterion | S1 | S2 | S3 |
|---|---|---|---|
| Expectancy positive (after costs) | FAIL (−0.18R) | FAIL (−0.43R) | FAIL (−0.15R) |
| PF ≥ 1.3 | FAIL (0.77) | FAIL (0.53) | FAIL (0.79) |
| Max DD < 10% | FAIL (62.6%) | FAIL (46.7%) | FAIL (36.7%) |
| Test similar to training (walk-forward) | FAIL (0/3) | FAIL (1/3) | FAIL (0/3) |
| Paper vs backtest | not yet (Phase 7) | – | – |
**All fail → no live, no XM demo EA test on these rules.**

## What I recommend (not forcing a strategy)
1. Don't start Phase 7 "live-candidate" paper trading with any of these. If the routines keep paper trading, label it "data collection, no proven edge".
2. These 1H systems lose mainly to costs (gross ≈ 0). Next research ideas, each to go through the same 7 phases:
   - slower 4H/1D trend systems with fewer trades and wider targets, where costs are a smaller part of R;
   - a KIWAMI account (lower spread, no swap).
   But on a 1,000 USDT XM account, wider stops conflict with the 0.01-lot minimum at 1% risk. That's a real constraint.
3. For long-term BTC exposure, the earlier spot DCA plan (no leverage) has none of these cost and edge problems.
4. Real orders: never without Rishi's "haan".

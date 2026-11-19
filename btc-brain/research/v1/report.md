# BTC Training Mode — Steps 1–3 Report (generated 19 Nov 2026, ~23:05 IST)

All numbers below come from `backtest.py` / `analyze.py` / `step3.py` in this folder. Rerun: `python3 fetch.py && python3 analyze.py && python3 step3.py`.

## Data
- Source: Delta India public API, `BTCUSD` perpetual, 1H and 4H candles (`btc_1h.csv`, `btc_4h.csv`).
- Fetched 20 Jul 2026 05:30 IST → 19 Nov 2026 22:30 IST (2,945 complete 1H candles, 736 complete 4H candles, **no gaps**).
  The extra month before 20 Aug is warm-up only (EMA50/ADX/pivots); trades allowed from 20 Aug 2026 05:30 IST.
- "Now" taken from the Delta ticker timestamp (19 Nov 2026 23:04 IST); the still-forming candles were dropped.
- In-sample (IS) = 20 Aug – 19 Oct 2026 (~2 months). Out-of-sample (OOS) = 20 Oct – 19 Nov 2026 (~1 month), untouched while choosing tweaks.
- Volume is Delta's own volume (one exchange), not global BTC volume.

## US events used (BLS and federalreserve.gov schedules; times ET converted)
| Event | Date | Time IST |
|---|---|---|
| NFP | 4 Sep 2026 | 18:00 |
| CPI | 11 Sep 2026 | 18:00 |
| FOMC decision | 16 Sep 2026 | 23:30 |
| NFP | 2 Oct 2026 | 18:00 |
| CPI | 14 Oct 2026 | 18:00 |
| FOMC decision | 28 Oct 2026 | 23:30 |
| NFP | 6 Nov 2026 | 19:00 (after US DST ended 1 Nov) |
| CPI | 10 Nov 2026 | 19:00 |
Not included (unsure / not in scope): Jackson Hole (late Aug), PCE, PPI, Fed speeches, FOMC minutes. I'm not sure these were the only market-moving events.

## Definitions
- Condition: **trending** if 4H ADX(14) ≥ 20 at entry, else **sideways**.
- Weekend = Saturday/Sunday UTC (Sat 05:30 IST → Mon 05:30 IST).
- News = entry within ±2h of an event above. (Entries within ±30 min are blocked by the strategy itself.)
- Drawdown = peak-to-trough on the closed-trade equity curve starting at 1,000 USDT.
- Trade #23 is still **open** (marked at the last close). It's included in "ALL" and "OOS" and shown separately as closed-only.

## Step 2 — Baseline backtest (strategy.md v1)
| Sample | Trades | Win % | Avg win | Avg loss | Expectancy/trade | Total P&L | Max DD | Longest losing streak |
|---|---|---|---|---|---|---|---|---|
| ALL, net of 0.05%/side | 23 | 30.4% | +14.48 | −10.98 | **−3.23 USDT (−0.33R)** | **−74.36** | 114.27 (11.4%) | 6 |
| ALL, no costs | 23 | 30.4% | +15.83 | −9.62 | −1.87 (−0.19R) | −43.11 | 91.34 (9.1%) | 6 |
| ALL closed only, net | 22 | 27.3% | +15.42 | −10.98 | −3.78 (−0.39R) | −83.23 | 114.27 (11.4%) | 6 |
| IS, net | 17 | 17.6% | +13.05 | −10.90 | −6.67 (−0.69R) | −113.44 | 113.44 (11.3%) | 6 |
| IS, no costs | 17 | 17.6% | +14.27 | −9.58 | −5.37 (−0.56R) | −91.34 | 91.34 (9.1%) | 6 |
| OOS, net (incl. open #23) | 6 | 66.7% | +15.56 | −11.57 | +6.51 (+0.68R) | +39.08 | 23.15 (2.3%) | 2 |
| OOS, no costs | 6 | 66.7% | +17.00 | −9.88 | +8.04 (+0.84R) | +48.23 | 19.76 (2.0%) | 2 |
| OOS closed only, net | 5 | 60.0% | +17.78 | −11.57 | +6.04 (+0.62R) | +30.21 | 23.15 (2.3%) | 2 |

Results: 16 stop-loss, 3 TP1 then breakeven, 3 TP1+TP2, 1 open. Total costs paid: 31.25 USDT (≈1.4 USDT/trade, ≈0.14R). Average risk per trade 9.58 USDT.

### Condition breakdown (ALL, net / no costs)
| Group | Trades | Win % | Expectancy net | Total net | Total no-cost |
|---|---|---|---|---|---|
| Trending (ADX≥20) | 17 | 29.4% | −3.49 (−0.36R) | −59.36 | −38.16 |
| Sideways (ADX<20) | 6 | 33.3% | −2.50 (−0.26R) | −15.00 | −4.95 |
| Weekday | 20 | 25.0% | −4.62 (−0.47R) | −92.43 | −68.06 |
| Weekend | 3 | 66.7% | +6.02 (+0.60R) | +18.07 | +24.95 |
| News ±2h | 1 | 0% | −11.07 | −11.07 | −9.65 |
| No news | 22 | 31.8% | −2.88 (−0.30R) | −63.29 | −33.46 |
| Long | 13 | 15.4% | −6.76 (−0.71R) | −87.87 | −70.94 |
| Short | 10 | 50.0% | +1.35 (+0.16R) | +13.51 | +27.83 |

Where it failed: mainly **longs in late Aug – Sep**, when the 4H trend still read "UP" but BTC was topping out
(several longs were 5.7–7.9 ATR above the 4H EMA50, i.e. late, stretched entries), plus weak "doji" trigger candles.
Weekend and news groups have only 3 and 1 trades, so they tell us nothing. Sideways vs trending isn't clearly different either.

## Step 3 — Losing trades (one line each; # = row in trades.csv)
| # | Date IST | Side | What went wrong | Rule that would have avoided it |
|---|---|---|---|---|
| 1 | 25 Aug 20:30 | L | Bought 7.3 ATR above 4H EMA50: late, stretched trend | B (not extended) |
| 2 | 26 Aug 19:30 | L | Stretched (6.3 ATR) plus a small-body candle (0.19) | B, D |
| 3 | 28 Aug 16:30 | L | Stretched (6.5 ATR) | B |
| 4 | 28 Aug 20:30 | L | Stretched (5.7 ATR), doji (body 0.18), 5× volume spike (selling climax) | B, D |
| 5 | 1 Sep 19:30 | L | Sideways (ADX 13), doji (body 0.10) | A, D |
| 6 | 6 Sep 13:30 | L | Weekend, sideways (ADX 16), doji (0.10), very tight stop (0.37%) | A, D, E |
| 8 | 8 Sep 22:30 | S | Weak rejection (closed mid-candle), price hugging EMA, ADX 17 | A, C |
| 10 | 23 Sep 19:30 | L | Stretched (7.9 ATR) | B |
| 11 | 25 Sep 14:30 | L | Volume barely passed (1.21×), trend fading | none of the tested rules |
| 12 | 25 Sep 20:30 | L | Doji (body 0.10) | D |
| 14 | 9 Oct 18:30 | S | Clean setup, level just failed: normal loss | none |
| 15 | 12 Oct 15:30 | L | Price right at the EMA (trend-flip zone), small body (0.13) | D |
| 16 | 14 Oct 16:30 | L | 1.5h before CPI, ADX 19 | A, F |
| 17 | 16 Oct 18:30 | S | Strong candle, level failed: normal loss | none |
| 19 | 26 Oct 22:30 (OOS) | S | Short closed in the upper part of the candle (weak rejection) | C |
| 20 | 27 Oct 23:30 (OOS) | S | ~24h before FOMC, level failed | none |

### Candidate rules (chosen by looking only at IS losers; each run as a full re-simulation)
Acceptance test: must filter at least 3 IS losers **and** improve IS net expectancy **and** not hurt OOS.
| Rule | IS losers avoided | IS winners lost | IS net exp → | OOS net exp (base +6.51, n=6) → | Decision |
|---|---|---|---|---|---|
| A: 4H ADX ≥ 20 | 4 (#5,6,8,16) | 2 (#7,13) | −6.67 → −8.95 (worse) | +6.51 (n=6, unchanged) | **Rejected**: IS got worse |
| B: entry ≤ 5 ATR(1H) from 4H EMA50 | 5 (#1,2,3,4,10) | 0 | −6.67 → −5.15; total −113.44 → −61.79; DD 6.2% | **−0.28** (n=3), total +39.08 → −0.83 | **Rejected**: hurt OOS (cut 3 OOS trades, 2 of them winners) |
| C: close in outer third of candle | 1 | 0 | −6.67 → −6.36 | +3.61 (n=5) | Rejected: <3 losers, OOS worse |
| D: trigger body ≥ 20% of range | 6 (#2,4,5,6,12,15) | 0 | −6.67 → −4.40; total −48.36; DD 4.8% | **+3.29** (n=5), total +39.08 → +16.45 | **Rejected**: OOS worse (filtered OOS winner #21) |
| E: no weekend | 1 | 1 | −7.26 | +3.29 | Rejected |
| F: no entry within ±2h of news | 1 | 0 | −6.40 | +6.51 | Rejected: <3 losers |

**Rules added: none.** B and D both looked good in-sample, but both made the untouched last month worse, so by our
anti-overfitting rule they're rejected. "After tweak" = "before tweak" (baseline v1). Note: the OOS test has only 5–6 trades,
so this accept/reject is itself weak evidence. B and D stay on a **watch list** to re-check after Step 4 paper data.

## Honest verdict
- **Sample is too small**: 23 trades total (17 IS, 6 OOS), well under the 30 needed. None of these numbers are statistically reliable.
- **Overall expectancy is negative**: −0.33R (−3.23 USDT) per trade after costs, −74.36 USDT over 3 months, and max drawdown 11.4%
  (above the 10% limit in Step 4). Even without costs it's negative (−0.19R).
- The last month (OOS) was positive (+0.68R, 4 of 6 wins; 3 of 5 among closed trades), but that coincides with a strong BTC downtrend
  where shorts worked. One good month in one regime doesn't prove an edge.
- So: **no proven positive expectancy yet.** It's okay to move to Step 4 **paper trading only** to collect data, but it isn't ready for real money or the XM EA.
  No profit is guaranteed.

# Final Strategy for Step 4 Paper Trading (= v1, no rules added)

Status: backtest 20 Aug–19 Nov 2026 is **negative overall** (−0.33R/trade net, 23 trades, DD 11.4%). Use for PAPER ONLY to collect ≥30 trades.

Rules: exactly as in `strategy.md`:
1. Trend 4H: close vs EMA50 + EMA50 slope over 3 candles (UP → only BUY, DOWN → only SELL, else NO TRADE).
2. Level: 1H pivot (3 left/3 right), last 120h, not closed through since.
3. Trigger: 1H candle touches level (±0.25 ATR14), closes back on the trend side of it, candle colour in trend direction.
4. Volume > 1.2× average of the previous 20 1H candles.
5. Stop = beyond candle extreme/level + 0.3 ATR. Size = 10 USDT ÷ R (Delta 0.001 BTC; XM 0.01-lot steps, skip if R > $1,000).
6. TP1 = 2R (close half, stop → entry), TP2 = 3R.
7. One trade at a time; −30 USDT day loss → stop for the day; 3 losses in a row → pause and report to Rishi; no new trade ±30 min around CPI/NFP/FOMC.

Watch list (rejected now, re-test on paper data; adopt only if they help on new data and on ≥3 losers):
- B: skip if entry is > 5 ATR(1H) away from the 4H EMA50 (late, stretched entries).
- D: skip if trigger candle body < 20% of its range (doji).

Step 4 pass criteria (Rishi's): ≥30 paper trades, positive expectancy, drawdown < 10%. Then ask: "XM demo EA par test shuru karein?"

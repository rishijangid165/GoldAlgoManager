# Training plan and live pass criteria

Live alerts and the XM demo EA stay off until this plan is actually passed. Paper trading in the meantime is **data collection only**.

## Early training (5 steps)

1. **Write a simple strategy** with clear entry, stop, and target rules (trend + support/resistance + volume).
2. **Backtest** on historical 1H and 4H data. Record every trade. Report win rate, average win, average loss, max drawdown, and where it failed (sideways, news, weekend).
3. **Learn from losers.** One line per losing trade. Add a new rule only if it helps on at least 3 trades and also holds on a later, unused window. Do not add a rule on the strength of one trade.
4. **Paper trade** for at least 2 weeks (later raised to 4+ weeks and 50+ trades). Weekly report required.
5. **Ask permission before live.** If numbers pass, give Rishi a summary and ask: "XM demo EA par test shuru karein?" Do not go further without "haan".

Result of the first 3-month test is in `research/v1/`. The v1 strategy was **net negative**. No extra rule was added, to avoid overfitting.

## Advanced training (7 phases)

1. **Data** — at least 12 months of BTC data (15m, 1H, 4H, 1D). Check gaps, spikes, and spread. Include estimated XM spread and overnight cost. A backtest with no costs is misleading.
2. **Market regime** — label candles as Trend Up, Trend Down, Sideways, or High-Volatility/News (4H trend, ATR, volume). Test each strategy by regime. A strategy that only works in one regime may be used only in that regime.
3. **Compare 3 strategies** on the same data:
   - Trend-following (pullback entry)
   - Support/resistance reversal
   - Breakout + volume confirmation
   Report for each: trades, win rate, average win/loss, expectancy, profit factor, max drawdown, Sharpe.
4. **Walk-forward** — build rules on 70% of the data, test unchanged on 30%. Repeat on 3 different time windows. Reject a strategy that fails the test window.
5. **Stress test** — Monte Carlo shuffle of trade order (1000 times) and worst-case drawdown; worst week/month separately; rerun with double slippage and spread. The strategy must still survive.
6. **Risk engine** — 0.5–1% risk, ATR-based stop, lot formula, daily 3% / weekly 6% / 3-loss stop, half size or no trade in high-volatility or news regimes. See `research/advanced/risk_engine.md`.
7. **Paper trading and weekly self-review** — at least 4 weeks and 50+ trades. Each week: trades, win rate, expectancy, drawdown, top 3 mistakes, rule changes only with 5+ trades of evidence, and the gap versus backtest. If that gap is large, pause alerts and find out why.

Result of phases 1–6 is in `research/advanced/`. **All three strategies failed** after costs. No strategy was selected for live use.

## Stage 2 discipline

Stage 2 (thesis, A+/A sizing, 3× reward, journal, Sunday review, monthly exam, no revenge, no FOMO) is already applied to paper trading so that data collection also builds the habit. The earlier edge tests have **not** been passed, so this is still not a green light for live trading.

## Live pass criteria (all required)

- Expectancy is positive
- Profit factor is at least **1.3**
- Max drawdown is under **10%**
- Test-window results are similar to the training window
- Paper results are close to the backtest
- At least **50 paper trades** over **4 or more weeks**

If even one item fails, do not go live or start the XM demo EA. There is no profit guarantee even if every item passes.

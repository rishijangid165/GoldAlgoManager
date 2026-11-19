# Lessons so far

These come mainly from the v1 and advanced backtests, not from the four short paper wins. Paper wins are too few to change the rules.

## Key backtest lessons

1. **Costs kill 1H trading on XM.** Spread, slippage, and overnight fees eat the edge on short 1-hour trades. A backtest with no costs looks better than it is and is not reliable.
2. **Late buys in a topping market hurt the most.** In Aug–Sep 2026 the 4H trend still read "UP" while BTC was stalling after a large rise. Several long entries were already far extended above the 4H average.
3. **Weak doji entries are a common loser.** Several losses came from trigger candles with a very small body (weak conviction at the level).
4. **Sideways markets also lost money.** A "level bounce" is not enough when there is no clear trend. Many days should simply be NO TRADE.
5. **The 0.01 lot minimum blocks wide stops on a 1,000 USDT account.** If the stop is more than about $1,000 away, even 0.01 lot risks more than 1%. Those setups must be skipped, so many otherwise valid ideas cannot be taken at this account size.

## Process lessons

- In v1 Step 3, six candidate filters were tested. **None** looked good on both the first two months and the last unused month, so **no rule was added**. Adding a rule just because it would have saved yesterday's losers is overfitting.
- Two ideas remain on a watch list only (re-test on new paper data, do not adopt yet): skip very stretched entries, and skip weak/doji trigger candles.
- In the 12-month advanced test, all three strategies (pullback, support/resistance reversal, and breakout) were **net negative** after estimated XM costs. Walk-forward and double-cost stress tests also failed. No strategy was selected for live use.
- Risk rules can limit damage. They cannot turn a losing strategy into a winning one.
- A handful of recent paper trades in profit (+26.46 USDT, no costs) does **not** cancel a failed backtest.

## What we will not do yet

- No live trading and no XM demo EA until the pass criteria in `rules/training-plan.md` are actually met and Rishi says "haan".
- No new rule in production until it has a backtest, a walk-forward test, and a paper test, with numbers attached.

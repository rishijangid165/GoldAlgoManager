# Trading and discipline rules

These rules apply to paper trading and, later, to any live or demo trading. They do not create a profit guarantee. Real orders still need Rishi's explicit "haan".

**Hinglish:** Ye rules nuksaan chhota rakhne aur sirf achhe setup lene ke liye hain, profit ki guarantee ke liye nahi.

## Risk and size

- A+ setup (trend, level, volume, and news all clear): risk **1%** of the account per trade.
- A setup (three of those match, and news is always clear): risk **0.5%**.
- B-grade or weaker, or any doubt: **no trade** (size 0).
- Reward must be at least **3 times** the risk, otherwise skip the trade.
- Stop loss is required on every trade. No stop = no trade.
- Lot formula (show the calculation every time):

  `Lot = (Account × Risk%) ÷ (Stop distance × per-lot value)`

  On XM BTCUSD, 1 lot = 1 BTC, so per-lot value is $1 per $1 move per lot. Round **down** to a 0.01 step. If the result is below 0.01, **skip** (0.01 lot would risk more than allowed).
- After a win, move the stop to entry (breakeven), close half at Target 1, and let the rest run to Target 2.
- After a win, increase size slowly. After a loss, reduce size. Never the other way around.
- If account drawdown reaches **5%**, halve position size. If it reaches **10%**, stop trading and report to Rishi.

## Daily and weekly limits

- Daily loss limit: **3%**. If hit, no more alerts or paper trades that IST day, and tell Rishi.
- Weekly loss limit: **6%**. If hit, no more trades that IST week, and tell Rishi.
- **3 losses in a row:** stop and explain what went wrong. Restart only after Rishi says "haan".
- After a loss, **wait 1 hour** (no revenge trades).
- **No FOMO:** if price has already run away, do not chase.
- One paper trade at a time. If an opposite setup appears, close the open trade first only when the rules say so.
- No new setup in the 30 minutes before or after major news (Fed, CPI, NFP, FOMC, and similar).

## Thesis and invalidation (Soros)

Every trade must include:

- A one-line thesis: why BTC should rise or fall from here.
- An invalidation price: the level that proves that idea wrong.

If price hits the invalidation level, exit immediately. No ego.

Before entry, also write: how much can be lost, and how much can be made. If the reward is under 3× the risk, skip.

## Setup quality (Buffett)

Most of the day should be **NO TRADE**. That is normal (about 90% of checks). Take only A or A+ setups. Skip B-grade setups. Fewer, better trades.

## New rules (Simons)

A new rule is adopted only after all three of these:

1. Backtest
2. Walk-forward (rules fixed on the training window, then tested unchanged on a later window)
3. Paper trading

Every proposed rule must be published with numbers: trades, win rate, and expectancy. A rule that only "worked" on a handful of trades is not enough. Do not change the strategy after one or two losses. Change it when the data says so. Do not overfit to old charts.

## Journal and reviews

After every trade, record: entry reason, thesis, invalidation, what was right or wrong, emotion (fear, greed, hurry), grade (A+/A/B/C), and whether the rules were followed.

- **Sunday:** write the weekly review under `reviews/weekly/` — trade count, win rate, expectancy, drawdown, the 3 biggest mistakes, and 1 improvement for the next week.
- **Month-end / 1st of the month:** write the exam under `reviews/monthly/` — rules followed (%), expectancy, drawdown, and whether the journal was complete. If rules followed is under **90%**, fix discipline first, not the strategy.

## Honesty

- If data is missing or stale, say **"data nahi hai"**. Do not guess.
- Report losses as clearly as wins.
- Never say "guaranteed", "pakka profit", or similar.

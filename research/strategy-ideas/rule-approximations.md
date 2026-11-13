# Rule-based approximations of the discretionary gold process

Written before the 2026-11-13 backtest run (see `research/backtest/`). These are testable shapes, not the live playbook. The playbook after the test is `research/playbook.md`.

Hypothesis: a small set of clear, structure-based 1h setups, with 0.5% risk, R:R ≥ 1.5, one trade at a time, and no entries through the Asia range until that range is complete, can show a measurable edge on `GC=F` after spread and slippage. A naive RSI fade at the same levels is the control and is expected to be weaker, especially against the higher-TF trend.

Setups to test, each with and without a daily+4H trend filter:

1. **Trend pullback** — D/4H trend (close vs 50/200-day and 4H 50-SMA, optionally LH/HL) plus a 1h rejection in a 4H/daily swing zone.
2. **Liquidity sweep** — fade a 1h sweep of the prior-day or Asia high/low that closes back inside.
3. **Asia breakout** — first London or early-NY 1h close beyond the completed Asia range, stop on the far side of the range, skip absurdly wide or tight ranges.
4. **RSI mean reversion (control)** — 1h RSI ≤ 30 or ≥ 70 at a major level, fade.

Primary evidence is the 1h series (~730 days, Yahoo’s cap). 15m (~60 days) is a short robustness window only.

# Risk Engine (Phase 6), implemented in risk.py

**Simple Hinglish mein:** har trade mein account ka 0.5–1% se zyada risk nahi. Stop ATR ke hisaab se lagega. Lot formula se banega aur
neeche round hoga. Lot 0.01 se kam bane to trade skip. Din mein 3% ya hafte mein 6% nuksaan ho gaya, ya lagatar 3 loss hue, to trading band.
High-volatility ya news wale time mein size aadha.

## Rules
1. Risk per trade: 1% of current equity (allowed range 0.5–1%). Half of that in the HIGHVOL_NEWS regime.
2. Stop: ATR-based (each strategy defines it, e.g. candle extreme ± 0.3–1.0×ATR14(1H), or 1.5×ATR).
3. **Lot = (Account × Risk%) ÷ (Stop distance × per-lot value)**. XM BTCUSD: 1 lot = 1 BTC, so per-lot value = $1 per $1 move per lot.
   Round DOWN to a 0.01 step. If the result is < 0.01 → **SKIP** (0.01 lot would risk more than allowed).
4. Daily loss limit: −3% of the day's starting equity (IST day) → no new trades that day.
5. Weekly loss limit: −6% of the week's starting equity (IST Mon–Sun) → no new trades that week.
6. 3 losses in a row → stop and report to Rishi. In the backtest this is simulated as "pause until the next IST day";
   live, restart only after Rishi says "haan".
7. One trade at a time. No new trade within ±30 min of CPI/NFP/FOMC.
8. Real orders never without Rishi's explicit "haan".

## Worked example (account 1,000 USDT)
- Risk 1% = 1,000 × 0.01 = **$10**.
- BUY entry 63,000, stop 62,400 → stop distance $600.
  Lot = 10 ÷ (600 × 1) = 0.0167 → round down to **0.01 lot**. Actual risk = 0.01 × 600 = **$6**.
- Stop 61,800 (distance $1,200): Lot = 10 ÷ 1,200 = 0.0083 → below 0.01 → **SKIP** (0.01 lot would risk $12 = 1.2%).
- HIGHVOL_NEWS: risk $5 → only stops ≤ $500 can be traded at 0.01 lot.
- At 0.5% risk ($5) the maximum tradable stop is $500. That's why at 1,000 USDT most 1H setups get skipped (see report).
- Costs at 0.01 lot (assumed): spread $50/BTC → $0.50 + slippage $15/BTC per fill × 2 → $0.30 + swap $35/BTC/night → $0.35 per night.

# XAUUSD playbook

Gold only. Demo first. The assistant reads the chart and writes the decision; the EA (`GoldAIBridge`) only executes inside the published zone, with the hard risk caps below locked in the EA.

This book is grounded in the 1h `GC=F` backtest of 2024-07-07 to 2026-11-13 (see `research/backtest/README.md`). Those tests are rule-based approximations on futures, not a promise that live spot trades will match the numbers. If a setup did not show a clear edge, it is not an automatic trigger here.

Clock: **America/New_York** (COMEX). Add 9.5 hours for IST in US summer (EDT) or 10.5 hours in US winter (EST). High-impact US data is usually 08:30 ET (18:00 IST in summer, 19:00 IST in winter).

---

## 1. Hard rules (never broken)

1. **One open trade at a time.** No averaging, no second position, no hedge.
2. **Risk 0.5% of current equity per trade.** Size from the *actual* stop distance at fill. If that would be below 0.01 lots, skip.
3. **Always a stop.** No mental stops. SL sits beyond structure, not a round number chosen for comfort.
4. **Do not take a trade that cannot offer at least 1.5R** to the first target at the planned fill. If slippage or a gap makes the live R:R worse than 1.5 at entry, skip.
5. **Scale:** close half at **1.5R (TP1)**, move the rest to **breakeven** (entry). Leave the runner to **3R** or to the next clear structure level if that level is between 1.5R and 3R.
6. **Daily loss stop: −2% realized.** No new trades that COMEX session. An open trade already on is managed to its SL/TP; we do not “revenge” a second ticket.
7. **Max two *new* attempts per session**, and only if the first is already closed. In practice the A-setup often holds overnight, so most days are zero or one trade.
8. **Kill switch / `valid_until` / news blackout** in the decision file are binding. If any one of them says stand aside, stand aside.

---

## 2. Chart process (before every decision)

Read in this order, gold only:

| TF | Question |
|----|----------|
| **Daily** | LH/LL or HH/HL? Close vs 50- and 200-day SMA? Where is the last major swing, the prior day, and today's session extreme? |
| **4H** | Is 4H agreeing or is it the first bar against the daily? Mark 4H supply and demand (confirmed swings, breakdown/breakout origins). |
| **1H** | Location vs those zones, Asia range (once 03:00 ET is in), prior-day high/low, rejection vs impulse. |
| **15M** | Trigger only. Two 15m rejection closes can stand in for one 1h close if the higher TF is already valid. Do not invent a setup from 15m alone. |

Also check the session (Asia / London / NY), the futures–spot basis (often $3–7; **publish zones in broker spot**), DXY/yields/news as context, and the economic calendar for the next 24 hours.

Default bias is **NONE**. A trade needs a named setup below, a stop, and 1.5R. “Price is in the zone” is not enough without a rejection or a close-break.

---

## 3. When *not* to trade

Stand aside (bias NONE) when any of these is true:

- No setup from section 4 or 5 is present, or the only signal is a pullback/RSI pattern we do not automate.
- **High-impact US news blackout:** from **30 minutes before to 90 minutes after** 08:30 ET releases (NFP, CPI, PPI, GDP, PCE) and around FOMC (typically 14:00 ET). Do not *enter* inside the window. An already-open, valid trade can be left on unless the thesis is the event itself.
- Inside the first 30 minutes of a session if price is still a one-sided impulse and there is no close back in range (the 13 Nov 2026 lesson: do not short a live rally just because it has reached a planned sell zone).
- Asia range is too tight (`< $5`) or too wide (stop would exceed ~3× 1h ATR, recently often ~$45–60). Skip the breakout.
- The close that would trigger a breakout has already run more than **half the Asia range** beyond the level — that is a chase. Wait for a later retest, or stand aside.
- After a −2% day, or after a messy gap through the planned stop.
- The last hour of the COMEX week (after 16:00 ET Friday) — do not *open* a new trade into the weekend. An already-open A-setup may be held; weekend holds of breakouts were profitable on average in the test, but gap risk is real (one historical stop slipped −1.1R).
- Any doubt about the basis (spot vs `GC=F`) that would mis-place the zone by more than a few dollars.

---

## 4. A-setup — Asia-range breakout (take this)

**This is the only mechanical setup with a clear 1h edge after costs:** 132 trades, 53.8% win rate, **+0.37R**, profit factor **1.79**, max drawdown **−3.4%**. Both buys and sells worked. London was the best slice (72 trades, **+0.53R**, PF 2.27). The edge showed up in 2024, 2025, and 2026.

### Setup

1. Lock the **Asia range** at 03:00 ET (high/low from 18:00 ET the prior calendar evening through 03:00 ET). Do not use a still-forming Asia high/low.
2. In **London (03:00–08:00 ET, preferred)** or **early New York through ~08:00–09:00 ET**, wait for the **first 1h close** clearly outside that range, in a direction you will actually trade (below).
3. **Stop** goes beyond the *other* side of the Asia range, plus a small buffer (~0.15× 1h ATR). If that stop is narrower than $5 or wider than 3× 1h ATR, skip.
4. Entry is the next 1h open (or a slightly conservative zone around that open for the EA). Do not move the stop closer after entry just to make the size larger.

### Direction

- **Soft trend bias, not a hard daily-MA gate.** With-trend buys (price already above daily 50/200 and 4H 50-SMA) were the cleanest subset (+0.53R). A hard “must be below both daily MAs” filter left almost no sells and missed good shorts in a fresh downtrend.
- Default: trade the Asia close-break **in the direction of the current 4H structure** (4H HH/HL → only upside breaks; 4H LH/LL → only downside breaks).
- A clean **London** close-break *against* a late daily MA trend may still be taken if the 4H has already turned and the range is orderly. Do not force a counter-trend NY late-morning break.

### Invalid / skip

- Second, third, or late re-break of the same Asia range the same day (the test only took the first close).
- Close already extended > 50% of the Asia range through the level.
- After 13:00 ET — no new breakout entries. 09:00 and 11:00 ET hours were the weak ones in the test; be pickier after the NY open.
- 15m can refine the entry but cannot justify a breakout the 1h has not closed.

---

## 5. B-setup — NY liquidity sweep, with trend (optional, modest)

The unfiltered fade-every-sweep book **lost money** (−0.16R, 36% drawdown). With a D+4H trend filter it was only **scratch** overall (+0.02R). The one slice worth considering:

- **New York session only** (London sweeps with the same filter lost −0.32R).
- Sweep of the **prior-day or Asia high/low** by a meaningful amount (not a $0.50 tick; use at least ~0.15× 1h ATR), then a **close back inside**.
- Trade **with the higher-TF trend:** sell a sweep of highs in a downtrend; buy a sweep of lows in an uptrend. With-trend sells were +0.17R (small sample, 23 trades); with-trend buys were scratch.
- Stop beyond the sweep wick plus a buffer. Same 1.5R / 3R scale.
- Take this only if no A-setup is in play or still valid. It does not earn a standalone slot in a mechanical book.

---

## 6. What we do *not* auto-take

**Mechanical trend pullbacks** (1h rejection at a 4H/daily zone, in the MA trend) were **negative** on the 1h sample (−0.09R with the filter, −0.22R without). With-trend *buys* in the bull were the problem (−0.19R, 65 trades).

The only hint of edge is a **clear sell** of a 4H supply zone in an *established* daily LH/LL downtrend, after a **rejection close** (15 trades, +0.35R, plus a small 15m confirmation in the 2026 selloff). That is optional, discretionary, and must meet all of:

- Daily and 4H are already making lower highs / lower lows, not merely “below a lagging 200-SMA.”
- The zone is a real 4H or daily swing (or a breakdown origin), not a local 1h wiggle.
- There is a bearish 1h close (or two 15m closes) *inside* the zone — not a market order into a live impulse.
- Invalidation is a 1h close above the zone. SL sits above the rejection wick / zone top.
- If this conflicts with a live A-setup, the A-setup wins.

**RSI oversold/overbought at a level is not a trade.** The control test lost −0.21R. RSI may support a stand-aside or a “wait for rejection” call; it does not authorize an entry by itself.

---

## 7. Entry, stop, and targets (how to write the decision)

- **Entry zone** in *spot* XAUUSD, with the futures–spot basis stated in the note. Keep the zone tight enough that a fill still leaves ≥ 1.5R to TP1 after a typical $0.20–0.40 spread.
- **SL** beyond structure (far side of Asia range for A; beyond the wick for B or a discretionary supply sell), plus a small ATR buffer. Do not tighten after a paper fill to juice size.
- **TP1 = 1.5R**, half off, stop of the runner to **entry**. **TP2 = 3R** or the next opposite swing if it sits between 1.5R and 3R.
- **`valid_until`** should expire before the next news blackout or before 13:00 ET for an A-setup that has not triggered.
- One decision, one zone, one direction. If the idea is gone, publish **NONE** rather than leaving a stale bias.

---

## 8. Priority when more than one idea appears

1. News blackout / daily loss stop / kill switch → **NONE**.
2. **A-setup (Asia breakout)** if it is valid.
3. Else **B-setup (NY with-trend sweep)** if it is valid and no A-trade is on.
4. Else a *discretionary* downtrend supply rejection, only as in section 6.
5. Else **NONE**.

The backtest combo that looked at pullbacks *first* blocked better breakouts and turned a strong A-setup into a weak mixed book. Do not repeat that.

---

## 9. Daily rhythm

- Recurring check every ~3 hours on weekdays is enough, with a compulsory read **before London (03:00 ET)** to lock the Asia range, and another **before 08:30 ET** if data is on the calendar.
- If an A-setup has not triggered by 13:00 ET, cancel it and go NONE until the next session’s range is complete.
- After PPI/NFP/FOMC, re-read D/4H/1H from scratch. Do not reuse the pre-news zone.
- Weekend: no new Friday 16:00 ET entries. Review open risk before the Sunday 18:00 ET reopen.

---

## 10. What this book does not claim

The supporting test used `GC=F` 1h history of about 28 months, a cost model, no full news calendar, and conservative same-bar stops. Fifteen-minute data covers only the autumn 2026 selloff. Live trading is still a human (or AI) chart read plus the EA’s hard caps — not a fully automated signal bot. If future checks show the A-setup going stale, the default is back to **NONE**, not a wider set of weaker rules.

# XAUUSD playbook

Version 2026-11-14 (v3). Gold only. Demo first. The assistant reads the chart and writes the decision; the EA (`GoldAIBridge`) only executes inside the published zone, with the hard risk caps below locked in the EA.

**v2 change (out-of-sample):** the unfiltered Asia-range breakout is no longer described as a durable, automatic edge. The 2024-07-07 to 2026-11-13 `GC=F` book (132 trades, +0.37R, PF 1.79; see `research/backtest/README.md`) and the same window on spot XAUUSD (128 trades, +0.27R, PF 1.52) are real — but a 2012–2026 walk-forward on HistData spot 1h does **not** confirm it (A-setup OOS −0.03R, PF 0.93, only 6 of 15 years green; 2012–2023 was −0.09R). Evidence and the tests we refused to adopt are in `research/deep-study-2026-11-14/REPORT.md`. Hard risk rules are unchanged.

**v3 change (Phase 2, 12 pre-registered variants, 0 post-hoc adds):** three ideas *did* clear a bar that also requires 2012–2023 not to be a hidden loss (OOS n≥40, avg R>0, PF≥1.20, ≥8/15 green years, and 2012–2023 avg R≥0 and PF≥1.0). They are now sections 5–7: a New York close-break of the completed London range *with* the daily+4H MA trend (OOS +0.13R, PF 1.23, 10/15 years, and 2012–2023 also +0.12R); FOMC continuation after the first 60 minutes (OOS +0.38R, PF 1.86, 11/15 years, thin sample); and a 20-day Donchian *long-only* core (OOS +0.34R, PF 1.74, 11/15 years). Two-way and 200-SMA-regime Donchian officially passed as well, but we operationalize long-only — shorts are not the source of that edge. Seven other Phase 2 ideas, including London-mid pullbacks, news fades, NFP continuation, and prior-day sweep-and-reclaim, stay on the watchlist. Details: `research/deep-study-2026-11-14/PHASE2.md`.

Those tests are still rule-based approximations, not a promise that live broker-spot trades will match the numbers. If a setup did not show a clear *and stable* edge, it is not an automatic trigger here.

Clock: **America/New_York** (COMEX). Add 9.5 hours for IST in US summer (EDT) or 10.5 hours in US winter (EST). High-impact US data is usually 08:30 ET (18:00 IST in summer, 19:00 IST in winter). FOMC is typically 14:00 ET.

---

## 1. Hard rules (never broken)

1. **One open trade at a time.** No averaging, no second position, no hedge.
2. **Risk 0.5% of current equity per trade.** Size from the *actual* stop distance at fill. If that would be below 0.01 lots, skip.
3. **Always a stop.** No mental stops. SL sits beyond structure, not a round number chosen for comfort.
4. **Do not take a trade that cannot offer at least 1.5R** to the first target at the planned fill. If slippage or a gap makes the live R:R worse than 1.5 at entry, skip.
5. **Scale:** close half at **1.5R (TP1)**, move the rest to **breakeven** (entry). Leave the runner to **3R** or to the next clear structure level if that level is between 1.5R and 3R.
6. **Daily loss stop: −2% realized.** No new trades that COMEX session. An open trade already on is managed to its SL/TP; we do not “revenge” a second ticket.
7. **Max two *new* attempts per session**, and only if the first is already closed. In practice a Donchian or a London-range break often holds overnight or longer, so most days are zero or one trade.
8. **Kill switch / `valid_until` / news blackout** in the decision file are binding. If any one of them says stand aside, stand aside — with the single, explicit exception in section 3 for the FOMC-continuation setup at 15:00 ET.

---

## 2. Chart process (before every decision)

Read in this order, gold only:

| TF | Question |
|----|----------|
| **Daily** | LH/LL or HH/HL? Close vs 50- and 200-day SMA? Close vs the prior 20-session high/low? Where is the last major swing, the prior day, and today's session extreme? |
| **4H** | Is 4H agreeing or is it the first bar against the daily? Mark 4H supply and demand (confirmed swings, breakdown/breakout origins). |
| **1H** | Location vs those zones, Asia range (once 03:00 ET is in), **London range (once 08:00 ET is in)**, prior-day high/low, rejection vs impulse. |
| **15M** | Trigger only. Two 15m rejection closes can stand in for one 1h close if the higher TF is already valid. Do not invent a setup from 15m alone. |

Also check the session (Asia / London / NY), the futures–spot basis (often $3–7; **publish zones in broker spot**), DXY/yields/news as context, and the economic calendar for the next 24 hours.

Default bias is **NONE**. A trade needs a named setup below, a stop, and 1.5R. “Price is in the zone” is not enough without a rejection or a close-break.

---

## 3. When *not* to trade

Stand aside (bias NONE) when any of these is true:

- No setup from sections 4–8 is present, or the only signal is a pullback/RSI pattern we do not automate.
- **High-impact US news blackout:** from **30 minutes before to 90 minutes after** 08:30 ET releases (NFP, CPI, PPI, GDP, PCE) and around FOMC (typically 13:30–15:30 ET). Do not *enter* inside the window, with one exception: the **FOMC continuation** setup in section 6 may enter at the **15:00 ET** open only, after the 14:00 bar has closed. An already-open, valid trade can be left on unless the thesis is the event itself.
- Inside the first 30 minutes of a session if price is still a one-sided impulse and there is no close back in range (the 13 Nov 2026 lesson: do not short a live rally just because it has reached a planned sell zone).
- Asia range is too tight (`< $5`) or too wide (stop would exceed ~3× 1h ATR, recently often ~$45–60). Skip the Asia breakout. The 2026-11-14 study did **not** find an edge in dropping this cap or in using a half-range stop so that wide days can still trade; wide days also have worse 1.5R continuation. Keep the skip as a sanity filter. The same $5 / 3× 1h ATR cap applies to the NY London-range break (section 5).
- The close that would trigger a breakout has already run more than **half the relevant range** (Asia for section 4, London for section 5) beyond the level — that is a chase. Wait for a later retest, or stand aside.
- After a −2% day, or after a messy gap through the planned stop.
- The last hour of the COMEX week (after 16:00 ET Friday) — do not *open* a new trade into the weekend. An already-open A-setup or NY London-range trade may be held; weekend holds of breakouts were profitable on average in the test, but gap risk is real (one historical stop slipped −1.1R). A Donchian long that triggers on Friday’s daily close is entered at the **Sunday 18:00 ET** open, so the Sunday gap *is* the entry — size from the actual stop at that fill, and skip if R:R to 1.5R is no longer there.
- Any doubt about the basis (spot vs `GC=F`) that would mis-place the zone by more than a few dollars.

---

## 4. A-setup — Asia-range breakout (qualified; not a 15-year edge)

**Status, 2026-11-14 v3:** this remains a setup whose *shape* we will still take when it is clean, but it is **not** a proven 15-year edge. On `GC=F` 1h, 2024-07-07 to 2026-11-13, the unfiltered book was 132 trades, 53.8% win rate, **+0.37R**, PF **1.79**, max DD **−3.4%** (London +0.53R). The same rules on spot XAUUSD in that window were still positive (+0.27R, PF 1.52). On spot walk-forward **2012–2026**, the same A-setup was **−0.03R**, PF 0.93, 6/15 years green, and **2012–2023 was −0.09R**. Almost all of the profit sat in 2024–2026. London-only, which looked best in the short futures sample, was negative on the long OOS (−0.04R).

The Phase 2 work did **not** rescue this Asia-range rule. What *did* hold on 2012–2026 is a different breakout: New York’s first close through the *London* range, with a hard daily+4H gate (section 5). Do not confuse the two.

Until later reviews show the 2024–2026 Asia edge holding up — or clearly dying — take this setup only when it is clean, prefer it *with* the 4H/daily trend rather than against it, and do not size it as if +0.37R were a long-run expectancy. If the next few months go stale, the default is back to **NONE**, not a wider set of weaker rules.

### Setup

1. Lock the **Asia range** at 03:00 ET (high/low from 18:00 ET the prior calendar evening through 03:00 ET). Do not use a still-forming Asia high/low.
2. In **London (03:00–08:00 ET, preferred)** or **early New York through ~08:00–09:00 ET**, wait for the **first 1h close** clearly outside that range, in a direction you will actually trade (below).
3. **Stop** goes beyond the *other* side of the Asia range, plus a small buffer (~0.15× 1h ATR). If that stop is narrower than $5 or wider than 3× 1h ATR, skip.
4. Entry is the next 1h open (or a slightly conservative zone around that open for the EA). Do not move the stop closer after entry just to make the size larger.

### Direction

- **Soft trend bias, not a hard daily-MA gate.** On the 2024–2026 samples, with-trend buys were the cleanest subset. On the 2012–2026 spot walk-forward, a hard D+4H MA gate (`A_trend_ma`) was the *least bad* pre-registered Phase 1 variant (OOS +0.10R, PF 1.17, 8/15 years) — but almost all of that P&L is again 2024–2026; 2012–2023 was scratch (−0.01R). It is a useful bias, not a 15-year licence for *this* Asia rule. (The hard D+4H gate *is* required for the NY London-range setup in section 5.)
- Default: trade the Asia close-break **in the direction of the current 4H structure** (4H HH/HL → only upside breaks; 4H LH/LL → only downside breaks). Be slower to take a clean break that fights both the daily and the 4H.
- A clean **London** close-break of the *Asia* range *against* a late daily MA trend may still be taken if the 4H has already turned and the range is orderly. Do not force a counter-trend NY late-morning break. Do not treat “London only” as a long-sample upgrade.

### Invalid / skip

- Second, third, or late re-break of the same Asia range the same day (the test only took the first close).
- Close already extended > 50% of the Asia range through the level.
- After 13:00 ET — no new Asia-breakout entries. 09:00 and 11:00 ET hours were the weak ones in the test; be pickier after the NY open. (Section 5 has its own 08:00–12:00 ET window and is not this rule.)
- 15m can refine the entry but cannot justify a breakout the 1h has not closed.

---

## 5. NY London-range break, with daily+4H trend (mechanical)

**Status, 2026-11-14 v3 — adopted.** This is the session setup that actually held on the long sample. HistData spot 1h, OOS 2012–2026: **286 trades**, 44.4% wins, **+0.134R**, PF **1.23**, max DD **−5.9%**, **10 of 15** years green. 2012–2023 was also positive (**+0.122R**, PF 1.21, 195 trades); 2024–2026 was **+0.161R**, PF 1.26. Average hold about 50 hours. The 4H-only twin missed the bar (OOS PF 1.13) and is not a licence to drop the daily filter. The in-sample warmup (2009–2011) was negative (−0.21R, 38 trades) — noted, not a reason to ignore the OOS bar we pre-registered. 2026 through 6 Nov is a red year so far (−0.11R, 22 trades).

### Setup

1. Lock the **London range** at 08:00 ET (high/low of 03:00–08:00 ET). Do not use a still-forming London high/low.
2. In **New York morning, 08:00–12:00 ET** (IST 18:00–21:00, ± DST), wait for the **first 1h close** clearly outside that range, **in the daily+4H MA trend** (close vs 50/200 on both daily and 4H: longs only when both are up, shorts only when both are down).
3. **Stop** goes beyond the *other* side of the London range, plus a small buffer (~0.15× 1h ATR). If that stop is narrower than $5 or wider than 3× 1h ATR, skip.
4. Skip if the close has already run more than **half the London range** beyond the level, or if the bar is inside a news blackout (including 08:30 ET releases).
5. Entry is the next 1h open. Same 1.5R / 3R scale.

### Invalid / skip

- Second or later close-break of the same London range the same day.
- 4H-only trend without daily agreement (tested; did not clear PF 1.20).
- After 12:00 ET — no new entries under this rule.
- A pullback to London mid / VWAP is **not** this setup (tested separately; failed the 2012–2023 check).

---

## 6. FOMC continuation after 60 minutes (mechanical, rare)

**Status, 2026-11-14 v3 — adopted, thin sample.** OOS 2012–2026: **62 trades** (about four a year), 58.1% wins, **+0.380R**, PF **1.86**, max DD **−2.6%**, **11 of 15** years green. 2012–2023 +0.369R / PF 1.82; 2024–2026 +0.419R / PF 1.96; in-sample also positive. Holds average ~50 hours. Yearly counts are small; 2014, 2022, and 2025 were red or weak. The fade twin lost badly (OOS −0.57R, PF 0.31) — do not fade.

### Setup

1. Only on a scheduled **FOMC** day (typically the 14:00 ET announcement).
2. Wait for the **14:00–15:00 ET** bar to close. Trade in the direction of that close versus the **13:00 close** (last close before 14:00).
3. **Stop** beyond that 14:00 bar’s extreme, plus the usual ATR buffer. Skip if the stop fails the $5 / 3× 1h ATR check or if 1.5R is not available.
4. Entry is the **15:00 ET** open. This is the only new entry allowed inside the generic FOMC blackout (13:30–15:30). Do not enter before 15:00, and do not enter other setups until 15:30.
5. Same 1.5R / 3R scale. NFP continuation was tested the same way and did **not** pass (recent years faded); do not generalize this rule to NFP, CPI, or PPI.

---

## 7. 20-day Donchian long-only (low-frequency core)

**Status, 2026-11-14 v3 — adopted, with an occupancy caveat.** OOS 2012–2026, longs only: **79 trades**, 51.9% wins, **+0.342R**, PF **1.74**, max DD **−3.5%**, **11 of 15** years green. 2012–2023 was **+0.168R**, PF 1.30 (58 trades) — not a 2024 residual — though 2024–2026 was much stronger (+0.822R, PF 4.25). In-sample already +0.33R. Average hold about **610 hours (~25 days)**.

Two-way Donchian (OOS +0.121R, PF 1.21) and the 200-SMA regime variant (OOS +0.156R, PF 1.29) officially met the same bar. We still **do not short Donchian breaks**: 2012–2023 for two-way was only +0.056R / PF 1.08, and for the regime variant was a hairline +0.007R / PF 1.004. The edge is the longs.

### Setup

1. On a completed session daily, the close is **above the prior 20 session highs** (excluding today).
2. Enter at the next **18:00 ET open** (Sunday 18:00 after a Friday close). Do not signal during the 17:00–18:00 break hour.
3. **Stop** is **2× daily ATR** below that open (minimum $10). Skip if the live stop after the Sunday/open gap no longer leaves 1.5R to TP1.
4. Same 1.5R / 3R scale. Longs only.

### Occupancy

Five or so signals a year with ~25-day holds can occupy the one-trade book for a large fraction of the year and block sections 5 and 6, which have more trades and much shorter holds. Take a fresh Donchian long only when no shorter adopted setup is open or clearly setting up. If a NY London-range break or an FOMC continuation is also available, prefer those and treat the Donchian break as trend confirmation, not as a second ticket. A standing “core + tactical” book would break the one-trade hard rule and is not adopted.

---

## 8. B-setup — NY liquidity sweep, with trend (optional, weak; not mechanical)

The unfiltered fade-every-sweep book **lost money** on the 2024–2026 futures sample (−0.16R, 36% drawdown) and again on the 2012–2026 spot walk-forward (OOS −0.06R, 5/15 years). With a D+4H trend filter it was only **scratch** on the short futures sample (+0.02R) and still slightly negative on the long OOS. NY-with-trend, the only slice previously kept, is OOS **−0.02R**, PF 0.95, 6/15 years, and was −0.10R in 2012–2023 (the 2024–2026 slice was again the only good one). Phase 2’s prior-day-only sweep-and-reclaim, even conditioned on regime, also failed (NY OOS −0.003R; London −0.27R). It does **not** earn a standalone mechanical slot. If it is used at all, keep it rare and discretionary:

- **New York session only** (London sweeps with the same filter lost −0.32R in Phase 1, and Phase 2 London PDH was worse).
- Sweep of the **prior-day or Asia high/low** by a meaningful amount (not a $0.50 tick; use at least ~0.15× 1h ATR), then a **close back inside**.
- Trade **with the higher-TF trend:** sell a sweep of highs in a downtrend; buy a sweep of lows in an uptrend. With-trend sells were +0.17R (small sample, 23 trades); with-trend buys were scratch.
- Stop beyond the sweep wick plus a buffer. Same 1.5R / 3R scale.
- Take this only if no adopted setup from sections 4–7 is in play or still valid.

---

## 9. What we do *not* auto-take

**Mechanical trend pullbacks** (1h rejection at a 4H/daily zone, in the MA trend) were **negative** on the 1h sample (−0.09R with the filter, −0.22R without). With-trend *buys* in the bull were the problem (−0.19R, 65 trades).

The only hint of edge is a **clear sell** of a 4H supply zone in an *established* daily LH/LL downtrend, after a **rejection close** (15 trades, +0.35R, plus a small 15m confirmation in the 2026 selloff). That is optional, discretionary, and must meet all of:

- Daily and 4H are already making lower highs / lower lows, not merely “below a lagging 200-SMA.”
- The zone is a real 4H or daily swing (or a breakdown origin), not a local 1h wiggle.
- There is a bearish 1h close (or two 15m closes) *inside* the zone — not a market order into a live impulse.
- Invalidation is a 1h close above the zone. SL sits above the rejection wick / zone top.
- If this conflicts with a live adopted setup from sections 4–7, the adopted setup wins.

**RSI oversold/overbought at a level is not a trade.** The control test lost −0.21R. RSI may support a stand-aside or a “wait for rejection” call; it does not authorize an entry by itself.

**Do not mechanically fade NFP or FOMC** after the first 30–60 minutes (Phase 2 fades lost money; FOMC fade OOS −0.57R). **Do not** treat a NY pullback to London mid, or a prior-day sweep-and-reclaim, as automatic — both failed the long-sample bar.

---

## 10. Entry, stop, and targets (how to write the decision)

- **Entry zone** in *spot* XAUUSD, with the futures–spot basis stated in the note. Keep the zone tight enough that a fill still leaves ≥ 1.5R to TP1 after a typical $0.20–0.40 spread.
- **SL** beyond structure (far side of the Asia range for section 4; far side of the London range for section 5; beyond the 14:00 FOMC bar for section 6; 2× daily ATR for a Donchian long; beyond the wick for a discretionary B or supply sell), plus a small ATR buffer where the rule calls for one. Do not tighten after a paper fill to juice size.
- **TP1 = 1.5R**, half off, stop of the runner to **entry**. **TP2 = 3R** or the next opposite swing if it sits between 1.5R and 3R.
- **`valid_until`** should expire before the next news blackout, before 13:00 ET for an Asia A-setup that has not triggered, or before 12:00 ET for a NY London-range setup that has not triggered. A FOMC-continuation zone is valid for the 15:00 open, not all afternoon. A Donchian long is valid at the 18:00 ET open only.
- One decision, one zone, one direction. If the idea is gone, publish **NONE** rather than leaving a stale bias.

---

## 11. Priority when more than one idea appears

1. News blackout / daily loss stop / kill switch → **NONE**, except the section 6 FOMC continuation at 15:00 ET.
2. **FOMC continuation** (section 6) if it is valid — rare, high expectancy, short hold.
3. Else **NY London-range break with daily+4H** (section 5) if it is valid and no trade is on. This is the workhorse.
4. Else **Asia-range A-setup** (section 4) if it is still valid and clean, as qualified in v2, and no later adopted setup has taken the slot.
5. Else a **fresh Donchian long** (section 7) at the 18:00 ET open, only if the book is otherwise empty. If a section 5 or 6 setup is also available, prefer those and use the Donchian break as regime confirmation, not a second ticket.
6. Else **B-setup** (section 8) or a *discretionary* downtrend supply rejection (section 9), only as written, and only if nothing above is on.
7. Else **NONE**.

Do not let a 25-day Donchian long starve sections 5 and 6. The backtest combo that looked at weaker pullbacks *first* blocked better breakouts; do not repeat that pattern with a slow core either.

---

## 12. Daily rhythm

- Recurring check every ~3 hours on weekdays is enough, with a compulsory read **before London (03:00 ET)** to lock the Asia range, another **at 08:00 ET** to lock the London range, and another **before 08:30 ET** if data is on the calendar.
- NY morning (08:00–12:00 ET / IST 18:00–21:00 ± DST): watch for the first 1h close through the London range with daily+4H agreement.
- If an Asia A-setup has not triggered by 13:00 ET, cancel it. If a NY London-range setup has not triggered by 12:00 ET, cancel it. Then NONE until the next session’s ranges are complete, unless section 6 applies later that day.
- **FOMC days:** stand aside 13:30–15:30 except for a possible 15:00 ET continuation entry. After the event, re-read D/4H/1H from scratch. Do not reuse a pre-news Asia or London-break zone.
- **18:00 ET** (Sunday reopen after Friday): if Friday’s daily closed above the prior 20-session high and the book is empty, consider the Donchian long at that open.
- Weekend: no new Friday 16:00 ET entries. Review open risk before the Sunday 18:00 ET reopen.

---

## 13. Tested and not adopted (2026-11-14)

These were pre-registered and checked on the 2012–2026 spot walk-forward. They are **not** playbook rules.

Phase 1:

- **Half-range stop** on a wide Asia range (so a $48 range can still trade): more trades, worse book (OOS −0.05R).
- **Dropping the 3× ATR width cap**, or tightening it to 2×: no durable edge (no-cap was scratch; 2× was worse).
- **Limit entry at a 38.2% or 50% retrace** of the close-break, or at the broken Asia level, instead of the next open: fill rates are high (86–93%), but a later 1.5R is rare (~10%, ~4% on wide days) and the books are OOS-negative.
- **Mechanical “rejection then retrace to the zone”** (the 13 Nov discretionary type): in a downtrend, a 38.2% limit fills more often than 50% (67% vs 59%), but after the fill 1.5R is only 2–6% and the stop is hit 39–46% of the time.
- **London-only** as a long-sample upgrade of the Asia A-setup: negative OOS, despite looking excellent on 2024–2026 futures.

Phase 2 (12 variants, 0 post-hoc; full tables in `PHASE2.md`):

- **4H-only NY London-range break** (OOS +0.08R, PF 1.13, 11/15 years) — close, not adopted; do not drop the daily half of the gate.
- **NY pullback to London mid with D+4H** (OOS +0.03R, PF 1.04; 2012–2023 −0.05R; 2024–2026 +0.22R; max DD −17%).
- **NFP continuation** after 60–90 minutes (OOS +0.09R, PF 1.14; 2012–2023 +0.19R, but 2024–2026 −0.11R).
- **NFP fade** (OOS −0.14R) and **FOMC fade** (OOS −0.57R, PF 0.31).
- **Prior-day high/low sweep-and-reclaim with D+4H**, NY (OOS −0.003R) or London (OOS −0.27R).
- **Donchian shorts**, including two-way and 200-SMA-regime shorts, even though those IDs formally passed: 2012–2023 contribution is thin; the operational C-rule is long-only.

---

## 14. Watchlist (not rules yet)

- Whether the 2024–2026 Asia A-setup edge *persists* after this study. If it fades, stand aside more, do not loosen filters.
- Whether 2026 stays weak for the NY London-range break (slightly red through 6 Nov) or reverts to the 2012–2025 pattern.
- NFP continuation: good in 2012–2023, poor in 2024–2026. Watch, do not start trading it.
- 4H-only NY London-range break (PF 1.13) — interesting, not a reason to loosen D+4H.
- Friday upward drift on session daily (2012–2026 close–open about +$1, 55% up). Do not turn this into a Friday long.
- A verified CPI/PPI calendar, and Dukascopy / broker M1 for 2003–2008 and for days HistData has not published yet.
- Futures–spot basis around GC rolls can be tens of dollars; always recompute before publishing a zone.
- A second “core trend” slot so a Donchian long can run beside the tactical book. Not adopted; would need an explicit risk-budget decision.

---

## 15. What this book does not claim

The original supporting test used `GC=F` 1h history of about 28 months, a cost model, no full news calendar, and conservative same-bar stops. The 2026-11-14 studies added ~17 years of spot XAUUSD (HistData, 2009-03 to 2026-11-06) and a 2012–2026 walk-forward, then a 12-variant Phase 2 search with a pre-registered bar. The file still has no official CPI/PPI calendar, and 7–13 Nov 2026 is futures-only. FOMC continuation has only 62 OOS trades. Live trading is still a human (or AI) chart read plus the EA’s hard caps — not a fully automated signal bot. If future checks show an adopted window going stale, the default is back to **NONE**, not a wider set of weaker rules.

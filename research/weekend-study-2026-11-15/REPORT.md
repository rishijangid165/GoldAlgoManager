# Weekend study 2026-11-15: full broker M1, same-bar resolution, pre-registered new ideas

**In short.**
1. The full MetaQuotes-Demo XAUUSD history from 2004 to 2026 is now on the box: 7.1 M M1 bars, decoded read-only from the terminal's own files.
2. With every trade managed minute by minute, the conservative same-bar rule turned out not to matter. It touched only 0–2 trades per setup.
3. FOMC continuation and the Donchian-20 long still pass the bar. NY London-range break and Asia + D+4H still miss it, at PF 1.18–1.19.
4. Of the 14 new or variant ideas and 12 exit variants, **none survives the multiple-testing correction**.
5. Two realism findings matter more than any new idea:
   - **The live EA's Friday auto-close** is harmless or even helpful for FOMC and Donchian, but cuts NY and Asia to roughly break-even in 2012–2023.
   - **The live EA's post-TP1 trailing** lowers expectancy on three of the four setups.

Pre-registration: `PREREGISTRATION.md`, committed in `e2d7509` at 2026-11-14 12:08:55 IST, before any P&L was computed. Its header says "~12:45 IST"; that was a typo, and the commit time is the record. Code: `wdata.py`, `m1engine.py`, `study.py`. Results: `results/`. The whole run takes about 45 seconds on the box.

## 1. Data depth

| Source | M1 | M5 | M15 | H1 |
|---|---|---|---|---|
| `copy_rates_range` on the running terminal ("Max bars" = Unlimited, no restart) | 100,000 | 100,000 | 100,000 | 100,000 |
| Decoded terminal `.hcc` base files (read-only copies) | **7,100,401** | **1,505,705** | **515,011** | **130,415** |
| Range (UTC) | 2004-06-11 → 2026-11-13 20:59 | same | same | same |

- **Why the API still stops at 100k.** The terminal reports `maxbars = 100000000`, but the chart caches (`cache/*.hc`, exactly 100k×60 bytes) were built under the old cap and are only rebuilt on a restart, which we must not do.
- **How the full history was read.** The full M1 history sits in yearly `.hcc` files. `hcc_reader.py` decodes those; `build_deep_data.py` resamples them on the server clock and converts to ET (server time = ET+7).
- **Validation.** The decoded H1 matches the API H1 exactly on all 100,000 overlapping bars. The decoded M1 matches the API M1 exactly on all 100,000 overlapping bars, spread included.
- **Data caveats:**
  - M1 is sparse before 2009: 80k bars in 2004, 140–240k in 2005–07, 316–356k a year from 2009.
  - **Stored spread is 0 before 2010, and looks compressed in old history.** The 2026 Jan–Jun median is 4 points, against 17 points in the live Jul–Nov window.
  - **Spread model.** Every fill therefore uses max(recorded M1 spread, live-window median for that ET hour), plus $0.10 slippage per fill. The hourly floor is $0.13–0.30, the same profile as the 2026-11-14 retest. Bars are bid: longs fill at ask, shorts at bid, and exits are on the correct side.
- **CPI calendar.** Dates are the ALFRED `CPIAUCSL` vintage dates; where a month has two, the later one is used. That gives 269 releases from 2004-07 to 2026-10, with no Nov 2025 release (`cpi_dates.csv`). NFP is the first-Friday proxy, as before.
- **CSVs.** The CSVs are in `data/broker/` and are **not** committed (git-ignored). `data/broker/manifest_full.json` is committed.

## 2. Part A: v3 setups on broker data with same-bar resolution

OOS = 2012-01-01 → 2026-11-13. "Back" = 2005–2011 backcast, which is not part of the bar. Green years are years with positive avg R.

| Setup | Engine | OOS n | avg R | PF | MaxDD | Green | 2012–23 avg R / PF | 2024–26 avg R | Back avg R (n) | Bar |
|---|---|---|---|---|---|---|---|---|---|---|
| NY London-range break D+4H | old HistData study (v3) | 286 | +0.134 | 1.23 | 5.9% | 10/15 | +0.122 / 1.21 | +0.161 | — | pass |
| | H1 conservative, broker | 286 | +0.114 | 1.197 | 8.2% | 8/15 | +0.052 / 1.09 | +0.253 | +0.015 (80) | **fail** (PF) |
| | **M1-managed, broker** | 286 | +0.106 | 1.180 | 8.1% | 7/15 | +0.025 / 1.04 | +0.288 | +0.007 (80) | **fail** |
| | M1 + EA Friday close | 300 | +0.057 | 1.110 | 9.7% | 8/15 | −0.002 / 0.996 | +0.185 | +0.038 (80) | **fail** |
| FOMC continuation | old (v3) | 62 | +0.380 | 1.86 | 2.6% | 11/15 | +0.369 / 1.82 | +0.419 | — | pass |
| | H1 conservative, broker | 68 | +0.305 | 1.676 | 2.3% | 10/15 | +0.302 / 1.68 | +0.316 | +0.099 (19) | pass |
| | **M1-managed, broker** | 68 | +0.321 | 1.720 | 2.3% | 10/15 | +0.320 / 1.73 | +0.325 | +0.093 (19) | **pass** |
| | M1 + EA Friday close | 67 | +0.426 | 2.047 | 2.0% | 13/15 | +0.455 / 2.17 | +0.325 | +0.155 (18) | pass |
| Donchian-20 long | old (v3) | 79 | +0.342 | 1.74 | 3.5% | 11/15 | +0.168 / 1.30 | +0.822 | — | pass |
| | H1 conservative, broker | 82 | +0.276 | 1.536 | 4.9% | 11/15 | +0.076 / 1.13 | +0.823 | +0.611 (39) | pass |
| | **M1-managed, broker** | 80 | +0.266 | 1.518 | 4.9% | 11/15 | +0.069 / 1.12 | +0.820 | +0.612 (38) | **pass** |
| | M1 + EA Friday close | 160 | +0.174 | 1.879 | 2.0% | 10/15 | +0.107 / 1.52 | +0.376 | +0.588 (42) | pass |
| Asia breakout + D+4H (`A_trend_ma`) | old HistData Phase 1 | 319 | +0.096 | 1.17 | — | 8/15 | −0.01 | — | — | fail |
| | H1 conservative, broker | 327 | +0.113 | 1.198 | 7.4% | 8/15 | +0.023 / 1.04 | +0.425 | +0.065 (131) | **fail** (PF) |
| | **M1-managed, broker** | 326 | +0.109 | 1.190 | 9.9% | 8/15 | +0.017 / 1.03 | +0.427 | +0.075 (130) | **fail** |
| | M1 + EA Friday close | 333 | +0.025 | 1.047 | 10.4% | 7/15 | −0.019 / 0.97 | +0.182 | +0.037 (132) | **fail** |

### 2a. Same-bar ambiguity: resolved, and it does not matter

- **How often it happens.** Under the old H1 engine, the stop and a target fell inside the same hour on only **1** NY trade, **0** FOMC, **0** Donchian and **2** Asia trades. On the M1 path, 0–1 trades per setup still had both inside one minute; those were also counted stop-first.
- **What drives the gap.** The small difference between "H1 conservative" and "M1-managed" (NY −0.008R, FOMC +0.016R, Donchian −0.010R, Asia −0.004R) comes from the bid/ask fill model, not from same-bar order. Stops and targets now trigger on the correct side of the spread, and 2011–2015 spreads were $0.30–0.70.
- **Conclusion.** The old conservative same-bar rule was not hiding an edge, and it was not flattering the books either.

### 2b. Verdicts on the v3 setups

- **FOMC continuation: holds.** Passes on M1, every way it was tested. Thin: about 4–5 trades a year.
- **Donchian-20 long: holds.** But 2012–2023 alone is only +0.07R / PF 1.12. Most of its weight is the 2005–2011 and 2024–26 gold bull markets. It is still above the 2012–2023 floor (≥ 0R, PF ≥ 1.0).
- **NY London-range break: fails again on broker data.** This is a second, independent check, now with minute-level management and the stored spread. PF is 1.18 against the 1.20 bar, green years 7/15, and 2012–2023 only +0.025R. Its 2012–2023 yearly record is 4 green and 8 red. 2024–26 carries it.
  - The **15m version (F13)** is not better: OOS +0.118R, PF 1.207, but 2012–2023 is −0.008R.
- **Asia breakout + D+4H: still a knife-edge fail.** PF 1.19, and 2012–2023 is +0.017R.
  - The **15m version (F14)**: PF 1.218, but only 7/15 green years, and 2012–2023 is +0.005R.
  - It also only works in 2024–26, so it is rejected by rule.

### R1. What the live EA actually does: Friday auto-close

- **What the EA does.** GoldAIBridge v1.02+ flattens GoldAI trades 45 minutes before the Friday session end, which is 16:15 ET. It also blocks new entries from 14:15 ET Friday. All earlier backtests held positions over weekends.
- **How long trades are held** (M1 book):

  | Setup | Median hold | Mean hold | Trades held over a weekend |
  |---|---|---|---|
  | NY London-range break | 25 h | 51 h | 31% |
  | FOMC continuation | 17 h | — | 22% |
  | Asia + D+4H | 25 h | — | 26% |
  | Donchian-20 long | 456 h (19 days) | — | 93% |

- **Effect on each setup.** FOMC improves (13/15 green years, PF 2.05). Donchian keeps passing: more trades because it re-enters after Friday, lower avg R, but PF 1.88 and DD 2.0%. **NY and Asia fall to about 0R in 2012–2023** (−0.002R and −0.019R).
- This is not something to "adopt". It is what the live book does today, and it makes the NY and Asia verdicts stricter, not looser.

## 3. Family F: pre-registered new ideas (Holm over 14; α 0.05)

| ID | OOS n | avg R | PF | Green | 2012–23 avg R | 2024–26 | Back | p (boot) | Holm thr | Bar | Holm | Adopt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 CPI cont 60 min | 82 | −0.168 | 0.74 | 5/15 | −0.164 | −0.178 | +0.03 | 0.90 | 0.050 | no | no | **no** |
| F2 CPI cont 30 min | 82 | +0.170 | 1.33 | 9/15 | +0.279 | −0.042 | −0.30 | 0.12 | 0.0071 | yes | no | **no** |
| F3 NFP cont 30 min | 78 | +0.009 | 1.02 | 8/15 | +0.096 | −0.185 | −0.25 | 0.48 | 0.0125 | no | no | **no** |
| F4 NFP cont 60 min (M15) | 81 | +0.162 | 1.29 | 7/15 | +0.056 | +0.428 | −0.41 | 0.16 | 0.0083 | no | no | **no** |
| F5 prior-day H/L break at NY open, D+4H | 68 | +0.229 | 1.45 | 8/14 | +0.151 | +0.479 | +0.07 | 0.083 | 0.0056 | yes | no | **no** |
| F6 NY break, ATR pct ≤ 80 | 205 | +0.135 | 1.24 | 7/15 | +0.040 | +0.383 | +0.10 | 0.080 | 0.0050 | no | no | **no** |
| F7 NY break, ATR pct ≥ 20 | 241 | +0.109 | 1.18 | 8/15 | +0.007 | +0.296 | +0.01 | 0.12 | 0.0063 | no | no | **no** |
| F8 Asia trend, ATR pct ≤ 80 | 248 | +0.060 | 1.10 | 7/15 | +0.009 | +0.255 | +0.06 | 0.25 | 0.0100 | no | no | **no** |
| F9 Asia trend, ATR pct ≥ 20 | 271 | +0.140 | 1.25 | 8/15 | +0.028 | +0.463 | +0.14 | 0.046 | 0.0042 | yes | no | **no** |
| F10 Donchian, ATR pct ≤ 80 | 61 | +0.429 | 1.87 | 11/15 | +0.222 | +1.124 | +0.42 | **0.011** | 0.0036 | yes | no | **no** (closest) |
| F11 weekly gap fade | 56 | −0.150 | 0.78 | 4/15 | −0.052 | −0.550 | +0.14 | 0.82 | 0.025 | no | no | **no** |
| F12 weekly gap go | 56 | −0.083 | 0.87 | 6/15 | −0.080 | −0.096 | −0.32 | 0.68 | 0.0167 | no | no | **no** |
| F13 NY London break on 15m | 385 | +0.118 | 1.21 | 10/15 | −0.008 | +0.369 | +0.21 | 0.047 | 0.0045 | no | no | **no** |
| F14 Asia trend break on 15m | 382 | +0.124 | 1.22 | 7/15 | +0.005 | +0.569 | +0.13 | 0.036 | 0.0038 | no | no | **no** |

**Nothing survives Holm.** The best raw p is 0.011 (F10), against a first-step threshold of 0.0036. With roughly 4–20 trades a year, an honest +0.2R edge needs years more data before it can clear a 14-test correction. That is the point of the correction.

- **Bar passes that failed Holm** (F2, F5, F9, F10) go to the watchlist, with these flags:
  - F2 (CPI 30 min) is **negative in 2024–26 and in the backcast**. It looks like an old-regime effect.
  - F9 is the A4 Asia rule, which fails the bar on its own. A volatility filter on a weak base is not a new edge.
  - F5 (prior-day H/L break) has only about 5 trades a year, and 2014, 2017 and 2021 were heavy losers.
  - F10 (Donchian, skip the top-20% ATR days) is the most interesting: 11/15 green, +0.22R in 2012–2023, positive backcast. It drops 19 of 80 trades.
- **Weekly gaps** (|gap| ≥ max($3, 0.25 × D-ATR), 73 gaps since 2012):
  - Fill rates: 10% fill in the first hour, 53% by the end of the Sunday session, 44% by the Monday NY open.
  - Neither fading nor following the gap is an edge (F11/F12).
  - Note that "by the end of the Sunday session" is a longer window than "by the Monday NY open". The Sunday session runs to 17:00 ET Monday, so 53% > 44% is consistent.

## 4. Family X: exits on fixed entry lists (Holm over 12; paired ΔR)

| Setup \| exit | OOS avg R | PF | MaxDD | Green | 2012–23 | ΔR vs baseline | p(ΔR>0) | Holm thr | Adopt |
|---|---|---|---|---|---|---|---|---|---|
| NY \| X1 EA trail | +0.055 | 1.09 | 8.4% | 8/15 | +0.015 | **−0.051** | 0.97 | 0.050 | no |
| NY \| X2 fixed 2R | +0.109 | 1.17 | 6.0% | 10/15 | +0.074 | +0.003 | 0.46 | 0.0071 | no |
| NY \| X3 chandelier | +0.104 | 1.20 | 8.0% | 7/15 | +0.024 | −0.002 | 0.52 | 0.0083 | no |
| FOMC \| X1 EA trail | +0.425 | 1.95 | 1.8% | 11/15 | +0.417 | +0.104 | 0.043 | 0.0056 | no |
| FOMC \| X2 fixed 2R | +0.489 | 1.97 | 3.0% | 11/15 | +0.461 | +0.169 | 0.035 | 0.0050 | no |
| FOMC \| X3 chandelier | +0.613 | 2.47 | 2.3% | 13/15 | +0.611 | +0.292 | **0.010** | 0.0042 | no (closest) |
| Donchian \| X1 EA trail | +0.222 | 1.43 | 5.4% | 9/15 | +0.020 | **−0.044** | 0.77 | 0.010 | no |
| Donchian \| X2 fixed 2R | +0.393 | 1.73 | 4.0% | 8/15 | +0.126 | +0.127 | 0.031 | 0.0045 | no |
| Donchian \| X3 chandelier | +0.141 | 1.31 | 4.7% | 7/15 | +0.013 | −0.125 | 0.90 | 0.025 | no |
| Asia \| X1 EA trail | +0.087 | 1.15 | 10.0% | 10/15 | +0.000 | **−0.022** | 0.80 | 0.0125 | no |
| Asia \| X2 fixed 2R | +0.078 | 1.12 | 11.8% | 9/15 | −0.001 | −0.031 | 0.81 | 0.0167 | no |
| Asia \| X3 chandelier | +0.231 | 1.46 | 7.0% | 11/15 | +0.196 | +0.122 | 0.060 | 0.0063 | no |

- **No exit change survives Holm.** The baseline TP1 1.5R + BE + TP2 3R / next level stays the tested exit.
- **The live EA trail (X1, which v1.03.1 runs by default) is not the tested exit.** It lowers OOS expectancy on NY (−0.051R; one-sided p of harm 0.031, uncorrected), Donchian (−0.044R) and Asia (−0.022R). It only helps FOMC (+0.104R, not significant).
- **This is a live/backtest mismatch, not a research finding to adopt.** See the proposal file.

## 5. Descriptives (no rules taken from these)

- **Session drift (OOS, % per session):**
  - Asia (18:00–03:00 ET) is +0.034% a session (t = 4.3, survives Holm within the table). It is positive in both 2012–23 (+0.016%, p = 0.02) and 2024–26 (+0.110%), with 8 of 12 years positive in 2012–23.
  - London and NY are flat.
  - This is the well-known overnight drift in gold. It is mostly a 2024–26 phenomenon in size. It is logged as a hypothesis for the next pre-registration, not as a rule.
- **Weekday (whole session):** no weekday survives Holm. Friday +0.07% (p = 0.08) is the same "Friday drift" already on the watchlist.
- **Setup by weekday** (D2): NY breaks taken on a Wednesday were −0.28R (57 trades), and Asia breaks on a Wednesday −0.03R. These are post-hoc slices with no correction, so do not filter on them.

## 6. What this means for the playbook (v3.2)

Changes made, all evidence-driven, none loosening a rule:

1. **§5 NY London-range break: "adopted" → "probation".** It has failed the pre-registered bar on two independent broker checks (H1 PF 1.197; M1 PF 1.180, 7/15 green years). 2012–2023 is about 0R once the live Friday close is applied. The rules are unchanged, and it stays in the paper tracker. The forward record decides: demote it to watchlist if the paper/live book is flat or negative after about 15 trades. This is the retest's recommendation, now confirmed.
2. **§6 FOMC and §7 Donchian:** status lines updated with the broker M1 numbers, including the result with the EA Friday close. Both still pass.
3. **§3 weekend text:** brought in line with what the EA does. GoldAI trades are flattened at about 16:15 ET Friday, and Donchian re-enters on Sunday 18:00 only on a fresh signal. Both are tested here and still pass.
4. **§4 Asia:** the status note now has the broker M1 numbers. It is still qualified, not an edge.
5. **§10:** notes that the EA's post-TP1 trail is **not** the tested exit, pending the owner's decision.
6. **§13 and §14:** tested-and-not-adopted, and new watchlist items (F2, F5, F10, FOMC exits, Asia chandelier, Asia overnight drift).
7. **§15:** data-source update (full broker M1; CPI calendar now exists).
8. **§16 (manual trades) is untouched.**

The exact text proposals that need an owner decision are in `PROPOSALS.md`.

## 7. Limitations

- **Before 2010** there is no stored spread, so the floor profile is used, and M1 is sparse before 2009. The backcast is indicative only.
- **The "walk-forward"** here means fixed rules, chosen in 2026-11-14 Phase 1/2, evaluated year by year on 2012–2026. No parameters were re-fitted, so there is no in-sample optimisation to leak. But the v3 rules were themselves chosen after looking at 2012–2026 HistData, so these Part A numbers are a robustness check, not fresh OOS.
- **Daily 2% loss stop:** not modelled in the M1 engine. It never binds with one trade at 0.5% risk.
- **NFP** dates are a first-Friday proxy, as before. Some months, BLS publishes on the second Friday.
- **Single source:** one broker's quotes. Spot quotes differ slightly between brokers.

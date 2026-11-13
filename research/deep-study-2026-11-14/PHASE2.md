# Phase 2 — pre-registered setup search (2026-11-14)

HistData spot XAUUSD 1h, 2009-12-11 to 2026-11-06 (America/New_York). Walk-forward: 2009–2011 is warmup / in-sample only; out-of-sample is 2012–2026. Costs and risk match the existing engine: $0.25 spread + $0.10 slippage per fill, 0.5% equity risk, $100k start, 100 oz/lot, TP1 1.5R half-off then breakeven, TP2 3R, one trade at a time, 2% daily loss stop, conservative same-bar stop-first. Signals at bar close, entry next open, except the Donchian family, which enters at the 18:00 ET open of the just-closed daily (the 17:00 hour is the COMEX break, so the stock engine would miss it).

This note is the Phase 2 record. Phase 1 (Asia A-setup, retrace books, 13 Nov post-mortem) is in `REPORT.md`. Playbook changes are in `research/playbook.md` v3.

## Pre-registration

The variant list and the adoption bar were fixed in `phase2_setups.py` before any Phase 2 P&L was computed. **12 variants were tested. 0 were added after seeing results.**

Adoption bar (includes the Phase 1 lesson that a 2024–2026-only book is not enough):

- OOS 2012–2026: n ≥ 40, average R > 0, profit factor ≥ 1.20
- Stability: at least 8 of 15 OOS years with average R > 0
- Regime check: 2012–2023 also average R ≥ 0, PF ≥ 1.0, and n ≥ 20

Fail any one item and the idea is watchlist only.

NY morning was pre-registered as 08:00–12:00 ET so it covers IST 18:00–21:00 under both DST offsets. London mid is used instead of VWAP (HistData volume is not true volume). The C-family stop cap is 4× daily ATR (stops are 2× daily ATR by construction); a 3× *1h* ATR cap would have blocked them.

### The 12 variants

| ID | Family | Rule (short) |
|----|--------|----------------|
| `A_ny_lon_brk_d4h` | A | First NY 08:00–12:00 ET 1h close beyond the completed London range, with daily+4H MA trend, far-side London stop, 3× 1h ATR cap, no 50% chase, news blackout on |
| `A_ny_lon_brk_h4` | A | Same, 4H-only trend |
| `A_ny_lon_mid_pb` | A | First NY touch of London mid with a rejection close (close_loc ≥ 0.60 / ≤ 0.40), D+4H, stop beyond the London extreme |
| `B_nfp_cont` | B | NFP: signal at the 09:00 ET bar close (~60–90 min after 08:30), direction vs the 07:00 close, stop beyond the 08:00–10:00 window extreme |
| `B_nfp_fade` | B | Same timing, opposite direction |
| `B_fomc_cont` | B | FOMC: signal at the 14:00 ET bar close (60 min after 14:00), direction vs the 13:00 close, stop beyond that bar’s extreme |
| `B_fomc_fade` | B | Same timing, opposite direction |
| `C_donch20` | C | 20-session Donchian: completed daily close vs the prior 20-day high/low (excluding today); enter 18:00 ET open; stop 2× daily ATR (min $10) |
| `C_donch20_long` | C | Same, longs only |
| `C_donch20_reg` | C | Same, longs only above the daily 200-SMA, shorts only below it |
| `D_pdh_ny_reg` | D | Prior-day high/low (not Asia) sweep and close back, D+4H, New York only, news blackout on |
| `D_pdh_lon_reg` | D | Same, London only |

Family B runs with the engine news filter off because the entry is *after* the event by design.

## Headline result

**5 of 12 met the pre-registered bar. 7 go to the watchlist.**

Adopted: `A_ny_lon_brk_d4h`, `B_fomc_cont`, `C_donch20`, `C_donch20_long`, `C_donch20_reg`.

Operational playbook choice inside family C: **long-only is the C-rule we will actually take.** Two-way and the 200-SMA regime variant officially passed, but almost all of their 2012–2023 edge (and then some) is in the longs. Short Donchian breaks are not a core rule.

## OOS scoreboard (2012–2026)

Average R is expectancy R in this engine. Max DD and end equity are on the $100k, 0.5% risk book. 2026 is through 6 Nov.

| Variant | n | Win % | Avg R | PF | Max DD | 2012–23 Avg R / PF | 2024–26 Avg R | Green years | Verdict |
|---------|--:|------:|------:|---:|-------:|--------------------:|--------------:|------------:|---------|
| A_ny_lon_brk_d4h | 286 | 44.4 | +0.134 | 1.23 | −5.9% | +0.122 / 1.21 | +0.161 | 10/15 | **Adopt** |
| A_ny_lon_brk_h4 | 504 | 43.5 | +0.084 | 1.13 | −6.5% | +0.102 / 1.17 | +0.035 | 11/15 | Watchlist (PF 1.13) |
| A_ny_lon_mid_pb | 542 | 41.7 | +0.028 | 1.04 | −16.8% | −0.047 / 0.92 | +0.223 | 7/15 | Watchlist (2024–26 only) |
| B_nfp_cont | 77 | 45.5 | +0.089 | 1.14 | −5.0% | +0.186 / 1.34 | −0.115 | 8/15 | Watchlist (PF 1.14; faded recently) |
| B_nfp_fade | 73 | 35.6 | −0.139 | 0.78 | −6.6% | −0.121 / 0.81 | −0.182 | 6/15 | Watchlist |
| B_fomc_cont | 62 | 58.1 | +0.380 | 1.86 | −2.6% | +0.369 / 1.82 | +0.419 | 11/15 | **Adopt** |
| B_fomc_fade | 36 | 19.4 | −0.568 | 0.31 | −9.3% | −0.597 / 0.30 | −0.515 | 1/13 | Watchlist (also n<40) |
| C_donch20 | 128 | 46.9 | +0.121 | 1.21 | −7.0% | +0.056 / 1.08 | +0.316 | 9/15 | **Adopt** (formal; two-way is weak pre-2024) |
| C_donch20_long | 79 | 51.9 | +0.342 | 1.74 | −3.5% | +0.168 / 1.30 | +0.822 | 11/15 | **Adopt (C-core)** |
| C_donch20_reg | 110 | 46.4 | +0.156 | 1.29 | −7.0% | +0.007 / 1.00 | +0.721 | 10/15 | **Adopt** (formal; 2012–23 is a hairline pass) |
| D_pdh_ny_reg | 147 | 42.2 | −0.003 | 0.99 | −7.0% | −0.057 / 0.90 | +0.109 | 7/14 | Watchlist |
| D_pdh_lon_reg | 55 | 32.7 | −0.269 | 0.60 | −6.5% | −0.368 / 0.49 | −0.141 | 3/12 | Watchlist |

## In-sample vs out-of-sample

| Variant | IS 2009–2011 n / Avg R / PF | OOS 2012–2026 n / Avg R / PF |
|---------|-----------------------------|------------------------------|
| A_ny_lon_brk_d4h | 38 / −0.211 / 0.70 | 286 / +0.134 / 1.23 |
| A_ny_lon_brk_h4 | 77 / −0.113 / 0.81 | 504 / +0.084 / 1.13 |
| A_ny_lon_mid_pb | 81 / −0.133 / 0.78 | 542 / +0.028 / 1.04 |
| B_nfp_cont | 14 / −0.059 / 0.89 | 77 / +0.089 / 1.14 |
| B_nfp_fade | 6 / −0.172 / 0.74 | 73 / −0.139 / 0.78 |
| B_fomc_cont | 12 / +0.477 / 1.91 | 62 / +0.380 / 1.86 |
| B_fomc_fade | 6 / −1.029 / 0.00 | 36 / −0.568 / 0.31 |
| C_donch20 | 23 / −0.075 / 0.91 | 128 / +0.121 / 1.21 |
| C_donch20_long | 15 / +0.331 / 1.63 | 79 / +0.342 / 1.74 |
| C_donch20_reg | 16 / +0.247 / 1.45 | 110 / +0.156 / 1.29 |
| D_pdh_ny_reg | 31 / +0.070 / 1.11 | 147 / −0.003 / 0.99 |
| D_pdh_lon_reg | 7 / −0.563 / 0.36 | 55 / −0.269 / 0.60 |

The adoption bar was OOS-only by design (2009–2011 is warmup). Still worth saying out loud: **the adopted NY London-range book lost money in the warmup window** (−0.21R, 38 trades). FOMC continuation and Donchian long-only were already positive in-sample.

## Adopted setups, in more detail

### A — NY close-break of the London range, daily+4H trend

This is the most even session idea we have on the long sample. 2012–2023 (+0.122R, PF 1.21, 195 trades) and 2024–2026 (+0.161R, PF 1.26, 91 trades) are in the same neighbourhood, unlike the Asia A-setup, which was a 2024–2026 story. About 19 trades per OOS year. Average hold ~50 hours. TP2 hit 26% of the time.

Requiring *both* daily and 4H trend is what cleared the bar. The 4H-only twin has more trades (504) and 11 green years, but OOS PF 1.13 misses 1.20, and 2024–2026 faded to +0.035R. We do not loosen the filter after the fact.

Yearly average R (OOS): 2012 −0.08, 2013 +0.24, 2014 +0.07, 2015 +0.24, 2016 +0.48, 2017 −1.03 (one trade), 2018 +2.22 (two trades), 2019 +0.02, 2020 +0.11, 2021 −0.11, 2022 −0.09, 2023 +0.22, 2024 +0.20, 2025 +0.28, **2026 −0.11** (22 trades, through 6 Nov). Red years are real; 2026 year-to-date is one of them. Stability is “most years,” not “every year.”

Rule as tested: lock the London high/low at 08:00 ET. In 08:00–12:00 ET, take the first 1h close outside that range, only with the daily+4H MA trend, skip if the close has already run more than half the London range, skip inside the news blackout, stop beyond the far side of the London range plus the usual ATR buffer, skip if the stop is under $5 or over 3× 1h ATR. Entry is the next 1h open.

### B — FOMC continuation after 60 minutes

Strongest expectancy, smallest adopted sample. OOS 62 trades (about four a year), 58% wins, +0.38R, PF 1.86, max DD only −2.6%. 2012–2023 and 2024–2026 agree (+0.37R / +0.42R). In-sample was also positive. TP2 hit 26%. Average hold ~50 hours (2024–2026 holds were much shorter, ~10 hours).

Yearly counts are thin (often 1–6 trades). Red or scratch years: 2014 (−0.44R, n=3), 2021 (−0.03R, n=5), 2022 (−0.67R, n=5), 2025 (−0.18R, n=6). Eleven green years still meet the bar, but this is not a high-frequency licence — it is a rare event trade.

The fade twin is unambiguously bad (OOS −0.57R, PF 0.31, 1/13 green years). Do not fade FOMC after the first hour.

Rule as tested: on a scheduled FOMC day, wait for the 14:00–15:00 ET bar to close. Trade in the direction of that close versus the 13:00 close (the last close before 14:00). Stop beyond that 14:00 bar’s extreme plus a buffer. Entry is the 15:00 ET open. This is *inside* the playbook’s generic “90 minutes after FOMC” stand-aside window (13:30–15:30). The playbook now carves an explicit exception for this one setup only; other entries stay blocked until 15:30.

### C — 20-day Donchian, long-only as the core

Gold’s multi-year upward drift was the pre-registered reason to test a low-frequency breakout. Long-only is the cleanest of the three:

- OOS 79 trades, 51.9% wins, **+0.342R**, PF **1.74**, max DD **−3.5%**, 11/15 green years
- 2012–2023: 58 trades, +0.168R, PF 1.30 (real, not a 2024 residual)
- 2024–2026: 21 trades, +0.822R, PF 4.25, 71% wins — much stronger in the recent bull, as expected, but not the whole story
- In-sample already +0.331R
- Average hold ~610 hours (~25 days). TP2 29%

Two-way Donchian officially passes (OOS +0.121R, PF 1.21, 9/15) but 2012–2023 is only +0.056R / PF 1.08. The 200-SMA regime variant also officially passes (OOS +0.156R, PF 1.29, 10/15) but 2012–2023 is a hairline +0.007R / PF 1.004 — almost all of its extra P&L vs long-only is recent, and adding shorts did not help the pre-2024 book. We therefore **do not short Donchian breaks** as a playbook rule, even though those two IDs met the letter of the bar.

Weak long-only years: 2013 (n=2, −1.00R), 2015 (n=4, −1.01R), 2021 (n=4, −0.18R). 2014 was scratch.

Rule as tested: when a completed session daily closes above the prior 20 session highs (excluding today), enter at the next 18:00 ET open (Sunday reopen after a Friday close). Stop is 2× daily ATR, at least $10, capped at 4× daily ATR. Same 1.5R / 3R scale. Weekend gap risk is inside the test (the Sunday open *is* the entry).

Occupancy warning: ~5 long signals a year × ~25-day holds can keep the one-trade book busy for a large fraction of the year and starve the NY London-range and FOMC books, which have more trades and much shorter holds. See the process recommendation below.

## Watchlist (tested, not adopted)

- **4H-only NY London-range break** — close, not over the line (OOS PF 1.13). Do not loosen D+4H after seeing this.
- **NY pullback to London mid** — the Phase 1 pattern again: 2024–2026 +0.22R / PF 1.37, but 2012–2023 −0.05R / PF 0.92, max DD −17%. Not a rule.
- **NFP continuation** — the unusual one: *good* in 2012–2023 (+0.19R, PF 1.34) and *poor* in 2024–2026 (−0.11R, PF 0.81). OOS PF 1.14 misses 1.20. Watch whether the recent fade persists; do not start trading it because the earlier decade looked fine.
- **NFP fade and FOMC fade** — both lose, FOMC fade badly. After the first hour, do not fade these events mechanically.
- **Prior-day high/low sweep-and-reclaim** — NY is scratch-to-negative OOS (−0.003R); London is clearly negative (−0.27R). Conditioning on D+4H does not rescue it. This is consistent with Phase 1’s weak B-setup.

## What this does not claim

- Twelve pre-registered variants is a small, honest search, not an exhaustive one. We did not hunt extra MA lengths, Donchian windows, or entry hours after seeing P&L.
- HistData ends 6 Nov 2026; 7–13 Nov is still futures-only. No official CPI/PPI calendar (NFP is first-Friday plus the calendar file; FOMC is from the Fed list).
- These are rule-based approximations on cash-spot 1h with a simple cost model. Live broker fills, Sunday gaps, and contract rolls can differ.
- FOMC continuation has only 62 OOS trades. A handful of event days move the average.
- Meeting the bar is not a promise of next year’s P&L. 2026 year-to-date for the NY London-range book is slightly negative.

## Process recommendation (EA / decision file)

Hard risk caps do not change (0.5%, one trade, 2% day stop, 1.5R / 3R). Do not encode these entries into the EA this weekend; the EA remains an execution bridge. The assistant should start *looking for* the adopted setups on the chart, with this priority, because of the occupancy problem:

1. News blackout, daily loss stop, or kill switch → NONE. Exception: on an FOMC day, `B_fomc_cont` may enter at the **15:00 ET** open only, after the 14:00 bar has closed. All other new entries stay blocked until 15:30 ET.
2. If that FOMC continuation is valid, it goes first (rare, high expectancy, ~2-day hold).
3. Else the **NY London-range break with daily+4H trend**, 08:00–12:00 ET, if no trade is on. This is the workhorse (~19 times a year, ~2-day hold, stable across 2012–2023 and 2024–2026).
4. The original **Asia-range A-setup** stays as in playbook v2: take it only when it is clean and preferably with the 4H/daily trend; it is still not a 15-year edge.
5. **Donchian long-only** at the 18:00 ET open, only when the book is otherwise empty and a *fresh* 20-day high break has just closed. Do not park a 25-day Donchian long if it would routinely block (3) and (2). Treat the Donchian break as regime confirmation for the NY London-range trade when a shorter setup is also available.
6. B-setup NY sweep and discretionary supply sells remain optional and weak.
7. Else NONE.

A second simultaneous “core trend” slot would let Donchian run alongside the tactical book. That would break the current one-trade hard rule and is **not** adopted here; it would need an explicit owner decision and a fresh risk budget.

Tables: `results/phase2/wf_summary.csv`, `results/phase2/wf_oos_years.csv`, `results/phase2/trades_*.csv`, `results/phase2/adoption.json`. Figure: `figures/phase2_yearly_avg_r.png`.

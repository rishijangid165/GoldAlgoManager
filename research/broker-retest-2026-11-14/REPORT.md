# Broker-data retest of playbook v3 (2026-11-14)

**Question.** Do the playbook v3 setups that passed on HistData spot (`research/deep-study-2026-11-14/PHASE2.md`) still pass on the broker's own XAUUSD history, with the broker's spread?

**Short answer.**

| Setup | Verdict on broker data |
|---|---|
| FOMC continuation | Holds |
| Donchian-20 long | Holds, but the 2012–2023 part is thinner |
| NY London-range break (D+4H) | Misses the bar by a hair: OOS PF 1.19 vs the required 1.20. It is still positive, but the pre-2024 edge is about half as large. |
| Asia breakout | Still not a long-run edge. The D+4H-filtered version scrapes the bar only with the broker spread (PF 1.208), and fails it with the old fixed cost. Almost all of its P&L is 2024–2026. |

Spread was not what changed the results. The broker spread model and the old fixed $0.25 give nearly identical numbers. The differences come from the bars themselves: small price differences flip the "first close beyond the range" and MA-trend thresholds on roughly 10–15% of trade days.

## 1. Broker history pulled

Source: MetaQuotes-Demo MT5 (the running demo terminal, account `<demo-login>`). Data came from the official `MetaTrader5` Python package under Wine, using read-only `copy_rates_range` / `copy_rates_from_pos` only. No order, position or terminal-setting calls were made, and the terminal was not restarted. The scripts are in `scripts/mt5_wine/`. CSVs are in `data/broker/` (git-ignored); `data/broker/manifest.json` is committed.

| TF | Rows | First bar (UTC) | Last bar (UTC) | Limit |
|---|--:|---|---|---|
| M1 | 100,000 | 2026-07-31 06:40 | 2026-11-13 20:59 | 100k cap (~3.5 months) |
| M15 | 100,000 | 2022-08-11 19:45 | 2026-11-13 20:45 | 100k cap (~4.3 years) |
| H1 | 100,000 | 2009-10-13 09:00 | 2026-11-13 20:00 | 100k cap (~17 years) |
| H4 | 33,546 | 2005-01-02 22:00 | 2026-11-13 18:00 | full server history |
| D1 | 5,763 | 2004-06-10 21:00 | 2026-11-12 22:00 | full server history |

- **The 100,000-bar ceiling is the terminal's "Max bars in chart" setting** (`terminal_info().maxbars = 100000`), not the server. Every M1/M15/H1 request beyond it came back empty or with 1 row. Raising it needs a settings change and a terminal restart, which was out of scope with the live EA attached. With it raised, the server may well hold older M1/M15 data.
- **Time zone.** Bar times are server wall-clock, **ET+7 all year** (EET/EEST on US DST dates). This was verified by matching H1 closes to HistData (ET). A 7h offset gives a median |diff| of $0.03 (2019) to $0.22 (2026) in every month tested; 6h and 8h give $0.7–7. Note: `scripts/build_dashboard_data.py` hard-coded UTC+2, which is right only in US winter. It now has an ET+7 helper for MT5 deal times.
- **Price agreement with HistData** on 99,010 common H1 bars: median |close diff| $0.03–0.14 in 2012–2024 and $0.22 in 2025–26, with a 95th percentile under $0.8 after 2011. 2009–2010 are noisier ($1–1.4), but that is warmup only.

## 2. Method (unchanged rules, new data)

- The signal functions, the engine, the adoption bar and the walk-forward split are **imported** from the Phase 2 code, not rewritten (`retest_broker.py`):
  - 0.5% risk on $100k
  - TP1 at 1.5R, half off, then the stop goes to breakeven; TP2 at 3R
  - one trade per book, conservative same-bar stop-first, 2% day stop
  - OOS 2012–2026, at least 8 of 15 green years, and the 2012–2023 regime check
- Features (session daily, D/4H MAs, ATR, Asia/London ranges, FOMC/NFP flags) are built from broker H1 exactly as they were from HistData H1. Both series start on a US-daylight-time day, so the 4H bins line up the same way. (This matters: an EST start shifts every 4H bin by one hour. I found this while building the paper tracker.)
- **Spread.** An MT5 bar's `spread` field is the *minimum* spread during the bar, so on H1 it understates cost. Per bar I used max(bar spread, the 2026 M1 median spread for that ET hour), plus the same $0.10 slippage per fill. The 2026 M1 median by ET hour runs from $0.13 (NY morning) to $0.30 (18:00–19:00 ET reopen). Median used: $0.20 (2012–15 ~$0.30–0.39, 2018–26 ~$0.16). A second run with the old flat $0.25 isolates the data effect.
- No new variants were added. Asia breakout is reported for the same three pre-registered Phase 1 parameter sets (`A_base`, `A_4h_ma`, `A_trend_ma`).

## 3. Results: OOS 2012–2026

Old = HistData spot 1h (to 6 Nov 2026). Broker = MT5 H1 with the broker spread model (to 13 Nov 2026). Full tables are in `results/comparison.csv`, `results/broker_spread/`, `results/fixed_025/`.

| Setup | Book | n | Win % | Avg R | PF | Max DD | 2012–23 Avg R / PF | 2024–26 Avg R | Green yrs | Bar |
|---|---|--:|--:|--:|--:|--:|---|--:|--:|---|
| NY London-range break D+4H | Old | 286 | 44.4 | +0.134 | 1.23 | −5.9% | +0.122 / 1.21 | +0.161 | 10/15 | Pass |
| | **Broker** | 286 | 44.1 | **+0.115** | **1.19** | −7.6% | +0.054 / 1.08 | +0.254 | 8/15 | **Fail (PF)** |
| | Broker, $0.25 | 286 | 44.1 | +0.116 | 1.20 (1.198) | −8.0% | +0.048 / 1.07 | +0.270 | 8/15 | Fail (PF) |
| FOMC continuation | Old | 62 | 58.1 | +0.380 | 1.86 | −2.6% | +0.369 / 1.82 | +0.419 | 11/15 | Pass |
| | **Broker** | 68 | 55.9 | **+0.308** | **1.66** | −2.4% | +0.304 / 1.66 | +0.325 | 10/15 | **Pass** |
| Donchian-20 long | Old | 79 | 51.9 | +0.342 | 1.74 | −3.5% | +0.168 / 1.30 | +0.822 | 11/15 | Pass |
| | **Broker** | 82 | 48.8 | **+0.282** | **1.59** | −4.4% | +0.082 / 1.14 | +0.828 | 11/15 | **Pass** |
| Asia breakout (mechanical) | Old | 905 | 40.3 | −0.034 | 0.93 | −28.8% | — | — | 6/15 | Fail |
| | Broker | 945 | 39.2 | −0.054 | 0.90 | −28.5% | −0.080 / 0.86 | +0.057 | 4/15 | Fail |
| Asia breakout + 4H MA | Old | 575 | 41.7 | +0.022 | 1.03 | −17.0% | — | — | 9/15 | Fail |
| | Broker | 594 | 42.6 | +0.046 | 1.08 | −10.9% | +0.018 / 1.03 | +0.154 | 11/15 | Fail |
| Asia breakout + D+4H MA | Old | 319 | 44.5 | +0.096 | 1.17 | −8.1% | (−0.01) | — | 8/15 | Fail |
| | Broker | 328 | 44.2 | +0.115 | 1.21 (1.208) | −5.6% | +0.027 / 1.04 | +0.422 | 8/15 | Pass by 0.008 |
| | Broker, $0.25 | 327 | 44.3 | +0.110 | 1.20 (1.199) | −5.7% | +0.021 / 1.03 | +0.421 | 8/15 | Fail |

**Trade-level agreement** (same entry hour and side, 2012 to 6 Nov 2026): NY 259/286 old trades reproduced (91%), FOMC 59/62 (95%), Donchian 68/79 (86%), Asia variants 83–87%.

### Yearly avg R, old vs broker (adopted three)

| Year | NY old | NY broker | FOMC old | FOMC broker | Donch old | Donch broker |
|---|--:|--:|--:|--:|--:|--:|
| 2012 | −0.08 | −0.25 | +0.65 | +0.65 | +0.24 | +0.24 |
| 2013 | +0.24 | +0.24 | +1.47 | +1.22 | −1.00 | −1.00 |
| 2014 | +0.07 | +0.23 | −0.44 | +0.31 | −0.01 | +0.03 |
| 2015 | +0.24 | −0.04 | +2.23 | −1.05 | −1.01 | −1.01 |
| 2016 | +0.48 | +0.40 | +0.22 | −0.22 | +0.08 | −0.29 |
| 2017 | −1.03 | −0.16 | +1.47 | +1.73 | +0.09 | +0.09 |
| 2018 | +2.22 | +2.23 | +0.59 | +0.60 | +1.47 | +0.66 |
| 2019 | +0.02 | −0.06 | +0.64 | +0.64 | +0.66 | +0.66 |
| 2020 | +0.11 | +0.13 | +0.06 | +0.07 | +0.20 | +0.35 |
| 2021 | −0.11 | −0.19 | −0.03 | −0.02 | −0.18 | −0.17 |
| 2022 | −0.09 | −0.02 | −0.67 | −0.32 | +0.09 | +0.10 |
| 2023 | +0.22 | −0.15 | +2.22 (n=1) | +0.23 (n=4) | +1.00 | +0.43 |
| 2024 | +0.20 | +0.26 | +0.67 | +0.39 | +1.19 | +1.21 |
| 2025 | +0.28 | +0.36 | −0.18 | −0.18 | +0.65 | +0.66 |
| 2026 | −0.11 | +0.07 | +1.20 | +1.20 | +0.75 | +0.75 |

## 4. Per-setup conclusions

**FOMC continuation: holds.** It is still the strongest expectancy: +0.31R, PF 1.66, max DD −2.4%, and 2012–2023 and 2024–2026 agree. Broker data finds 6 more events than HistData (68 vs 62; HistData has gaps, e.g. 2023 has 4 vs 1). Avg R is lower but still well over the bar. *No change: keep it as priority 1.*

**Donchian-20 long: holds, but less evenly than it looked.** OOS +0.28R, PF 1.59, 11/15 green. The 2012–2023 part drops from +0.17R / PF 1.30 to +0.08R / PF 1.14. This is still a pass on the regime check (≥ 0, PF ≥ 1.0), but most of the edge is the 2024–2026 bull (+0.83R). *No change in rank. Treat it as a regime trade, not an all-weather one. The occupancy warning from Phase 2 still applies.*

**NY London-range break D+4H: borderline, now a fail by the letter of the bar.** OOS PF 1.194 (1.198 with the old cost) vs the 1.20 bar. Average R is still positive (+0.115R), and it reproduces 91% of the old trades. But the pre-2024 edge halves (+0.05R, PF 1.08) and only 8/15 years are green (10/15 before). The 2024–2026 part looks better (+0.25R), and 2026 YTD turns slightly positive (+0.07R vs −0.11R on HistData). Honest reading: this is a thin edge whose sign survives a data change but whose size does not. Under the pre-registered rule it drops to watchlist.

- *Recommended change (owner's call, playbook v3.2):* keep looking for it as the workhorse, but tag it "probation". Its live/paper record over the next 4–8 weeks decides. Do not loosen anything to rescue the PF. If the forward paper book is flat or negative after ~15 trades, demote it.

**Asia breakout: still not a long-run edge.** The mechanical rule loses on broker data too (−0.05R, 4/15 years). The D+4H-filtered version technically passes with the broker spread (PF 1.208), fails with the flat $0.25 (1.199), and its 2012–2023 part is scratch (+0.03R, PF 1.04). A pass by 0.008 PF on one cost assumption, with all the P&L in 2024–2026, is not an adoption. *No change: "only when clean, with the D/4H trend" stays the rule. The paper tracker follows the D+4H version so we see whether the 2024–26 behaviour persists.*

## 5. Caveats

- **History depth.** H1 covers the same 2012–2026 OOS window as HistData, so the comparison is like-for-like. M15 only goes back to Aug 2022 and M1 only to 31 Jul 2026, because of the terminal's 100k-bar cap. So intrabar checks (for example, resolving same-bar stop-vs-target order with M1) are only possible for the last ~3.5 months and were **not** done here. The engine still uses conservative stop-first.
- **This is a demo server.** MetaQuotes-Demo quotes are an aggregated demo feed. A live retail broker's prices, spreads (especially around news and the 18:00 ET reopen) and fills will differ. The ~$0.20 average spread is a demo figure.
- **Bar spread is a floor.** MT5 bars store the minimum spread. The hour-of-day M1 profile is from 2026 only and was applied to all years (older years used their own higher bar spreads where those were bigger).
- **News calendar** is still FOMC (Fed pages) plus a first-Friday NFP proxy. CPI/PPI are not in the blackout. The live playbook's manual 30/90-minute rule covers them; the backtest does not.
- **Fragility.** About 10–15% of trades differ between two price sources that agree to ~$0.1 a bar. Edges of +0.1R live inside that noise. Only FOMC (and, more weakly, Donchian) are clearly bigger than it.
- Twelve pre-registered Phase 2 variants plus three Phase 1 Asia variants were tested. Nothing was added after seeing results.

## 6. Files

- `broker_data.py`: imports the raw MT5 pulls, fixes the time zone, models the spread
- `retest_broker.py`: runs the retest (`python research/broker-retest-2026-11-14/retest_broker.py`)
- `results/comparison.csv`, `results/frame_meta.json`, `results/{broker_spread,fixed_025}/wf_summary.csv`, `wf_oos_years.csv`, `trades_*.csv`
- `scripts/mt5_wine/broker_history_ro.py`, `broker_history_chunks_ro.py`, `live_snapshot_ro.py`: read-only Wine pulls

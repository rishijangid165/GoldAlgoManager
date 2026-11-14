# Weekend study 2026-11-15: pre-registration

Written **before** any P&L in this study was computed (2026-11-14, ~12:45 IST). It is committed to the repo before the test code runs, so the commit time is the proof. Nothing below may be changed after results are seen. Any later idea goes into a separate "post-hoc / exploratory" section of the report and cannot be adopted this weekend.

## Data

- **Source.** Broker MetaQuotes-Demo XAUUSD M1, 2004-06-11 to 2026-11-13. It is decoded read-only from the terminal's own `.hcc` base files: `copy_rates_range` is still capped at 100k bars on the running terminal, and the decoded H1 matches the API H1 exactly on all 100,000 overlapping bars. M5, M15 and H1 are resampled from M1. Server clock is ET+7.
- **Features.** The existing no-look-ahead builder (`dataset.build_exec_from_series`) is used unchanged on broker H1, or on M15 with H1 features, plus `phase2_setups.add_london_range / add_donchian / add_news_flags`. History starts on an EDT day, so the 4H bins match the earlier studies.
- **Calendar.**
  - FOMC: Fed list, as before.
  - NFP: first-Friday proxy, as before.
  - CPI: release dates are the ALFRED vintage dates of `CPIAUCSL`, one per month at 08:30 ET. Where a month has two weekday vintages, the later one is the CPI release; the earlier one is the February seasonal-factor revision or a FRED correction. Nov 2025 has no release (shutdown).
- **Samples.** Warmup/backcast is 2005–2011. Price data before 2009 is sparse in places and spread is not recorded before 2010. The backcast is reported but is not part of the adoption bar. **OOS is 2012-01-01 to 2026-11-13**, with sub-periods 2012–2023 and 2024–2026.

## Execution model (all tests)

- **Signals.** Signals form at bar close (H1 or M15). Entry is at the next bar's open. Donchian enters at the 18:00 ET bar open.
- **Management on the M1 path.**
  - A gap at an M1 open fills at that open.
  - If one M1 bar touches both the stop and a target, the stop is assumed to come first. This is the only remaining ambiguity.
  - Baseline exit: 0.5% risk, TP1 at 1.5R (half off, stop to breakeven), TP2 at 3R, or the setup's `next_level` when it lies between 1.5R and 3R, as in the engine.
  - One trade at a time per setup book. No entries in the 17:00–18:00 ET break.
- **Costs.** Spread at the fill minute = max(M1 recorded spread, 2026 M1 median spread for that ET hour), plus $0.10 slippage per fill.

## Adoption bar

It is the PHASE2 bar, plus two extras.

1. OOS 2012–2026: n ≥ 40, avg R > 0, PF ≥ 1.20.
2. At least 8 of 15 OOS years with avg R > 0.
3. 2012–2023: n ≥ 20, avg R ≥ 0, PF ≥ 1.0. **For new ideas, 2012–2023 avg R must be strictly > 0.** Anything whose edge is only in 2024–26 is rejected.
4. **Multiple testing.** Within each family below, a Holm–Bonferroni correction at family-wise α = 0.05 is applied to a one-sided test that OOS mean R > 0. The p-value comes from a 20,000-draw bootstrap of per-trade R, seed 7. A new idea must pass items 1–3 **and** survive Holm.

## Part A: re-checks of the v3 setups (not a discovery family; reported against the old numbers)

| ID | What |
|---|---|
| A1 | `ny_lon_brk_d4h`, H1 signals, M1-managed (resolves same-bar order) |
| A2 | `fomc_cont`, H1 signals, M1-managed |
| A3 | `donch20_long`, 18:00 ET open, M1-managed |
| A4 | `asia_brk_trend` (`A_trend_ma`), H1 signals, M1-managed |
| A0 | For each of A1–A4, the same trades with the old conservative H1-bar management, to measure the same-bar effect |

## Family F: discovery, Holm over 14 tests

| ID | Hypothesis | Rule |
|---|---|---|
| F1 `cpi_cont_60` | Like FOMC, the first hour after CPI shows the move's direction | CPI day, M15. Signal at the 09:15–09:30 bar close. Direction = sign(close − close of the 08:15–08:30 bar). SL beyond the 08:30–09:30 high/low + 0.15×H1 ATR. $5 ≤ SL ≤ 3×H1 ATR. Entry at the 09:30 open. |
| F2 `cpi_cont_30` | Same, 30 minutes | Signal at the 08:45–09:00 bar close; window 08:30–09:00. Entry at the 09:00 open. |
| F3 `nfp_cont_30` | Same for NFP, 30 minutes | As F2 on NFP days |
| F4 `nfp_cont_60` | NFP after 60 minutes (the watchlist idea, now on M15/M1) | As F1 on NFP days |
| F5 `pdhl_brk_ny` | A break of the prior-session high/low at the NY open, with trend, continues | M15, 08:00–11:00 ET. First M15 close above the prior-session high (long, needs D+4H up) or below the prior-session low (short, needs D+4H down). Skip if the close is more than 0.5×H1 ATR past the level. SL beyond the extreme of the last 4 M15 bars + 0.15×H1 ATR. $5–3×H1 ATR. NFP/FOMC blackout on. |
| F6 `ny_brk_vol_le80` | Extreme volatility hurts the NY break | A1, but only if daily ATR(14) is ≤ its 80th percentile over the trailing 252 sessions (known at the prior close) |
| F7 `ny_brk_vol_ge20` | Dead markets hurt the NY break | A1, but only if ATR percentile ≥ 20 |
| F8 `asia_trend_vol_le80` | As F6 | On A4 |
| F9 `asia_trend_vol_ge20` | As F7 | On A4 |
| F10 `donch_vol_le80` | Donchian longs fail in volatility spikes | A3, but only if ATR percentile ≤ 80 |
| F11 `gap_fade` | Weekly-open gaps fill | Sunday reopen. Gap = 18:00 ET open − Friday close. If \|gap\| ≥ max($3, 0.25×daily ATR) and the 18:00 bar has not already filled it, trade toward the Friday close at the 19:00 ET open. SL = max(gap, $5) beyond entry, capped at 3×H1 ATR. Standard exits. |
| F12 `gap_go` | Weekly-open gaps continue | Same trigger, trade in the gap direction |
| F13 `ny_lon_brk_15m` | 15m signals improve the NY London break | A1 rules on M15 bars (first M15 close beyond the London range in 08:00–12:00 ET), H1 ATR for the buffer and cap |
| F14 `asia_trend_15m` | 15m signals improve the Asia break | A4 rules on M15 bars |

FOMC and Donchian entries are fixed in time (15:00 ET open, 18:00 ET open), so a "15m entry" is identical to A2/A3. Their M1 management covers the 15m question.

## Family X: exits, Holm over 12 tests

Entries are fixed to each setup's baseline entry list, so exits are compared on the same trades. Test: paired mean ΔR = R(alt) − R(baseline) > 0, bootstrap, Holm over the family. An exit is adopted only if ΔR survives Holm **and** the alternative book still passes items 1–3.

| ID | Exit |
|---|---|
| X1 | Live EA trail: after TP1 + breakeven, trail the runner to the tighter of the last confirmed M15 swing (2 bars each side) and price ∓ 1×M15 ATR(14), updated at each M15 close. Only tightens. TP2 kept. |
| X2 | No partial. Full position with a fixed 2R target, stop unchanged. |
| X3 | Chandelier. No partial, no TP. Once +1R is reached, trail at 3×H1 ATR(14) from the best close. Only tightens. |

Applied to A1, A2, A3 and A4 (4 × 3 = 12).

## Realism check R (not a discovery test)

- **R1: the EA's Friday auto-close.** Flatten at 16:15 ET Friday, and block new entries from 14:15 ET Friday. The live EA does this (v1.02 inputs). Reported for A1–A4 to show how far the live behaviour is from the backtest. It is not "adopted"; it is what the EA actually does.

## Descriptive D (no rule can be adopted from it)

- **D1.** OOS mean session return (Asia / London / NY) and mean daily return by weekday, with t-tests and Holm within the table.
- **D2.** v3 setup performance by weekday.
- **D3.** Weekly-gap fill rate: share of gaps that fill by the end of the Sunday session and by the Monday NY open.

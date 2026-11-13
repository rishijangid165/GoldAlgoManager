# Gold deep study — 14 November 2026

Overnight research mandate (owner, 13 Nov 23:59 IST): study gold from the start of available history, learn its behaviour, re-test the playbook setups with a proper out-of-sample / walk-forward design, and write a post-mortem of 13 November so the same mistakes are not repeated. Profit was not the goal. Getting the system more accurate was.

This report is the evidence book. The live playbook changes that follow from it are in `research/playbook.md` (version dated 2026-11-14). Anything not backed by out-of-sample numbers is marked **watchlist**, not a new rule.

## 1. Data

| Series | Source | Range used | Role |
|--------|--------|------------|------|
| XAUUSD 1h / 15m / 5m / session-daily | HistData.com M1, resampled, America/New_York | 2009-03-15 to 2026-11-06 | **Primary** long-history spot series |
| GC=F daily | Yahoo Finance | 2000-08-30 to 2026-11-13 | 25-year daily behaviour, 50/200 regime |
| GC=F 1h | Yahoo (~730d cap) | 2024-06-24 to 2026-11-13 | Reproduce the original backtest; futures–spot basis; 13 Nov post-mortem |
| GC=F 15m / 5m | Yahoo (~60d cap) | 2026-09-04 to 2026-11-13 | Post-mortem path, short robustness only |
| DXY daily | Yahoo `DX-Y.NYB` | 1971–2026 | Context, not traded |
| FOMC dates | Federal Reserve calendar / historical pages | 2006–2027 | News study, 14:00 ET convention |
| NFP dates | First Friday of each month (proxy) | 2006–2026 | News study, 08:30 ET convention |

**Not obtained this run (documented, not invented):** Yahoo spot `XAUUSD=X` (delisted); HistData 2003–2008 (empty download); Stooq (JS challenge); a clean Dukascopy XAUUSD history from 2003 (feed was up in spots, then 503 / TLS errors); official BLS CPI/PPI calendars (HTTP 403). HistData’s November 2026 zip stopped at **6 Nov**, so 7–13 Nov, including today, is GC=F only.

Costs in every book: **$0.25 spread + $0.10 slippage per fill**, 0.5% risk, 1.5R half-off / 3R runner, one trade at a time, 2% daily loss stop — same engine as `research/backtest/`. Signals fire at bar close; entry is the next open (or a limit fill for retrace tests). Same-bar stop-and-target is assumed to hit the stop first.

Walk-forward: 2009–2011 is warmup / embargo only (200-day SMA). **Out-of-sample years are 2012–2026.** Every pre-registered variant is reported, including losers.

The original 1h GC=F book (2024-07-07 to 2026-11-13) was re-run as a sanity check: **132 trades, +0.37R, PF 1.79, max DD −3.4%** — identical to `research/backtest/README.md`. The engine is not the issue.

## 2. Behaviour (spot 2009–2026, figures in `figures/`)

### 2.1 Sessions (ET: Asia 18:00–03:00, London 03:00–08:00, New York 08:00–17:00)

On 4,500+ sessions (`session_stats.csv`):

| Session | Mean range | Median | P90 | Share of the day’s range | Up-close share |
|---------|-----------:|-------:|----:|-------------------------:|---------------:|
| Asia    | $14.06 | $8.39 | $27.00 | 50% | 55% |
| London  | $11.34 | $8.03 | $20.88 | 45% | 50% |
| New York| $20.68 | $14.84 | $38.46 | 77% | 49% |

NY is where most of the day’s range is made. London is the *smallest* of the three sessions on average. That already warns against treating “London is the best breakout session” (true in the 28-month futures sample) as a law of gold.

### 2.2 Time of the session high / low (IST)

Both the daily high and the daily low print most often in **IST 18:00–21:00** (the New York morning / 08:30 ET news window in US winter, 08:30–12:00 IST-shifted in summer). There is a secondary cluster in IST 03:00–06:00 (London). See `figures/tod_high_low.png`. This is why a news blackout around 08:30 ET is not optional: that is frequently the extreme of the day.

### 2.3 Day of week

On XAUUSD session daily, 2012–2026 (`dow_effects.csv`, `figures/dow_effects.png`):

- Friday is the strongest close–open day: mean **+$1.03**, 55.1% up.
- Wednesday **+$0.98**, Thursday **+$0.64**.
- Monday is close to flat. Sunday (small sample) is slightly down.

GC=F daily since 2000 also has Friday as the strongest weekday log-return. This is **watchlist**, not a new trading rule: it is a drift study, not a setup, and a Friday long bias would fight the 13 Nov short plan.

### 2.4 Trend regime (daily 50/200)

On both HistData session-daily (2012–2026) and GC=F daily (2000–2026), gold has a real trend drift:

- Close above both 50- and 200-day SMAs: positive mean log-return, ~59% up days.
- Close below both: negative mean log-return, ~42–44% up days.
- High-vol quartile (ATR/price) has a slightly negative mean day, and a much wider range (~$59 vs ~$14 in the quiet quartile).

This supports a *soft* with-trend bias. It does not, by itself, make a breakout book.

### 2.5 Asia-range width vs breakout

Among 2012–2026 sessions (`asia_width_vs_break.csv`, `figures/asia_width_vs_break.png`), a London or early-NY close outside the Asia range is actually common (~70–97%, falling as the range gets wider). Follow-through after that close is **not** clearly better than a fade: `follow > fade` is only ~43–50% in every width bin. On ranges **wider than 3× 1h ATR**, a later 1.5R continuation after a retrace entry is especially rare (see §3.3: ~4% vs ~10% on all days). Wide Asia days are noisy, not a hidden goldmine.

### 2.6 News (NFP and FOMC only)

171 NFP and 124 FOMC events in 2012–2026 with 15-minute data (`news_summary.csv`):

- Realised range in the first 30 minutes after the print is about **2.1–2.2×** the prior two-hour range.
- Median first 60-minute range: about **$13.7 (NFP)** and **$12.9 (FOMC)**.
- A strict “the next 4 hours extend the first-hour close more than they retrace it” happens only ~24–27% of the time. First-hour news moves often give a lot back. The 30-to-90-minute window is still active; this supports the existing **30 minutes before to 90 minutes after** blackout, rather than a 15-minute pause.

CPI/PPI dates were not available from BLS this run, so 13 Nov PPI is discussed only in the post-mortem, not in the long-sample news table.

### 2.7 Liquidity sweeps

Unfiltered fade-every-sweep paths on 2012–2026 1h data still look poor as a book: London sweeps show high 1.5R *and* high 1R-stop rates (two-sided, wide paths); NY with-trend was the only slice the original playbook kept, and even that loses as a mechanical book in the long walk-forward (§3).

### 2.8 Futures vs spot basis

On 13,553 overlapping 1h bars (2024-06-24 to 2026-11-06): GC=F close minus XAUUSD close has **median +$17.75**, mean +$20.84, 10th–90th percentile **+$3.48 to +$44**, and close-to-close return correlation **0.88**. Month-by-month the gap is usually mid-single-digits to ~$20, but it **jumps around rolls** (e.g. 2026-08 median ~$57). November 2026 so far is calmer (mean ~$9.8). The $3–7 basis used in the 13 Nov notes is a reasonable *quiet-month* figure, not the overlap average. Zones must stay in **broker spot**.

Same 2024-07-07 to 2026-11-06 window, same breakout rules: GC=F **+0.37R / PF 1.79**, XAUUSD **+0.27R / PF 1.52 / DD −6.8%**. The recent edge is real on spot, just weaker and with more drawdown than futures suggested.

## 3. Setup re-test (walk-forward, spot XAUUSD 1h)

Pre-registered variants only. OOS = entry years 2012–2026. Full tables: `wf_summary.csv`, `wf_oos_years.csv`, `wf_regime_split.csv`.

### 3.1 The headline result

The playbook’s mechanical A-setup (Asia close-break, far-side stop, 3× ATR cap, no hard MA gate) **does not have a stable 15-year edge** after costs.

| Variant | OOS trades | Win rate | Avg R | PF | Max DD | Green years |
|---------|-----------:|---------:|------:|---:|-------:|------------:|
| A_base (current A-setup) | 905 | 40.3% | **−0.034** | 0.93 | −28.8% | **6 / 15** |
| A_trend_ma (D+4H MA gate) | 319 | 44.5% | **+0.096** | 1.17 | −8.1% | 8 / 15 |
| A_4h_ma | 575 | 41.7% | +0.022 | 1.03 | −17.0% | 9 / 15 |
| A_half_stop | 1,400 | 40.6% | −0.050 | 0.91 | −31.0% | 6 / 15 |
| A_cap_none | 898 | 41.2% | +0.002 | 1.00 | −23.0% | 8 / 15 |
| A_retest_382 | 879 | 39.6% | −0.056 | 0.89 | −31.3% | 4 / 15 |
| A_retest_50 | 878 | 39.6% | −0.054 | 0.90 | −29.8% | 6 / 15 |
| B_ny_trend | 399 | 41.9% | −0.022 | 0.95 | −18.3% | 6 / 15 |
| B_unfiltered | 1,639 | 40.3% | −0.058 | 0.91 | −41.6% | 5 / 15 |

Yearly expectancy: `figures/wf_yearly_avg_r.png`. Almost all of the “good” years sit in **2024–2026**.

Regime split (same trades, not a new search):

| Variant | 2012–2023 | 2024–2026 |
|---------|-----------|-----------|
| A_base | 730 tr, **−0.09R**, PF 0.85, −$25.4k | 175 tr, **+0.20R**, PF 1.37, +$11.2k |
| A_trend_ma | 246 tr, **−0.01R**, PF 0.97, −$1.9k | 73 tr, **+0.46R**, PF 2.00, +$17.1k |
| A_4h_ma | 457 tr, −0.04R, PF 0.93 | 118 tr, +0.27R, PF 1.50 |
| A_half_stop | 1,018 tr, −0.07R | 382 tr, −0.01R |
| B_ny_trend | 283 tr, −0.10R | 116 tr, +0.18R |

So: the 28-month futures backtest was not a bug, and it was not only a GC=F artefact. It was a **strong regime**. The same rules lost money for most of 2012–2023. A_trend_ma is the least-bad pre-registered filter on the long sample, but even that is scratch before 2024 and is **not** a 15-year proven edge. London-only, which looked excellent on GC=F 2024–2026 (+0.53R), is **negative** on 2012–2026 OOS (−0.04R).

### 3.2 Alternatives to the 3× ATR width filter

These were the questions raised by 13 November’s wide Asia range.

- **Tighter cap (2× / 2.5×):** worse or similar (2× is clearly worse: OOS −0.13R, small and unstable).
- **Looser cap (4×) or no cap:** no meaningful edge (no-cap OOS +0.002R, PF 1.00).
- **Half-range stop** (stop at the Asia midpoint so a $48 range can still trade): **more trades, worse book** (OOS −0.05R, DD −31%). Do not adopt.
- Trade counts are not monotonic in the cap because one open trade blocks later signals.

The 3× cap is not a hidden goldmine-skipper, and loosening it does not create an edge. Keep it as a risk/sanity filter, not because we measured a large filter edge.

### 3.3 Retest entry after a close-break (38.2% vs 50% vs the broken level)

Path study, first close-break of the Asia range, same session through 13:00 ET (`retrace_fill_summary.csv`):

| Slice | Retrace | Fill rate | Then reached 1.5R | Then hit far-side stop | Mean MFE if filled |
|-------|--------:|----------:|------------------:|-----------------------:|-------------------:|
| OOS | 0% (level) | 93.4% | 9.0% | 17.1% | 0.63R |
| OOS | 38.2% | 87.6% | 9.6% | 18.2% | 0.67R |
| OOS | 50% | 85.9% | 10.1% | 18.3% | 0.68R |
| Wide >3× ATR, OOS | 38.2% | 88.9% | **3.9%** | 8.9% | 0.49R |
| Wide >3× ATR, OOS | 50% | 87.7% | **4.0%** | 8.8% | 0.51R |

A 38.2% limit fills only a little more often than a 50% limit. After the fill, the move rarely reaches 1.5R (and almost never on wide-range days). The mechanical retrace books are all OOS-negative. **Do not replace next-open entry with a 38.2% or 50% limit as a rule.**

### 3.4 “Retest of a broken / rejection level” (today’s discretionary type)

After a 1h rejection at a 4H/daily swing zone, once price has left the zone, how often does a Fibonacci retrace of the subsequent push fill within ~8 hours (`rejection_retrace_summary.csv`)?

| Slice (OOS) | 38.2% fill | Then 1.5R | Then SL | 50% fill | Then 1.5R | Then SL |
|-------------|-----------:|----------:|--------:|---------:|----------:|--------:|
| All | 68.6% | 3.9% | 30.6% | 60.0% | 7.1% | 35.9% |
| Sells in a downtrend (today’s shape) | 66.7% | **2.4%** | 39.2% | 59.4% | **6.3%** | 45.5% |

A 38.2% limit fills more often than 50%, which is the honest answer to “would 38.2% have been better for a fill?” On 13 Nov, the published 3909–3913 zone sat closer to a 38.2% retrace and **did not fill**; a deeper 50% limit would have been more likely to fill. Historically, those fills do not pay: 1.5R after a downtrend sell retrace is 2–6%, and the stop is hit 39–46% of the time. This pattern stays **discretionary at best, and is not a mechanical setup**.

### 3.5 B-setup

Unfiltered sweeps lose. D+4H trend filter still loses on the long sample. NY-with-trend, the only slice kept in the playbook, is OOS **−0.02R (PF 0.95, 6/15 years)** and was itself negative in 2012–2023 (−0.10R). It looked fine in 2024–2026 (+0.18R), same regime story. It does not earn a mechanical slot.

## 4. Post-mortem — 13 November 2026

Prices below are **GC=F** (HistData spot ends 6 Nov). That day’s quiet-month basis was about +$4 (notes). Session 12 Nov 18:00 ET to 13 Nov 17:00 ET. Facts in `results/postmortem_2026-11-13.json`.

- **Asia range locked at 03:00 ET:** 3927.2 / 3879.1, width **$48.10**. London stayed inside it the whole session (high 3909.4, low 3889.1, hourly closes 3900.5–3905.6–3895.7–3897.2–3892.9). **No London close-break, so there was no A-setup to take**, width filter or not.
- **Width filter was not the binding constraint.** The 14:50 IST note used 1h ATR ~$14.1, so 3× = $42 and $48 failed the rule. Our Wilder-14 1h ATR at the last Asia bar was **$17.31** (3× = $52); a far-side stop of about $48 + 0.15×ATR ≈ $51 is then *borderline*, not a clear fail. Either way, skipping a non-existent breakout was not a missed A-trade.
- **SELL retest 3909–3913 spot never filled.** After 01:00 ET and before PPI, the futures high was **3910.2** (about 3906 spot at a +$4 basis), $3–7 short of the zone. A 50% retrace of the 3927→3883 drop sits near **3905** and *would* have been traded; a 38.2% retrace sits near **3910** and was almost tagged. That matches §3.4: 38.2% fills more often in general, but *this* zone was already a shallow retrace and still missed — and the pattern has no long-sample edge after a fill.
- **PPI (08:30 ET / 19:00 IST):** 08:00–10:00 ET range 3909.9–3876.1, later session low 3871.1. Two-sided, slightly through the Asia low, not a clean close-break, and inside the blackout. The owner-requested mid-range sells into that window were outside the playbook. They happened to book small profits with active management; that is not evidence the system should have been in the market.

What would have *helped*, measured on history rather than hindsight? Not a half-range stop, not a 38.2% standing limit, and not dropping the 3× cap. What would have helped is sticking to “no close-break, no A-trade; no fill, no chase; no entry inside the PPI window,” which is what the published plan already did until the owner asked for manual tickets.

## 5. What this changes — and what it does not

**Change (OOS-backed):** stop describing the unfiltered Asia breakout as a “clear, repeatable 1h edge.” It was a clear edge on GC=F and on spot **in 2024–2026**. It was a losing book on spot in 2012–2023. The playbook must say that in plain language. Default bias stays NONE unless a named setup is present *and* we accept that the recent edge may not persist.

**Do not adopt (tested, failed or scratch OOS):** half-range stops; dropping the 3× ATR cap; mechanical retrace entries at 38.2% or 50%; treating the rejection-retest as a core setup; promoting B-setup (including NY-with-trend) to a standalone book; treating “London only” as a long-sample upgrade.

**Keep:** 0.5% risk, one trade, hard stops, 1.5R / 3R scale, 2% daily loss stop, news blackout, no chase of a close already more than half the Asia range through the level, publish zones in spot, Friday no-new-entry into the weekly close. The 3× width skip stays as a sanity filter (wide days have worse continuation, and loosening the cap did not help).

**Watchlist (interesting, not yet a rule):** soft D+4H trend filter (best pre-registered variant, but almost all of its P&L is 2024–2026); Friday upward drift; whether the 2024–2026 breakout edge dies in the next few months — if it does, the default is back to NONE, not a wider set of weaker rules; Dukascopy 2003–2008 once the feed is stable; a verified CPI/PPI calendar.

## 6. Limitations

- Spot history starts March 2009, not 2000. Daily futures cover 2000+, but session studies and setups need intraday.
- 7–13 Nov 2026, including the post-mortem, is futures only.
- No official CPI/PPI history in the news table. NFP is a first-Friday proxy (holiday postponements are not all corrected). FOMC document stamps include some inter-meeting dates (2008, 2020); those days *did* move gold, but the set is not only scheduled statements.
- HistData is a retail spot feed, not the owner’s broker. Spread/slippage is a model.
- One-trade crowding means variants are not a clean ceteris-paribus grid.
- 2024–2026 includes an extraordinary bull and a violent 2026 selloff; results from that window should not be extrapolated without the 2012–2023 check we just did.

## 7. Re-running

```bash
source /workspace/gold-algo/.venv/bin/activate
export PYTHONPATH=/workspace/gold-algo
python research/deep-study-2026-11-14/download_extended.py   # HistData zips
python research/deep-study-2026-11-14/dataset.py             # resample
python research/deep-study-2026-11-14/news_calendar.py
python research/deep-study-2026-11-14/behavior_study.py
python research/deep-study-2026-11-14/retest_setups.py
```

Figures live in `figures/`. Tables live in `results/`.

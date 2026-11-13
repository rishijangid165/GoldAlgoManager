# XAU/USD — owner-requested demo trade #2 — 2026-11-13 17:44 IST (12:14 UTC)

**Type:** Owner-requested demo trade (not a high-bar researched signal). Rishi asked to take a demo fill now ("Ek demo trade lo", "Abhi") after a chart check showed gold bouncing toward, but still below, the 3909–3913 SELL retest zone.

**Account:** MetaQuotes-Demo login `<demo-login>` (demo, hedge). Demo-only; no real account.

## Brief multi-timeframe read (at decision / fill)

Spot ~3894.9 just before send (Swissquote ~3894.89 bid). MT5 XAUUSD bid **3894.80** / ask **3894.93** at send, fill **3894.81**. GC basis still ~+$4–5.

- **Daily / 4H:** LH/LL downtrend intact. The 15:30 IST push was rejected around 3908.8 GC / ~3903 spot, still inside 3905–3930 4H supply.
- **15M:** London had boxed ~3894–3905, then a push toward the sell zone that failed; price was mid-range at the fill, not a playbook A-setup (Asia range still ~$48, too wide) and not the 3909–3913 retest.
- **News:** US October PPI at **13:30 UTC / 19:00 IST**, blackout 13:00–15:00 UTC (18:30–20:30 IST). Position opened before the blackout with a hard SL and left running.

## New trade (placed)

| Field | Value |
| --- | --- |
| Side | SELL (trend direction) |
| Symbol | XAUUSD |
| Volume | 0.29 lots |
| Entry | 3894.81 (market) |
| SL | 3912.00 |
| TP | 3866.00 |
| Ticket / order | 11388939566 |
| Deal | 11147154203 |
| Magic / comment | 0 / `owner-requested-demo-2` |
| Equity at entry | $100,046.10 |
| Risk | $498.80 (~0.50% of equity; 0.5% cap $500.23, size rounded down) |
| R:R to TP | 1.67 (SL distance 17.20 vs bid, TP distance 28.80; fill 3894.81 → 17.19 / 28.81) |
| Time | 2026-11-13 17:44:48 IST (12:14:48 UTC); filled in 121.8 ms |
| Server retcode | 10009 Request executed |

Verified in MT5 terminal journal:

- `market sell 0.29 XAUUSD sl: 3912.00 tp: 3866.00`
- `deal #11147154203 sell 0.29 XAUUSD at 3894.81 done (based on order #11388939566)`
- script result code 0

SL 3912 was used because distance from spot (~$17.20) was inside the $8–$30 band; no fallback to entry+18 / entry−28.

**Lot-size note:** `SYMBOL_TRADE_TICK_VALUE` still printed 0.10, while contract size 100 × tick size 0.01 implies $1.00 per tick per lot. Size used the $1.00 figure (0.29 lots). If the broker value were actually 0.10, cash risk would be ~1/10 of $499 (under-risk, not over-risk).

Method: one-shot MQL5 script `GoldDemoSellOnce.mq5` compiled in MetaEditor (0 errors, 0 warnings) and launched via official terminal `/config` `[StartUp] Script=` on the already-logged-in demo portable terminal (`gold_sell_once.ini`). Script refuses any non-demo login/server and refuses a second XAUUSD position. StartUp script was disabled immediately after launch so a later restart cannot place a second order.

Owner Telegram fill alert was sent with `scripts/tg_send.sh` (ok) shortly after the fill.

## Follow-ups

- Trade left open through the PPI window; hard SL 3912 is the protection. Magic 0, so GoldAIBridge (magic 26011301) does not manage this fill.
- After this `/config` start, MT5 LiveUpdate applied build 6318 (12:16:58–12:17:04Z) and the chart EA dropped off. GoldAIBridge was reattached at 12:18:48Z on XAUUSD M15 with `C:\MT5\GoldAIBridge.set` (22 inputs) via `gold_ea_telegram.ini`. StartUp disabled immediately after the attach. EA journal: START + DECISION NONE (generated 12:17:56Z, already on GitHub with PPI blackout 13:00–15:00Z). Decision poll from GitHub succeeded.
- EA Telegram startup test failed with **4014** (`https://api.telegram.org` not in Tools → Options → Expert Advisors → Allow WebRequest after the restart — known Wine quirk). The URL list in `common.ini` did not persist the GUI-added telegram host. Needs a manual re-add on the running terminal; then confirm Experts log `WebRequest HTTP 200`. The owner's fill alert still went out via `tg_send.sh`.
- `gold_sell_once.ini` and `gold_ea_telegram.ini` StartUp sections are both disabled.

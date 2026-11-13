# XAU/USD — owner-requested demo trade #3 — 2026-11-13 18:35 IST (13:05 UTC)

**Type:** Owner-requested demo trade (not a high-bar researched signal). Rishi asked for another SELL now ("Ek aur SELL lo") in addition to ticket 11388939566. PPI was ~25 minutes away.

**Account:** MetaQuotes-Demo login `<demo-login>` (demo, hedge). Demo-only; no real account.

## Status of ticket 11388939566

This run did **not** close or modify ticket 11388939566. When the account was checked at about 18:34 IST, the Trade tab was already empty, equity equalled balance at **$100,226.19** (about +$180.09 vs $100,046.10 after the 11:11 IST close), and the earlier box session had reconnected at 12:57:01 UTC with "0 positions" after a disconnect whose previous authorization was from another IP. The box journal never recorded a close deal for 11388939566 (likely closed on the other session). The new fill below was placed on a flat account and is now the only open position.

## New trade (placed)

| Field | Value |
| --- | --- |
| Side | SELL |
| Symbol | XAUUSD |
| Volume | 0.34 lots |
| Entry | 3891.35 (market) |
| SL | 3906.00 |
| TP | 3866.00 |
| Ticket / order | 11389943963 |
| Deal | 11148219038 |
| Magic / comment | 0 / `owner-requested-demo-3` |
| Equity at entry | $100,226.19 |
| Risk | $498.10 (~0.50% of equity; 0.5% cap $501.13, size rounded down) |
| R:R to TP | 1.73 (SL distance 14.65, TP distance 25.35) |
| Time | 2026-11-13 18:35:30 IST (13:05:30 UTC) |
| Server retcode | 10009 Request executed |

SL 3906 was used because distance from bid (~$14.65) was inside the $8–$30 band; no fallback to entry+18 / entry−22.

**Lot-size note:** `SYMBOL_TRADE_TICK_VALUE` still printed 0.10; contract 100 × tick 0.01 implies $1.00 per tick per lot. Size used the $1.00 figure (0.34 lots).

**Method:** Intended one-shot MQL5 script `GoldDemoSell3.mq5` (demo-only guards, will not modify other tickets). MetaEditor **build 6318** (installed by the 12:17Z LiveUpdate) failed to compile any script, including a previously clean file, with `error 124: fatal compiler error: unknown error` at (0,0). The same fill was therefore sent once through the official **MetaTrader5 Python package** under Wine, attached to the already-running portable demo terminal, with the same demo-only login/server/mode guards, conservative tick value, and "do not modify existing tickets" rule. No second terminal was started for the fill. Owner Telegram fill alert was sent with `scripts/tg_send.sh` (ok).

Verified on the MT5 Trade tab (screenshot): SELL 0.34 XAUUSD at 3891.35, SL 3906.00, TP 3866.00, ticket 11389943963, algo trading on, GoldAIBridge still on the XAUUSD M15 chart.

## Terminal / EA

- The terminal **was restarted once** earlier in this run (13:00–13:04 UTC) while trying to compile; GoldAIBridge was reattached at 13:04:13 UTC on XAUUSD M15 with `C:\MT5\GoldAIBridge.set` (22 inputs) via `gold_ea_telegram.ini`. StartUp was then disabled.
- The fill at 13:05:30 UTC used that same running process; no second restart.
- After the restart, **https://api.telegram.org needs to be re-added** in Tools → Options → Expert Advisors → Allow WebRequest (Wine quirk). EA chart alerts will not go out until that is done. The fill alert already went out via `tg_send.sh`.
- `gold_sell_once.ini` and `gold_ea_telegram.ini` StartUp sections are both disabled.
- Trade left open through the PPI window (19:00 IST) with hard SL 3906.

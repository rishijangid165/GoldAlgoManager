# XAU/USD — owner-requested demo trade #4 — 2026-11-13 23:24 IST (17:54 UTC)

**Type:** Owner-requested demo trade (not a high-bar researched signal). Rishi asked to take a trade now ("Ek trade lena") on Friday night, after being told the book was flat and there was no playbook setup into the weekend close.

**Account:** MetaQuotes-Demo login `<demo-login>` (demo, hedge). Demo-only; no real account.

## Pre-trade check

Verified flat on the already-running portable terminal before the send:

- Balance / equity **$100,453.65**, margin $0.00
- 0 open positions, 0 pending orders
- trade_mode=demo, server MetaQuotes-Demo, trade allowed
- Spot bid/ask about 3889.83 / 3889.96 (Swissquote earlier ~3889.56)

## New trade (placed)

| Field | Value |
| --- | --- |
| Side | SELL |
| Symbol | XAUUSD |
| Volume | 0.37 lots |
| Entry | 3889.51 (market) |
| SL | 3903.00 |
| TP | 3868.00 |
| Ticket / order | 11397685376 |
| Deal | 11156335832 |
| Magic / comment | 0 / `owner-requested-demo-4` |
| Equity at entry | $100,453.65 |
| Risk | $500.24 (~0.50% of equity; 0.5% cap $502.27, size rounded down) |
| R:R to TP | 1.59 (SL distance 13.52, TP distance 21.48 vs bid 3889.48) |
| Time | 2026-11-13 23:24:49 IST (17:54:49 UTC) |
| Server retcode | 10009 Request executed |

SL 3903 was used because distance from bid (~$13.52) was inside the $8–$30 band; no fallback to entry+16 / entry−19.

**Lot-size note:** `SYMBOL_TRADE_TICK_VALUE` still printed 0.10; contract 100 × tick 0.01 implies $1.00 per tick per lot. Size used the $1.00 figure (0.37 lots).

**Method:** Official MetaTrader5 Python package under Wine, attached to the already-running portable demo terminal (same process as the afternoon session; **no terminal restart**). Same demo-only login/server/mode guards as the 18:35 IST fill, and the script aborts if the account is not flat. Owner Telegram fill alert was sent with `scripts/tg_send.sh` (ok).

Verified on the MT5 Trade tab: SELL 0.37 XAUUSD at 3889.51, SL 3903.00, TP 3868.00, ticket 11397685376, algo trading on, GoldAIBridge still on the XAUUSD M15 chart.

## Terminal / EA

- Terminal was **not** restarted for this fill (same `terminal64.exe /portable /config:gold_ea_telegram.ini /skipupdate` process).
- GoldAIBridge remains attached on XAUUSD M15 from the 13:04:13 UTC reattach with `C:\MT5\GoldAIBridge.set`. Decision on the chart is still NONE (Friday-close stand-aside).
- StartUp on both ini files remains disabled.
- Trade left open with hard SL 3903. This is Friday night; weekend gap risk sits on the owner-requested fill.

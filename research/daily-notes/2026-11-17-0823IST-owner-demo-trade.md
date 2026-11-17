# XAU/USD — owner-requested manual-book demo trade — 2026-11-17 08:23 IST (02:53 UTC)

**Type:** Owner-requested demo trade, logged in the separate manual book (playbook §16). Not a system/probation setup. Rishi asked to take a trade now ("Ek trade lo abhi") on Tuesday Asia session, after being told no playbook setup had qualified since Monday night.

**Account:** MetaQuotes-Demo login `<demo-login>` (demo, hedge). Demo-only; no real account.

## Pre-trade check

Verified flat on the already-running portable terminal before the send:

- Balance / equity **$100,155.39**, margin $0.00
- 0 open positions, 0 pending orders
- trade_mode=demo, server MetaQuotes-Demo, trade allowed
- Bid/ask 3864.68 / 3864.85, spread 17 points, stops_level 0

## Multi-timeframe read (broker data)

- **Daily:** Close 3863, well below SMA20 3995 / SMA50 4133 / SMA200 4429. Lower highs 4148 → 4067 → 4000 → 3923 → 3901 → 3873 (in progress). 16 Nov low 3832.35 is the recent swing low. ATR14 ~115.
- **4H:** Below SMA20 3888.69 / SMA50 4003 / SMA200 4070. Last confirmed swing high **3888.92** (16 Nov 19:30 IST). Last swing lows 3832.35 then 3841.15. ATR14 ~30.6.
- **1H:** Price slightly above SMA20 3861, still below SMA50 3878 and SMA200 4010. Last confirmed swing high 3888.92. Today's forming high 3872.97. ATR14 ~15.9.
- **15M:** Short-term bounce off 3843.42 (06:45 IST) to 3872.97 (07:45 IST), then back to ~3865 — mid Asia range (so far 3843.42–3872.97). Below SMA200 3878.
- **News:** No high-impact window now. Retail Sales blackout is 18:30–20:30 IST.

Direction with the higher-timeframe trend: **SELL**. SL placed beyond the last confirmed 1H/4H swing high (3888.92), not just above the 3873 Asia high — yesterday's tighter manual SL at 3872.50 was stop food.

## New trade (placed)

| Field | Value |
| --- | --- |
| Side | SELL |
| Symbol | XAUUSD |
| Volume | 0.19 lots |
| Entry | 3864.66 (market) |
| SL | 3890.00 |
| TP | 3820.00 |
| Ticket / order | 11427574952 |
| Deal | 11187806400 |
| Magic / comment | 0 / `manual-book` |
| Equity at entry | $100,155.39 |
| Risk | $481.46 (~0.48% of balance; 0.5% cap $500.78, size rounded down) |
| R:R to TP | 1.76 (SL distance 25.34, TP distance 44.66 vs fill 3864.66) |
| Time | 2026-11-17 08:23:42 IST (02:53:42 UTC) |
| Server retcode | 10009 Request executed |
| SL/TP on position | verified (3890.00 / 3820.00) |

**Lot-size note:** `SYMBOL_TRADE_TICK_VALUE` still printed 0.10; contract 100 × tick 0.01 implies $1.00 per tick per lot. Size used the $1.00 figure (0.19 lots).

**Method:** Official MetaTrader5 Python package under Wine (`C:\winpy\place_sell7.py`), attached to the already-running portable demo terminal (**no terminal restart**, GoldAIBridge not touched). Demo-only login/server/mode guards; script aborts if the account is not flat or not MetaQuotes-Demo. Owner Telegram fill alert was sent with `scripts/tg_send.sh`.

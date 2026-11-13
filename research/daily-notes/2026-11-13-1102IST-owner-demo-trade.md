# XAU/USD — owner-requested demo trade — 2026-11-13 11:02 IST (05:32 UTC)

**Type:** Owner-requested demo trade (not a high-bar researched signal). Rishi asked to take a demo fill now ("Le lo wese hi bs") after being told the rejection setup was not confirmed.

**Account:** MetaQuotes-Demo login <demo-login> (demo, hedge). Demo-only; no real account.

## Earlier ticket 11377847166 (12 Nov test SELL)

Confirmed from MT5 history (and terminal journal):

- Open: 2026-11-13 01:10:30 IST (2026-11-12 19:40:30 UTC / server 21:40:30) market SELL 0.01 XAUUSD at **3882.56**, SL 3905.00, TP 3850.00, deal 11135687590, comment `test`, magic 0.
- Close: 2026-11-13 04:30:01 IST (2026-11-12 23:00:01 UTC / server 2026-11-13 01:00:01) at **3905.00**.
- Deal 11136655706, order 11378779166, entry OUT, reason SL (`[sl 3905.00]`).
- Profit **-$22.44**, swap **-$0.05**, commission $0.00, net **-$22.49**.
- Start-of-day equity after the close: **$99,977.46**.

## Brief multi-timeframe read (at decision / fill)

GC=F around 3920 a few minutes earlier; MT5 XAUUSD (spot) bid **3914.84** / ask **3914.97** at send, fill **3914.82**. Basis still ~+$5–6 vs futures.

- **Daily:** Lower-high / lower-low downtrend intact after the 2026 low (futures 3856.7 / spot ~3852.7). Today a relief bar inside that trend. MA20/50/200 still well above. DXY ~103.17.
- **4H:** Still LH/LL; RSI mid-20s to ~29. The bounce tagged the planned supply / breakdown area.
- **1H:** Impulse off the Asia low into the 3905–3930 spot sell zone. Futures 1H high 3925.2 with closes ~3919.8 (spot close ~3914), so the "1H close above 3925 spot" invalidation had **not** triggered. RSI no longer oversold.
- **15M:** Bounce stretched (RSI had been very high), then a small pause around 3915–3921 spot. No clean bearish rejection close was required for this fill because the owner asked to take the trade anyway.

**News:** Selloff drivers (hot CPI, hawkish Fed talk, firm dollar) still in the background. US October PPI at **13:30 UTC / 19:00 IST**, blackout 13:00–14:30 UTC (18:30–20:00 IST). This position was opened before the blackout and left running.

## New trade (placed)

| Field | Value |
| --- | --- |
| Side | SELL (trend direction) |
| Symbol | XAUUSD |
| Volume | 0.16 lots |
| Entry | 3914.82 (market) |
| SL | 3945.00 |
| TP | 3860.00 |
| Ticket / order | 11382667647 |
| Deal | 11140626981 |
| Magic / comment | 0 / `owner-requested-demo` |
| Equity at entry | $99,977.46 |
| Risk | $482.56 (~0.48% of equity; 0.5% cap $499.89, size rounded down) |
| R:R to TP | 1.82 (SL distance 30.16, TP distance 54.84) |
| Time | 2026-11-13 11:02:24 IST (05:32:24 UTC); filled in 107 ms |
| Server retcode | 10009 Request executed |

Verified in MT5 terminal journal:

- `market sell 0.16 XAUUSD sl: 3945.00 tp: 3860.00`
- `deal #11140626981 sell 0.16 XAUUSD at 3914.82 done (based on order #11382667647)`
- script result code 0

Method: one-shot MQL5 script `GoldDemoSellOnce.mq5` compiled in MetaEditor and launched via official terminal `/config` `[StartUp] Script=` on the already-logged-in demo portable terminal. Script refuses any non-demo login/server. StartUp script was disabled immediately after the fill so a later restart cannot place a second order.

**Lot-size note:** After sync, `SYMBOL_TRADE_TICK_VALUE` still printed 0.10, while contract size 100 × tick size 0.01 implies $1.00 per tick per lot. Size used the $1.00 figure (0.16 lots). If the broker value were actually 0.10, cash risk would be ~1/10 of $482 (under-risk, not over-risk).

## Reasoning

Prefer trend-direction SELL: price was still inside/near the planned 3905–3930 spot sell zone, Daily/4H downtrend had not broken, and the 1H close invalidation above 3925 spot had not triggered. A disciplined setup would still have waited for a 1H (or two 15M) bearish rejection close; this fill was taken at the owner's request without that confirmation. SL above the bounce / next supply (~3940–3945 plan), TP at 3860 structure (plan TP2) to keep R:R ≥ 1.5. Only one trade; no real account.

## Follow-ups

- Position is open through the later PPI window unless the owner wants it managed or flattened before 13:00 UTC.
- After this `/config` restart, GoldAIBridge may not be attached on the chart. It uses magic 26011301, so it should not manage this magic-0 fill even if reattached.
- GitHub token still needed to publish decisions.

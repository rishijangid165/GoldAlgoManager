# GoldAIBridge v1.04: prop-firm readiness

Target: be ready for a prop-firm free trial / challenge review on **Sat 12 Dec 2026**.
Live system today: demo account only (v1.03.1 live; v1.04 built and compiled, not yet deployed).

## What v1.04 adds

| Area | What it does | Default (demo preset) | FTMO preset |
|---|---|---|---|
| Prop guard: daily loss | Measures equity against a start-of-day reference. At the guard level it blocks new entries, closes EA positions, deletes EA pending orders, sends Telegram. Stays blocked until the next daily reset. | OFF | 4% of initial (firm 5%) |
| Day reset | Reset hour in a chosen zone: broker server time, UTC, CE(S)T (Prague, DST-aware) or New York (DST-aware). | server 00:00 | CE(S)T 00:00 |
| Day reference | Balance, equity, or the higher of both at reset. If the EA was offline at reset, the balance is rebuilt from deal history and equity is taken as the higher of that and current equity. | MAX | MAX (stricter than FTMO's balance base) |
| Prop guard: max drawdown | Equity floor = initial - X% of initial (static) or high-water mark - X% (trailing, optional lock at initial). On trip: block + flatten + Telegram, and a **permanent latch** until cleared by hand. | OFF | 8% static (firm 10%) |
| Pre-trade fit check | A new trade is refused unless `risk x 1.25` still fits inside both the remaining daily room and the remaining DD room. | OFF | ON |
| Max open EA positions | Across all symbols (EA magic only). | 1 (guard off) | 1 |
| Daily profit cap | Blocks new entries after X% daily gain (optional flatten). | 0 = off | 0 = off (use 2% for E8 Pro) |
| Warning | One Telegram per day when 75% of an allowance is used. | — | 0.75 |
| Prop news mode | For each listed news event (MT5 calendar + news.json): close EA positions / delete EA pending N min **before** the release, no entries until M min after. Ambiguous calendar records (`calendar~`) are covered on both candidate times. Works even if the normal 30/90 entry blackout is off. | OFF | ON, 10 min before / 5 min after |
| Demo guard | `InpAllowLiveAccount=false` (replaces `InpAllowRealAccount`): any non-DEMO account (REAL or CONTEST) is locked. Optional `InpAllowedServers` allow-list (substring, e.g. `FTMO`). Startup log prints mode, server, company, masked login, and guard switches. | false / any server | false / `FTMO` |
| Friday close | Unchanged: no entries after the Friday cutoff, flatten about 45 min before the weekly close. | ON | ON |
| Telegram | `/status` now shows the prop guard and news mode lines; new `/guard` command. | | |

State is stored in terminal global variables scoped by **magic + account login**
(`GoldAI_<magic>_<login>_pg_*`): initial balance, peak, day start, day base, daily-trip day,
DD latch, profit-cap day, warning day. It survives restarts and does not leak between accounts.

To clear a tripped DD latch: set `InpPropResetDDLatch=true`, press OK, then set it back to `false`.

## Presets (token-free)

- `mql5/Presets/GoldAIBridge_demo.set`: current live behaviour (trailing OFF, Friday close ON, prop guard OFF, news blackout 30/90).
- `mql5/Presets/GoldAIBridge_prop_ftmo.set`: FTMO 5%/10% firm, guard 4%/8%, CE(S)T reset, news-flat ON, server allow-list `FTMO`, separate journal `GoldAI_journal_prop.csv`.
- The old `GoldAIBridge.set` is the v1.03 preset and is now legacy. It has `InpAllowRealAccount`, which v1.04 ignores, so the default `false` applies.

Telegram token and chat id are **blank** in both files. Paste them only into the EA dialog on the box.

### Suggested settings for other firms (adjust the FTMO preset)

| Firm / program | Firm rule (verified Nov 2026, re-check before buying) | Guard settings |
|---|---|---|
| **FTMO 2-Step (Standard or Swing)** | Daily 5% of initial, floor = balance at 00:00 CE(S)T - 5%. Max loss 10% of initial. EAs allowed. Standard **funded** accounts: no order fill (incl. SL/TP/pending) 2 min before to 2 min after restricted news (USD: rate decision, NFP, unemployment/wages, advance GDP, FOMC minutes, CPI) and close before the weekend. Challenge/Verification and Swing have no news restriction. | As preset. On Swing you may turn news-flat off. |
| **The5ers High Stakes** | Daily 5% of the **higher of balance/equity at 00:00 server time** (GMT+2/+3). Max loss 10% static. No order fill 2 min either side of high-impact news (profit deducted). Weekend holding allowed. **EA needs written approval first.** | `InpPropDailyPctOfInitial=false`, `InpPropDayBase=2` (MAX), `InpPropResetTz=0` (server), daily 4, DD 8, news-flat ON, `InpAllowedServers=5ers` (check the exact server name). |
| **E8 Pro** | Daily 2.5% of initial, from the day's starting balance at 00:00 server time; breach on equity **or** balance. Max 8% static. Only 2% of initial per day counts toward the target. News trading allowed. EAs allowed within server/request limits. | `InpPropFirmDailyLossPct=2.5`, `InpPropDailyLossPct=2.0`, `InpPropDayBase=0`, `InpPropResetTz=0`, `InpPropFirmMaxDDPct=8`, `InpPropMaxDDPct=6.5`, `InpPropDailyProfitCapPct=2.0`, news-flat optional, `InpAllowedServers=E8`. |

Sources: academy.ftmo.com (Maximum Daily Loss), ftmo.com/en/faq/can-i-trade-news, help.e8markets.com (E8 Pro, Daily Drawdown), the5ers.com/high-stakes and their FAQs.

## Free-trial checklist (do before paying for any challenge)

Use this on a free trial (for example FTMO Free Trial). **No purchase and no sign-up without Rishi's OK.**

1. **Terminal**: install the firm's MT5 (or add its server), log in on the trial account, and open an XAUUSD chart. The symbol may be `XAUUSD` or carry a suffix. `InpExpectedSymbol=XAUUSD` matches gold aliases.
2. **WebRequest**: Tools > Options > Expert Advisors > allow WebRequest for
   - `https://raw.githubusercontent.com` (decision + news.json)
   - `https://api.telegram.org` (alerts + commands)
   Confirm in the Experts log: `telegram startup test sent, WebRequest HTTP 200` and a decision poll with HTTP 200.
3. **Algo trading** button ON; the EA "Allow Algo Trading" box is ticked.
4. **Attach** GoldAIBridge v1.04 with `GoldAIBridge_prop_ftmo.set`. Set `InpPropInitialBalance` to the account size, paste the Telegram token/chat id, and use a **different magic** (e.g. 26011302) if the same terminal also runs the demo EA.
5. **Startup log** must show: `account: mode=DEMO server=FTMO-Demo...`, `prop guard ON: initial=...`, `new prop day from ...`. If mode is `REAL` or `CONTEST`, the EA locks itself. Only then decide to set `InpAllowLiveAccount=true`.
6. **Telegram**: `/status` shows `Prop guard: OK | day P/L ... DD floor ...`. `/guard` shows initial, peak, day start, base.
7. **Calendar**: the panel `News src: cal OK n` line shows the calendar is readable on that server. Firm terminals sometimes have no MT5 calendar, in which case news.json alone is used. Keep news.json filled past January 2027.
8. **Guard drill** (trial only): temporarily set `InpPropDailyLossPct=0.05`, open a tiny manual trade, and watch for a trip + Telegram. Restore 4.0. The daily trip clears at the next CE(S)T midnight.
9. **News-flat drill**: before the next listed release, confirm the panel shows `PropNews: FLAT WINDOW ...` from 10 min before, and that no EA entry happens until 5 min after.
10. **VPS / hosting rules**: FTMO allows a VPS. The5ers needs written EA approval. FundingPips disallows VPS (excluded). The box runs MT5 under Wine 24/7, which counts as a VPS-style host. Confirm the firm allows the IP/region and does not flag a shared IP.
11. **Friday close**: check the Friday cutoff/flatten line on the panel. FTMO Standard funded requires flat over the weekend.
12. **Record**: keep at least 20-30 system trades on demo with PF > 1.3 and max DD < 5% before paying (review on 12 Dec 2026).

## Self-test

- `mql5/Scripts/GoldPropGuardSelfTest.mq5`: an offline unit test of the guard maths (DST, day start in CE(S)T / New York / server / UTC, allowances, static/trailing floors, evaluate flags, pre-trade fit, news-flat windows incl. widened records). Drop it on any chart. It needs no trading or network. Expect `ALL PASS` in the Experts log and in `MQL5/Files/GoldPropGuardSelfTest.txt`.
- The day-start algorithm was cross-checked in Python against `zoneinfo` (Europe/Prague, America/New_York, reset hours 0/17/22) every 15 min over 2026-2028: 630,720 checks, 0 mismatches.

## Known limits / open risks

- The guard acts on ticks and the 1-second timer. A fast gap can still overshoot the guard level, so the buffer (4% vs 5%, 8% vs 10%) is the protection.
- If the EA is offline at the reset, equity at the reset instant is unknown. It is approximated conservatively.
- Flatten only closes EA positions unless `InpPropFlattenManual=true`. Manual trades on a prop account still count toward the firm's limits.
- Holiday sessions (Thanksgiving, Christmas, New Year) with market breaks over 2 hours are **not** auto-flattened. FTMO Standard funded requires flat before them, so flatten by hand or use `/closeall`.
- The news list is broader than FTMO's restricted list (it also has PPI, retail sales, PCE). That is stricter, so fewer trades.
- The FTMO 1-Step product uses 3% daily and an end-of-day trailing 10%. Use `InpPropDailyLossPct=2.5` and `InpPropDDTrailing=true` there.

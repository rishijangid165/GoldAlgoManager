# GoldAI Bridge — Setup for MetaTrader 5

This Expert Advisor (EA) does **not** invent its own entry rules. An AI assistant researches gold, writes a small JSON **decision file**, and the EA only trades when price comes into the zone in that file.

Simple picture (seedha matlab):

- **AI / assistant = dimaag.** It studies the market and writes `decisions/current.json`.
- **EA = haath.** It polls that file, respects hard risk limits, and places or closes the trade.
- Start on a **DEMO** account only. Live trading is blocked unless you turn that protection off yourself.

---

## 1. Copy the files into MT5

1. In MetaTrader 5, click **File > Open Data Folder**.
2. Open the `MQL5` folder inside it.
3. Copy:
   - `gold-algo/mql5/Experts/GoldAIBridge.mq5`  →  `MQL5/Experts/`
   - everything in `gold-algo/mql5/Include/` (`GoldAIJson.mqh`, `GoldAIDecision.mqh`, `GoldAIUtil.mqh`, `GoldAIJournal.mqh`)  →  `MQL5/Include/`
4. In MT5, open **Navigator** (Ctrl+N), right-click **Expert Advisors**, and click **Refresh**.
5. Double-click `GoldAIBridge` (or right-click > **Modify**) so MetaEditor opens it, then press **F7** to compile. You want **0 errors**. Warnings should be read, but the EA must compile cleanly before you attach it.

Hindi hint: *Data Folder waley `MQL5/Experts` aur `MQL5/Include` mein files copy karo, phir F7 dabake compile karo.*

---

## 2. Allow the decision-file URL (WebRequest)

The EA uses MT5 `WebRequest` to download the JSON. MT5 will block this until you allow the URL.

1. In MT5 go to **Tools > Options** (or Ctrl+O).
2. Open the **Expert Advisors** tab.
3. Tick **Allow WebRequest for listed URL**.
4. Click **Add** and paste the **base** URL of your host, for example:
   - `https://raw.githubusercontent.com`
   - `https://gist.githubusercontent.com`
   - `https://api.telegram.org`  (needed for instant trade alerts)
5. Click **OK**.

If this step is skipped, the Experts log will show error **4014** and the chart panel will say the poll failed.

You also need **Algo Trading** enabled (the toolbar button, or **Tools > Options > Expert Advisors > Allow algorithmic trading**).

---

## 3. Attach the EA to a gold chart — DEMO first

1. Open a **DEMO** account chart for gold. Common names: `XAUUSD`, `XAUUSDm`, `XAUUSD.m`, `GOLD`, `GOLDm`. The EA maps these suffixes automatically.
2. Timeframe can be M15 or H1; the EA trades from the decision file, not from candle patterns, but a clean gold chart is easier to watch.
3. Drag **GoldAIBridge** onto the chart.
4. In the **Common** tab, tick **Allow Algo Trading**.
5. In the **Inputs** tab, set `DecisionURL` (see section 5). Leave `AllowRealAccount` = **false**.
6. Click **OK**. You should see a comment panel in the top-left of the chart, and a smiley / EA icon in the top-right.

Agar account real/live hai aur `AllowRealAccount` false hai, EA **trade nahi karega**. Yeh safety feature hai — ise on mat karo jab tak demo par system prove na ho jaye.

The bundled `decisions/current.json` starts with `"bias": "NONE"`, so the EA will poll and show the panel but will not open a trade until a real researched decision is published.

---

## 4. Input settings (what each one means)

### Connection

| Input | Default | Meaning |
|---|---|---|
| `DecisionURL` | placeholder GitHub raw URL | Full URL to `current.json`. Must be allowed in WebRequest (section 2). |
| `PollMinutes` | 5 | How often the EA re-downloads the file. Minimum 1 minute. Trade *management* (SL / TP1) still happens on every tick. |
| `WebTimeoutMs` | 8000 | HTTP timeout in milliseconds. |
| `UseLocalFile` | false | If true, read `LocalFileName` from `MQL5/Files` instead of the web. Useful for a first test before hosting is ready. |
| `LocalFileName` | `current.json` | File name inside `MQL5/Files` when `UseLocalFile` is true. |

### Symbol

| Input | Default | Meaning |
|---|---|---|
| `ExpectedSymbol` | `XAUUSD` | Logical name in the decision file. `GOLD` and broker suffixes (`XAUUSDm` …) are treated as the same instrument. |

### Risk (locked in the EA — the JSON cannot loosen these)

| Input | Default | Meaning |
|---|---|---|
| `RiskPercentPerTrade` | 0.5 | Max percent of equity to risk on one trade. The file’s `max_risk_pct` can only go **lower**, never higher. |
| `MaxDailyLossPct` | 2.0 | If equity is down this much from the start-of-day (server time) equity, no new trades that day. Open trades are still managed. |
| `MaxOpenTrades` | 1 | Max GoldAI positions on this symbol (this EA’s magic number). |
| `MaxSpreadPoints` | 50 | Block a new entry if the current spread is wider than this, in **symbol points** (not pips). Watch the chart panel — gold digits differ by broker. |
| `MinConfidence` | 60 | Ignore a BUY/SELL decision whose `confidence` is below this. |
| `MagicNumber` | 26011301 | Marks this EA’s orders. Do not let two EAs share the same magic on the same symbol. |
| `SlippagePoints` | 30 | Max price deviation for market orders, in points. |

### Safety

| Input | Default | Meaning |
|---|---|---|
| `AllowRealAccount` | **false** | Leave this off. The EA refuses to trade on a real account unless you explicitly set this to true. |

### Trade management

| Input | Default | Meaning |
|---|---|---|
| `TP1CloseFraction` | 0.5 | Close this fraction of the lot at TP1, then move the stop to breakeven. If the position is already the broker’s minimum lot, the EA only moves the stop and lets TP2 work. |
| `BreakevenOffsetPoints` | 0 | Extra points beyond entry when moving the stop to breakeven (to help cover commission). |
| `CloseOnBiasFlip` | true | Close the open GoldAI trade if a new decision changes bias (BUY↔SELL) or goes to NONE. |
| `CloseOnKillSwitch` | true | If the file has `"kill_switch": true`, flatten GoldAI positions and do not open new ones. |

### Friday close (v1.02)

On Friday (server time) the EA flattens its own positions and pending orders shortly before the broker’s weekly gold close, then blocks new entries until after the weekend. A missed flatten is also attempted early Saturday (first 6 hours of server Saturday). The EA still uses **server time**, not your local clock.

| Input | Default | Meaning |
|---|---|---|
| `FridayCloseEnabled` | true | Turn Friday auto-close on or off. |
| `FridayCloseHHMM` | 0 | Flatten at this server time as `HHMM` (for example `2315` = 23:15). `0` means **auto**: 45 minutes before the symbol’s last Friday trade session end (`SymbolInfoSessionTrade`). If the session cannot be read, it falls back to 24:00 Friday minus 45 minutes (23:15 server). |
| `FridayNoEntryMinutes` | 120 | Block new entries this many minutes before the flatten time (default 2 hours). |
| `FridayCloseManual` | **false** | If true, also flatten **magic 0** manual positions and pending orders on this symbol. Other EAs’ magic numbers are never touched. Leave this off unless you want the EA to close your manual gold trades on Friday too. |

A Telegram alert is sent when at least one position or pending order is closed this way (once per Friday).

### Trailing after TP1 (v1.02)

After the existing half-close at TP1 and the move to breakeven, the remaining half can trail. The stop **only tightens** (never loosens) and always respects the broker’s `StopsLevel` / freeze level. The trail is measured against the **current bid/ask**, not the original entry, so a profitable trail can sit beyond the entry.

| Input | Default | Meaning |
|---|---|---|
| `TrailEnabled` | true | Trail the remaining half after TP1 + breakeven. |
| `TrailUseSwing` | true | Use the last confirmed swing on `TrailTF` (last closed bars). BUY trails behind the last swing low; SELL behind the last swing high. |
| `TrailUseATR` | true | Also compute a stop from `ATR(TrailATRPeriod) * TrailATRMult` on `TrailTF`. |
| `TrailTF` | M15 | Timeframe for the swing and the ATR. |
| `TrailSwingBars` | 2 | Bars on each side required to confirm a swing. |
| `TrailATRPeriod` | 14 | ATR period. |
| `TrailATRMult` | 1.0 | ATR multiplier. |
| `TrailMinStepPoints` | 20 | Ignore a tighten smaller than this, in symbol points. |
| `TrailTelegramMinSec` | 300 | Minimum seconds between trail Telegram alerts (throttled). |

If both swing and ATR are on, the EA uses the **tighter** of the two valid stops. A Telegram alert is sent on each meaningful trail, subject to the throttle. Telegram failures never block a trail or a Friday close.

### Journal

| Input | Default | Meaning |
|---|---|---|
| `JournalFile` | `GoldAI_journal.csv` | Written under `MQL5/Files`. Copy it out for review with `scripts/review_journal.py`. |

### Telegram alerts

The EA can send a short plain-text message the moment a trade opens, TP1 is taken (partial close + stop to breakeven), the remaining stop is trailed, a Friday auto-close flattens positions, a position closes, a new decision is received, or a hard error happens (decision WebRequest failure, kill switch, daily loss stop). A one-line `GoldAIBridge online` test is also sent when the EA is attached.

| Input | Default | Meaning |
|---|---|---|
| `EnableTelegram` | true | Turn alerts on or off. |
| `TelegramToken` | (empty) | Bot token from BotFather. Keep this private. Put it only in the local MT5 `.set` / Inputs box. **Do not commit it to git, and do not paste it in chat.** |
| `TelegramChatId` | (empty) | Numeric chat id that should receive the alerts. |

Also add `https://api.telegram.org` to the allowed WebRequest list (section 2). If the token, chat id, or URL is missing, the EA still trades — it only writes a line in the Experts log. Telegram failures never block an entry, an exit, or TP1 handling.

---

## 5. Hosting the decision file

The EA needs a **public HTTPS URL** that returns raw JSON (not an HTML page).

**Recommended:** a public GitHub repository (or a GitHub Gist) and its **raw** URL. The assistant can update `decisions/current.json` in that repo, and the EA will pick it up on the next poll.

Examples (these are **placeholders** — replace with your real account and repo once you decide):

```
https://raw.githubusercontent.com/USER/REPO/main/decisions/current.json
https://gist.githubusercontent.com/USER/GIST_ID/raw/current.json
```

Notes:

- In **Tools > Options > Expert Advisors**, add the *base* host (`https://raw.githubusercontent.com` or `https://gist.githubusercontent.com`), not only the full file path.
- Always use the **raw** link. A normal GitHub file page is HTML, and the EA cannot parse that.
- GitHub can cache raw files for a short time. The EA appends a timestamp query (`?t=...`) to reduce stale reads.
- Keep the repo / gist public so MT5 does not have to log in.
- Other hosts (a small VPS, object storage, a paste service with a stable raw HTTPS URL) also work, as long as `WebRequest` is allowed for that host.

**Until hosting is decided, leave `DecisionURL` as the placeholder and use the local-file path for tests:**

1. Copy `gold-algo/decisions/current.json` into `MQL5/Files/current.json`.
2. Set `UseLocalFile` = true.
3. After the assistant writes a new decision, copy the file in again (or set up hosting).

The assistant writes and validates the file with:

```bash
source /workspace/gold-algo/.venv/bin/activate
python /workspace/gold-algo/scripts/write_decision.py --bias NONE \
  --rationale "Waiting for the next window" --valid-hours 6
```

---

## 6. How a normal day should feel

1. Assistant researches gold (levels, dollar, yields, news) and writes a new `current.json`.
2. Within `PollMinutes`, the chart panel updates: bias, zone, SL, TPs, confidence, rationale, time left.
3. If bias is BUY or SELL, confidence is high enough, spread is OK, and *price is inside the zone*, the EA opens **one** market trade. Lot size comes from risk percent and the distance to the file’s stop-loss.
4. At TP1 it closes part of the position and moves the stop to breakeven. The rest targets TP2, and from that point the remaining half can trail (structure swing and/or ATR) — the stop only tightens, and never tighter than the broker’s stop level.
5. If the file goes stale (`valid_until` has passed), the kill switch is on, a news blackout window is active, or the Friday no-entry cutoff has been reached, it will not open a new trade. A kill switch or a bias flip can close an open trade. On Friday, at the configured flatten time (default: 45 minutes before the broker’s Friday gold session end), the EA closes its own positions, deletes its pending orders, and stays flat through the weekend.
6. Everything is logged in the Experts log and in `GoldAI_journal.csv`. If Telegram is configured, the same events also send an instant message (trade opened, TP1 + breakeven, trailing stop move, Friday auto-close, position closed with reason and P&L, new decision, or a hard error).

Review a session:

```bash
python /workspace/gold-algo/scripts/review_journal.py /path/to/GoldAI_journal.csv
```

---

## 7. Safety reminders

- Demo first. Always.
- The EA cannot think. If the decision file is wrong, the trade will be wrong — only the hard caps (risk %, daily loss, spread, max trades, demo lock) will still protect you.
- `WebRequest` does **not** work in the MT5 Strategy Tester. Test on a demo chart with a live poll or `UseLocalFile`.
- Do not share a real-account login, and do not turn `AllowRealAccount` on casually.
- If something looks wrong, use the kill switch in the decision file, or simply remove the EA from the chart / disable Algo Trading.

---

## 8. Quick checklist

- [ ] Files copied to `MQL5/Experts` and `MQL5/Include`
- [ ] Compiled with F7, 0 errors
- [ ] WebRequest URL allowed (or `UseLocalFile` on for a first test)
- [ ] `https://api.telegram.org` allowed if Telegram alerts are used
- [ ] Telegram token and chat id set in Inputs (never committed to git)
- [ ] Algo Trading enabled
- [ ] Attached to a DEMO gold chart
- [ ] `AllowRealAccount` is false
- [ ] Chart panel shows a successful poll (or a successful local file read)
- [ ] Hosting URL decided and confirmed with the assistant (still open)

## v1.03 additions (2026-11-14)

### News auto-blackout
- Blocks **new** entries from `InpNewsBlackoutBeforeMin` (30) minutes before to `InpNewsBlackoutAfterMin` (90) minutes after high-impact USD releases. Open positions are never closed by it.
- Source 1: MT5 built-in Economic Calendar (`CalendarValueHistory`, currency USD). An event counts when its name matches `InpNewsKeywords` (NFP, unemployment, AHE, CPI, PCE, GDP, PPI, retail sales, Fed rate decision, FOMC minutes/statement/press conference/projections, "Fed Chair") **and** importance >= `InpNewsMinImportance` (2 = moderate; FOMC Minutes is moderate in the MT5 calendar). `InpNewsAllHighUSD=true` additionally blocks every USD HIGH event (jobless claims, ISM, EIA, auctions...).
- Source 2: static list `decisions/news.json` (UTC times) read through WebRequest from raw.githubusercontent.com every `InpNewsRefreshMinutes`, cached in `MQL5/Files/GoldAI_<magic>_news_cache.json` for offline restarts. Both sources are always merged.
- Calendar time base (v1.03.1): `MqlCalendarValue.time` is not in one base on this terminal; some records come in server time (GMT+2), others already in UTC. Each record is resolved separately: candidates `raw - S` (S = `TimeTradeServer() - TimeGMT()`) and `raw`; the one on a New York release slot (08:30 / 10:00 / 14:00 / 14:30 ET, US DST aware) wins; if neither or both match, the window is widened to cover both (`calendar~`). The panel's `News src` line shows the counts.
- A blocked actionable decision is journaled (`NEWS_BLOCK`) and alerted on Telegram (one alert per decision+window, min `InpNewsAlertMinMinutes` apart).
- The decision file's own `news_blackout` array still works as before.

### Two-way Telegram
- Polls `getUpdates` every `InpTgPollSeconds` (5 s, short poll, `InpTgPollTimeoutMs` 3000 ms) and keeps the `update_id` offset in `MQL5/Files/GoldAI_<magic>_tg_offset.txt`.
- Only chat id `InpTgAllowedChatId` (730711407) is obeyed; everything else is ignored. Commands sent before the EA started are ignored.
- `/status`, `/pause`, `/resume` (pause persists in the terminal global variable `GoldAI_<magic>_paused`), `/closeall` (EA magic only, needs `/confirm <4-digit code>` within `InpTgConfirmSeconds`), `/help`.
- Same host as alerts (`https://api.telegram.org`), so no new WebRequest URL. The token stays only in the box `.set`/inputs.
- Do not run any other `getUpdates` poller or webhook on the same bot, or Telegram returns HTTP 409.

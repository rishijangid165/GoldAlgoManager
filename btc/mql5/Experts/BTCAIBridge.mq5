//+------------------------------------------------------------------+
//| BTCAIBridge.mq5  (BTC fork of GoldAIBridge v1.04)                |
//| AI-directed BTCUSD EA for MetaTrader 5.                          |
//|                                                                  |
//| The assistant researches BTC and writes a JSON decision file.    |
//| This EA polls that file and will only open a trade when price    |
//| is inside the AI entry zone. Hard risk limits stay locked here.  |
//|                                                                  |
//| Demo only by default. WebRequest must be allowed for the URL     |
//| (Tools > Options > Expert Advisors). See README.md.              |
//+------------------------------------------------------------------+
#property copyright   "BTC Algo / Rishi Jangid"
#property version     "1.00"
#property description "AI-directed BTCUSD EA (fork of GoldAIBridge v1.04). Trades only inside the AI zone."
#property description "BTC: symbol auto-detect, ATR(H1) SL-width limits, spread cap, weekend/maintenance gap rule."
#property description "DEMO only unless AllowLiveAccount=true. Hard SL on every order. Telegram prefixed [BTC]."

#include <Trade\Trade.mqh>
#include <BTCAIDecision.mqh>
#include <BTCAIJournal.mqh>
#include <BTCAITelegram.mqh>
#include <BTCAINews.mqh>
#include <BTCAIPropGuard.mqh>

//+------------------------------------------------------------------+
//| Inputs                                                             |
//+------------------------------------------------------------------+
input group "Connection"
input string InpDecisionURL     = "https://raw.githubusercontent.com/rishijangid165/GoldAlgoManager/main/btc/decisions/current.json"; // BTC decision file in GoldAlgoManager repo (btc/ folder)
input int    InpPollMinutes     = 5;                 // Poll interval in minutes (min 1)
input int    InpWebTimeoutMs    = 8000;              // HTTP timeout (milliseconds)
input bool   InpUseLocalFile    = false;             // Read from MQL5/Files instead of the URL
input string InpLocalFileName   = "current.json";    // Local filename inside MQL5/Files

input group "Symbol"
input string InpTradeSymbol     = "BTCUSD";          // Broker symbol to trade; auto-detects variants (BTCUSDm, BTCUSD., XBTUSD...) if not found
input string InpExpectedSymbol  = "BTCUSD";          // Logical symbol in the decision file

input group "Risk (locked in the EA)"
input double InpRiskPercentPerTrade = 0.50;          // Max % of equity risked per trade
input double InpMaxDailyLossPct     = 2.00;          // Stop new trades after this daily equity drop
input int    InpMaxOpenTrades       = 1;             // Max open BTCAI positions on this symbol
input int    InpMaxSpreadPoints     = 3000;          // Skip NEW entries if spread (points) is wider (0 = off). 3000 pts = $30 on a 2-digit BTCUSD
input double InpMaxSpreadPrice      = 30.0;          // Also skip if spread in PRICE units ($) is wider (0 = off); digit-independent
input int    InpMinConfidence       = 60;            // Ignore decisions below this confidence
input long   InpMagicNumber         = 26111601;      // Magic number for this EA's orders
input int    InpSlippagePoints      = 1000;            // Max deviation for market orders (points)

input group "Safety"
input bool   InpAllowLiveAccount    = false;         // Allow a NON-demo (REAL/CONTEST) account. Prop/live use must set this deliberately
input string InpAllowedServers      = "";            // Optional: only trade if server name contains one of these (; separated), e.g. FTMO

input group "Prop-firm guard (v1.04)"
input bool                 InpPropGuardEnabled      = false;           // Master switch (OFF on the demo preset, ON in prop presets)
input double               InpPropInitialBalance    = 0.0;             // Firm account size; 0 = capture balance at first attach (persisted)
input double               InpPropFirmDailyLossPct  = 5.0;             // Firm hard daily loss % (reference only)
input double               InpPropDailyLossPct      = 4.0;             // GUARD: block entries + flatten at this daily loss % (0 = off)
input bool                 InpPropDailyPctOfInitial = true;            // Daily % is of the initial balance (FTMO); false = of the day-start base
input ENUM_BTCAI_DAY_BASE InpPropDayBase           = BTCAI_BASE_MAX; // Day-start reference: balance, equity or the higher of both
input ENUM_BTCAI_RESET_TZ InpPropResetTz           = BTCAI_TZ_SERVER;// Time zone of the daily reset (FTMO = CE(S)T)
input int                  InpPropResetHour         = 0;               // Daily reset hour in that zone (0 = midnight)
input double               InpPropFirmMaxDDPct      = 10.0;            // Firm max overall loss % (reference only)
input double               InpPropMaxDDPct          = 8.0;             // GUARD: block + flatten when equity <= initial - this % (0 = off)
input bool                 InpPropDDTrailing        = false;           // Trailing DD: floor follows the equity/balance high-water mark
input bool                 InpPropDDTrailLock       = true;            // Trailing floor never rises above the initial balance
input int                  InpPropMaxOpenPositions  = 1;               // Max open EA positions on ALL symbols (0 = no extra cap)
input double               InpPropDailyProfitCapPct = 0.0;             // Block new entries after this daily gain % (E8 Pro 2%; 0 = off)
input bool                 InpPropProfitCapFlatten  = false;           // Also close EA positions when the profit cap is hit
input bool                 InpPropFlattenOnTrip     = true;            // Close EA positions + delete EA pending when a loss guard trips
input bool                 InpPropFlattenManual     = false;           // On a loss trip also close magic-0 manual positions (account-wide)
input double               InpPropHeadroomMult      = 1.25;            // New trade must fit: risk x this <= remaining daily and DD room
input double               InpPropWarnFraction      = 0.75;            // Telegram warning once this share of an allowance is used (0 = off)
input bool                 InpPropResetDDLatch      = false;           // Set true ONCE to clear a tripped DD latch, then back to false

input group "Prop news mode (v1.04)"
input bool   InpPropNewsFlatEnabled   = false;  // Be FLAT around listed news: close EA trades before, no entries until after
input int    InpPropNewsFlatBeforeMin = 10;     // Close EA positions / delete EA pending this many minutes before the release
input int    InpPropNewsFlatAfterMin  = 5;      // Stay flat (no entries) this many minutes after the release
input bool   InpPropNewsFlatManual    = false;  // Also close magic-0 manual positions before the news

input group "Trade management"
input double InpTP1CloseFraction    = 0.50;          // Fraction to close at TP1 (then SL -> breakeven)
input int    InpBreakevenOffsetPoints = 0;           // Extra points beyond entry for the BE stop
input bool   InpCloseOnBiasFlip     = true;          // Close if a new decision flips bias or goes NONE
input bool   InpCloseOnKillSwitch   = true;          // Close if the file raises kill_switch

input group "Stop-loss width (ATR, BTC)"
input bool             InpSlAtrCheckEnabled = true;       // Reject decisions whose SL distance is outside the ATR band
input ENUM_TIMEFRAMES  InpSlAtrTF           = PERIOD_H1;  // ATR timeframe
input int              InpSlAtrPeriod       = 14;         // ATR period
input double           InpSlAtrMinMult      = 0.5;        // Min SL distance = this x ATR (too tight -> skip)
input double           InpSlAtrMaxMult      = 4.0;        // Max SL distance = this x ATR (too wide -> skip)

input group "Weekend / maintenance gaps (BTC)"
input bool   InpGapNoEntries          = true;   // No new entries while the broker session is closed (weekend/maintenance)
input int    InpGapNoEntryLeadMin     = 30;     // ...nor this many minutes before a session gap starts
input int    InpGapMinMinutes         = 15;     // A break between sessions counts as a gap if at least this long
input int    InpMaxTickAgeSec         = 300;    // Also treat the market as closed if the last tick is older than this (0 = off)
input bool   InpWeekendFlattenEnabled = false;  // Flatten BTCAI trades before a LONG gap (weekend). Default OFF: BTC trades 24/7
input int    InpWeekendFlattenMinHours = 6;     // Only gaps at least this long trigger the flatten
input int    InpWeekendFlattenLeadMin = 30;     // Flatten this many minutes before that gap starts
input bool   InpWeekendFlattenManual  = false;  // Also flatten magic-0 manual positions/orders on this symbol

input group "Trailing after TP1"
input bool             InpTrailEnabled        = false;    // Trail the remaining half after TP1 + breakeven
input bool             InpTrailUseSwing       = true;     // Trail behind the last closed M15 swing high/low
input bool             InpTrailUseATR         = true;     // Also consider ATR(period) * multiplier
input ENUM_TIMEFRAMES  InpTrailTF             = PERIOD_M15; // Timeframe for swing and ATR
input int              InpTrailSwingBars      = 2;        // Bars on each side to confirm a swing
input int              InpTrailATRPeriod      = 14;       // ATR period
input double           InpTrailATRMult        = 1.0;      // ATR multiplier
input int              InpTrailMinStepPoints  = 20;       // Ignore a trail tighter than this (points)
input int              InpTrailTelegramMinSec = 300;      // Min seconds between trail Telegram alerts

input group "Journal"
input string InpJournalFile         = "BTCAI_journal.csv";  // Written under MQL5/Files

input group "Telegram"
input bool   InpEnableTelegram      = true;              // EnableTelegram (no-op until token + chat id are set; use a SEPARATE bot from gold)
input string InpTelegramToken       = "";                // TelegramToken (never share this)
input string InpTelegramChatId      = "";                // TelegramChatId

input group "News blackout (v1.03)"
input bool   InpNewsBlackoutEnabled   = true;            // Block NEW entries around high-impact USD news
input int    InpNewsBlackoutBeforeMin = 30;              // Minutes before the release
input int    InpNewsBlackoutAfterMin  = 90;              // Minutes after the release
input bool   InpNewsUseCalendar       = true;            // Use the MT5 built-in Economic Calendar (USD)
input string InpNewsKeywords          = "Nonfarm Payrolls;Unemployment Rate;Average Hourly Earnings;CPI;PCE;GDP;PPI;Retail Sales;Fed Interest Rate Decision;FOMC Minutes;FOMC Meeting Minutes;FOMC Press Conference;FOMC Statement;FOMC Economic Projections;Fed Chair"; // Calendar event-name keywords (; or , separated)
input int    InpNewsMinImportance     = 2;               // Keyword match needs importance >= this (1 low, 2 moderate, 3 high)
input bool   InpNewsAllHighUSD        = false;           // Also block on EVERY USD HIGH calendar event
input bool   InpNewsUseFile           = true;            // Also use the static list (news.json via WebRequest)
input string InpNewsURL               = "https://raw.githubusercontent.com/rishijangid165/GoldAlgoManager/main/decisions/news.json"; // Static USD macro news list (shared, read-only; same FOMC/CPI/NFP events as gold)
input int    InpNewsRefreshMinutes    = 30;              // Re-read calendar and news.json every N minutes (min 5)
input int    InpNewsLookaheadDays     = 21;              // Calendar look-ahead window (days)
input int    InpNewsAlertMinMinutes   = 30;              // Min minutes between news-block Telegram alerts

input group "Telegram commands (v1.03)"
input bool   InpTgCommandsEnabled     = true;            // Poll getUpdates for /status /pause /resume /closeall /help
input string InpTgAllowedChatId       = "730711407";     // ONLY this chat id may command the EA
input int    InpTgPollSeconds         = 5;               // getUpdates poll interval (seconds, min 2)
input int    InpTgPollTimeoutMs       = 3000;            // HTTP timeout for getUpdates (ms)
input int    InpTgConfirmSeconds      = 60;              // /closeall confirmation window (seconds)

//+------------------------------------------------------------------+
//| State                                                              |
//+------------------------------------------------------------------+
CTrade          g_trade;
string          g_sym                = "";   // resolved broker symbol (BTCUSD or a variant)
int             g_digits             = 2;
int             g_sl_atr_handle      = INVALID_HANDLE;
string          g_gap_status         = "";
datetime        g_gap_flat_key       = 0;
int             g_week_from[];
int             g_week_to[];
datetime        g_week_built         = 0;
CBTCAIJournal  g_journal;
BTCAIDecision  g_decision;

bool            g_have_decision      = false;
bool            g_trade_locked       = false;
string          g_lock_reason        = "";
string          g_poll_status        = "not polled yet";
int             g_last_http          = 0;
datetime        g_last_poll          = 0;
string          g_last_fingerprint   = "";
string          g_status             = "starting";
string          g_last_reject        = "";
string          g_pending_exit_reason = "";
datetime        g_last_panel         = 0;
bool            g_first_timer        = true;
datetime        g_last_trail_notify  = 0;
double          g_last_trail_sl      = 0.0;
int             g_atr_handle         = INVALID_HANDLE;
int             g_atr_period         = 0;
ENUM_TIMEFRAMES g_atr_tf             = PERIOD_CURRENT;
string          g_last_tg_key        = "";
string          g_tg_decision_fp     = "";

datetime        g_day_start          = 0;
double          g_day_start_equity   = 0.0;
ulong           g_tp1_done_ticket    = 0;

// v1.03 news blackout state
BTCAINewsEvent g_news_cal[];
BTCAINewsEvent g_news_file[];
BTCAINewsEvent g_news[];
datetime        g_news_cal_at        = 0;
datetime        g_news_file_at       = 0;
string          g_news_cal_status    = "not loaded";
string          g_news_file_status   = "not loaded";
string          g_news_alert_key     = "";
datetime        g_news_alert_at      = 0;
string          g_news_last_summary  = "";

// v1.04 prop guard state (mirrored in login-scoped global variables)
double          g_pg_initial         = 0.0;
double          g_pg_peak            = 0.0;
datetime        g_pg_day             = 0;
double          g_pg_day_balance     = 0.0;
double          g_pg_day_equity      = 0.0;
bool            g_pg_dd_latched      = false;
datetime        g_pg_daily_trip_day  = 0;
datetime        g_pg_profit_cap_day  = 0;
datetime        g_pg_warn_day        = 0;
int             g_pg_flags           = 0;
string          g_pg_status          = "off";
string          g_pnews_key          = "";
string          g_pnews_status       = "";
bool            g_live_warned        = false;

// v1.03 Telegram command state
bool            g_paused             = false;
long            g_tg_offset          = 0;
datetime        g_tg_last_poll       = 0;
datetime        g_start_gmt          = 0;
string          g_tg_last_err        = "";
datetime        g_tg_last_err_at     = 0;
string          g_confirm_code       = "";
datetime        g_confirm_until      = 0;
datetime        g_last_manage        = 0;

//+------------------------------------------------------------------+
string GvDayStartName()
  {
   return("BTCAI_" + IntegerToString(InpMagicNumber) + "_day");
  }

string GvDayEquityName()
  {
   return("BTCAI_" + IntegerToString(InpMagicNumber) + "_eq");
  }

string GvTp1Name()
  {
   return("BTCAI_" + IntegerToString(InpMagicNumber) + "_tp1");
  }

//+------------------------------------------------------------------+
string BTCAI_Truncate(const string text, const int max_chars)
  {
   if(max_chars <= 3 || StringLen(text) <= max_chars)
      return(text);
   return(StringSubstr(text, 0, max_chars - 3) + "...");
  }

//+------------------------------------------------------------------+
//| Journal a one-shot status event, skipping exact duplicates.      |
//+------------------------------------------------------------------+
void LogUnique(const string event, const string details)
  {
   const string key = event + "|" + details;
   if(key == g_last_reject)
      return;
   g_last_reject = key;
   Print("BTCAI ", event, ": ", details);
   g_journal.Write(event,
                   0,
                   g_sym,
                   (g_have_decision ? g_decision.bias_text : ""),
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   (g_have_decision ? g_decision.confidence : 0),
                   (g_have_decision ? g_decision.generated_at : 0),
                   (g_have_decision ? g_decision.rationale : ""),
                   details);
  }


//+------------------------------------------------------------------+
string TgFpFileName()
  {
   return("BTCAI_" + IntegerToString(InpMagicNumber) + "_tg_fp.txt");
  }

//+------------------------------------------------------------------+
void LoadTelegramState()
  {
   g_tg_decision_fp = "";
   const int h = FileOpen(TgFpFileName(), FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   g_tg_decision_fp = FileReadString(h);
   FileClose(h);
  }

//+------------------------------------------------------------------+
void SaveTelegramDecisionFp(const string fp)
  {
   g_tg_decision_fp = fp;
   const int h = FileOpen(TgFpFileName(), FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
     {
      Print("BTCAI telegram: could not save decision fingerprint");
      return;
     }
   FileWriteString(h, fp);
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Send a Telegram message. Failures are logged only; never block.  |
//+------------------------------------------------------------------+
bool NotifyTelegram(const string text)
  {
   int status = 0;
   string err = "";
   const bool ok = BTCAI_TelegramSend(InpEnableTelegram,
                                       InpTelegramToken,
                                       InpTelegramChatId,
                                       InpWebTimeoutMs,
                                       text,
                                       status,
                                       err);
   if(ok)
     {
      Print("BTCAI telegram sent, WebRequest HTTP ", status);
      return(true);
     }
   if(err == "telegram disabled" || err == "telegram token or chat id is empty")
     {
      // Quiet when the feature is off or not configured.
      return(false);
     }
   Print("BTCAI telegram failed: ", err, " (WebRequest HTTP ", status, ")");
   return(false);
  }

//+------------------------------------------------------------------+
void NotifyTelegramOnce(const string key, const string text)
  {
   if(key != "" && key == g_last_tg_key)
      return;
   NotifyTelegram(text);
   if(key != "")
      g_last_tg_key = key; // remember even on failure so a tick loop cannot spam
  }

//+------------------------------------------------------------------+
void LoadPersistedState()
  {
   if(GlobalVariableCheck(GvDayStartName()) && GlobalVariableCheck(GvDayEquityName()))
     {
      g_day_start        = (datetime)GlobalVariableGet(GvDayStartName());
      g_day_start_equity = GlobalVariableGet(GvDayEquityName());
     }
   if(GlobalVariableCheck(GvTp1Name()))
      g_tp1_done_ticket = (ulong)GlobalVariableGet(GvTp1Name());
  }

//+------------------------------------------------------------------+
void PersistDayState()
  {
   GlobalVariableSet(GvDayStartName(), (double)g_day_start);
   GlobalVariableSet(GvDayEquityName(), g_day_start_equity);
  }

//+------------------------------------------------------------------+
void PersistTp1(const ulong ticket)
  {
   g_tp1_done_ticket = ticket;
   GlobalVariableSet(GvTp1Name(), (double)ticket);
  }

//+------------------------------------------------------------------+
void RefreshDailyWindow()
  {
   MqlDateTime st;
   TimeToStruct(TimeCurrent(), st);
   st.hour = 0;
   st.min  = 0;
   st.sec  = 0;
   const datetime start = StructToTime(st);
   if(g_day_start != start)
     {
      g_day_start        = start;
      g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      PersistDayState();
      Print("BTCAI new trading day (server). Start equity=",
            DoubleToString(g_day_start_equity, 2));
     }
  }

//+------------------------------------------------------------------+
double DailyLossPct()
  {
   if(g_day_start_equity <= 0.0)
      return(0.0);
   const double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   return((g_day_start_equity - eq) / g_day_start_equity * 100.0);
  }

//+------------------------------------------------------------------+
bool DailyLossHit()
  {
   return(DailyLossPct() >= InpMaxDailyLossPct && InpMaxDailyLossPct > 0.0);
  }

//+------------------------------------------------------------------+
bool RealAccountBlocked()
  {
   if(InpAllowLiveAccount)
      return(false);
   return(!BTCAI_IsDemoAccount());
  }

//+------------------------------------------------------------------+
//| v1.04: optional server allow-list (substring, case-insensitive). |
//+------------------------------------------------------------------+
bool ServerBlocked()
  {
   string list = InpAllowedServers;
   StringTrimLeft(list);
   StringTrimRight(list);
   if(list == "")
      return(false);
   string server = AccountInfoString(ACCOUNT_SERVER);
   StringToUpper(server);
   StringReplace(list, ",", ";");
   string parts[];
   const int n = StringSplit(list, ';', parts);
   for(int i = 0; i < n; i++)
     {
      string k = parts[i];
      StringTrimLeft(k);
      StringTrimRight(k);
      StringToUpper(k);
      if(k != "" && StringFind(server, k) >= 0)
         return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
int CountOurPositions()
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != g_sym)
         continue;
      count++;
     }
   return(count);
  }

//+------------------------------------------------------------------+
bool SelectOurPosition(ulong &ticket)
  {
   ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != g_sym)
         continue;
      ticket = t;
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
int OurOpenBias()
  {
   ulong ticket = 0;
   if(!SelectOurPosition(ticket))
      return(BTC_AI_BIAS_NONE);
   const long type = PositionGetInteger(POSITION_TYPE);
   if(type == POSITION_TYPE_BUY)
      return(BTC_AI_BIAS_BUY);
   if(type == POSITION_TYPE_SELL)
      return(BTC_AI_BIAS_SELL);
   return(BTC_AI_BIAS_NONE);
  }

//+------------------------------------------------------------------+
void CloseOurPositions(const string reason)
  {
   g_pending_exit_reason = reason;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != g_sym)
         continue;
      if(!g_trade.PositionClose(ticket))
        {
         Print("BTCAI close failed ticket=", ticket,
               " ret=", g_trade.ResultRetcode(),
               " ", g_trade.ResultRetcodeDescription());
        }
      else
        {
         Print("BTCAI closed ticket=", ticket, " reason=", reason);
         if(g_tp1_done_ticket == ticket)
            PersistTp1(0);
        }
     }
  }

//+------------------------------------------------------------------+
string BuildDecisionUrl()
  {
   string url = InpDecisionURL;
   StringTrimLeft(url);
   StringTrimRight(url);
   const string stamp = IntegerToString((long)TimeGMT());
   if(StringFind(url, "?") >= 0)
      url += "&t=" + stamp;
   else
      url += "?t=" + stamp;
   return(url);
  }

//+------------------------------------------------------------------+
bool ReadLocalDecision(string &body, string &err)
  {
   body = "";
   err  = "";
   const int h = FileOpen(InpLocalFileName, FILE_READ | FILE_BIN);
   if(h == INVALID_HANDLE)
     {
      err = "cannot open MQL5/Files/" + InpLocalFileName + " err=" + IntegerToString(GetLastError());
      return(false);
     }
   const ulong size = FileSize(h);
   if(size == 0)
     {
      FileClose(h);
      err = "local file is empty";
      return(false);
     }
   uchar bytes[];
   ArrayResize(bytes, (int)size);
   const uint got = FileReadArray(h, bytes, 0, (int)size);
   FileClose(h);
   if(got == 0)
     {
      err = "could not read local file";
      return(false);
     }
   body = CharArrayToString(bytes, 0, WHOLE_ARRAY, CP_UTF8);
   return(true);
  }

//+------------------------------------------------------------------+
bool HttpGetDecision(string &body, int &status, string &err)
  {
   body   = "";
   err    = "";
   status = -1;
   char data[];
   char result[];
   string result_headers;
   const string headers = "User-Agent: MetaTrader5-BTCAIBridge/1.00\r\nCache-Control: no-cache\r\n";
   const string url     = BuildDecisionUrl();
   ResetLastError();
   status = WebRequest("GET", url, headers, InpWebTimeoutMs, data, result, result_headers);
   if(status == -1)
     {
      const int le = GetLastError();
      if(le == 4014)
         err = "4014 URL not allowed - add the host in Tools > Options > Expert Advisors > Allow WebRequest";
      else
         err = "WebRequest failed last_error=" + IntegerToString(le);
      return(false);
     }
   body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   if(status != 200)
     {
      err = "HTTP " + IntegerToString(status);
      return(false);
     }
   if(StringLen(JsonStripNoise(body)) < 2)
     {
      err = "empty HTTP body";
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
bool PollDecision()
  {
   string body = "";
   string err  = "";
   int    status = 0;

   if(InpUseLocalFile)
     {
      if(!ReadLocalDecision(body, err))
        {
         g_poll_status = "LOCAL FILE FAIL: " + err;
         g_last_http   = -1;
         g_last_poll   = TimeGMT();
         LogUnique("POLL_ERROR", g_poll_status);
         return(false);
        }
      status = 200;
     }
   else
     {
      if(!HttpGetDecision(body, status, err))
        {
         g_last_http   = status;
         g_poll_status = "HTTP FAIL: " + err;
         g_last_poll   = TimeGMT();
         LogUnique("POLL_ERROR", g_poll_status);
         NotifyTelegramOnce("POLL_ERROR|" + g_poll_status,
                            "BTCAI error: WebRequest failure\n" + g_poll_status);
         return(false);
        }
     }

   g_last_http = status;
   BTCAIDecision fresh;
   if(!BTCAI_DecisionParse(body, fresh))
     {
      g_poll_status = "PARSE FAIL: " + fresh.parse_error;
      g_last_poll   = TimeGMT();
      LogUnique("PARSE_ERROR", g_poll_status);
      return(false);
     }

   const string fp = BTCAI_DecisionFingerprint(fresh);
   const bool changed = (fp != g_last_fingerprint);
   g_decision       = fresh;
   g_have_decision  = true;
   g_last_poll      = TimeGMT();
   g_poll_status    = InpUseLocalFile ? "OK (local file)" : "OK";

   if(changed)
     {
      g_last_fingerprint = fp;
      g_last_reject      = "";
      Print("BTCAI new decision: ", fp, " | ", fresh.rationale);
      g_journal.Write("DECISION",
                      0,
                      fresh.symbol,
                      fresh.bias_text,
                      0.0, 0.0,
                      fresh.stop_loss,
                      fresh.tp1,
                      fresh.tp2,
                      0.0,
                      fresh.confidence,
                      fresh.generated_at,
                      fresh.rationale,
                      fp);
      if(fp != g_tg_decision_fp)
        {
         string msg = "BTCAI new decision\nBias: " + fresh.bias_text +
                      "\nZone: " + DoubleToString(fresh.zone_low, g_digits) +
                      " - " + DoubleToString(fresh.zone_high, g_digits) +
                      "\nSL: " + DoubleToString(fresh.stop_loss, g_digits) +
                      "  TP1: " + DoubleToString(fresh.tp1, g_digits) +
                      "  TP2: " + DoubleToString(fresh.tp2, g_digits);
         if(fresh.kill_switch)
            msg += "\nKILL SWITCH is ON";
         if(NotifyTelegram(msg))
            SaveTelegramDecisionFp(fp);
        }
     }
   return(true);
  }

//+------------------------------------------------------------------+
double EffectiveRiskPct()
  {
   double risk = InpRiskPercentPerTrade;
   if(g_have_decision && g_decision.max_risk_pct > 0.0 && g_decision.max_risk_pct < risk)
      risk = g_decision.max_risk_pct;
   return(risk);
  }


//+------------------------------------------------------------------+
//| Helpers                                                            |
//+------------------------------------------------------------------+
datetime DayStartOf(const datetime t)
  {
   MqlDateTime st;
   TimeToStruct(t, st);
   st.hour = 0;
   st.min  = 0;
   st.sec  = 0;
   return(StructToTime(st));
  }

//+------------------------------------------------------------------+
int ClosePositionsByMagicFilter(const bool include_manual, const string reason)
  {
   int closed = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != g_sym)
         continue;
      const long magic = PositionGetInteger(POSITION_MAGIC);
      const bool ours = (magic == InpMagicNumber);
      const bool manual = (include_manual && magic == 0);
      if(!ours && !manual)
         continue;
      if(ours)
         g_pending_exit_reason = reason;
      if(!g_trade.PositionClose(ticket))
        {
         Print("BTCAI close failed ticket=", ticket,
               " ret=", g_trade.ResultRetcode(),
               " ", g_trade.ResultRetcodeDescription());
        }
      else
        {
         closed++;
         Print("BTCAI closed ticket=", ticket, " magic=", magic, " reason=", reason);
         if(ours && g_tp1_done_ticket == ticket)
            PersistTp1(0);
        }
     }
   return(closed);
  }

//+------------------------------------------------------------------+
int DeletePendingByMagicFilter(const bool include_manual)
  {
   int removed = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != g_sym)
         continue;
      const long magic = OrderGetInteger(ORDER_MAGIC);
      const bool ours = (magic == InpMagicNumber);
      const bool manual = (include_manual && magic == 0);
      if(!ours && !manual)
         continue;
      if(!g_trade.OrderDelete(ticket))
         Print("BTCAI pending-delete failed ticket=", ticket,
               " ", g_trade.ResultRetcodeDescription());
      else
        {
         removed++;
         Print("BTCAI deleted pending ticket=", ticket, " magic=", magic);
        }
     }
   return(removed);
  }

//+------------------------------------------------------------------+
//| BTC symbol resolution                                              |
//+------------------------------------------------------------------+
bool SymbolExistsSel(const string name)
  {
   bool custom = false;
   if(name == "" || !SymbolExist(name, custom))
      return(false);
   return(SymbolSelect(name, true) || SymbolInfoInteger(name, SYMBOL_SELECT) != 0);
  }

//+------------------------------------------------------------------+
//| Reject ETFs / stocks that merely carry "BTC" in their name (e.g.  |
//| MetaQuotes-Demo "BTC" = Grayscale Bitcoin Mini Trust).            |
//+------------------------------------------------------------------+
bool LooksLikeSpotBtc(const string name)
  {
   string path = SymbolInfoString(name, SYMBOL_PATH);
   StringToUpper(path);
   if(StringFind(path, "ETF") >= 0 || StringFind(path, "STOCK") >= 0 ||
      StringFind(path, "SHARE") >= 0 || StringFind(path, "NASDAQ") >= 0 ||
      StringFind(path, "NYSE") >= 0)
      return(false);
   string base = SymbolInfoString(name, SYMBOL_CURRENCY_BASE);
   StringToUpper(base);
   if(base != "BTC" && base != "XBT")
      Print("BTCAI note: ", name, " base currency is '", base, "' (path ", path, "); accepted by name.");
   return(true);
  }

//+------------------------------------------------------------------+
//| Use InpTradeSymbol if it exists; else the chart symbol if it is  |
//| BTC; else scan the broker list for a BTCUSD variant.              |
//+------------------------------------------------------------------+
string ResolveTradeSymbol()
  {
   string want = InpTradeSymbol;
   StringTrimLeft(want);
   StringTrimRight(want);
   if(want == "")
      want = "BTCUSD";
   if(SymbolExistsSel(want) && LooksLikeSpotBtc(want))
      return(want);
   if(BTCAI_SymbolsMatch(want, _Symbol) && LooksLikeSpotBtc(_Symbol))
      return(_Symbol);
   string best = "";
   const int total = SymbolsTotal(false);
   for(int i = 0; i < total; i++)
     {
      const string name = SymbolName(i, false);
      if(!BTCAI_SymbolsMatch(want, name) || !LooksLikeSpotBtc(name))
         continue;
      // prefer the shortest name (BTCUSD. over BTCUSD.pro etc.)
      if(best == "" || StringLen(name) < StringLen(best))
         best = name;
     }
   if(best != "" && SymbolExistsSel(best))
      return(best);
   return("");
  }

//+------------------------------------------------------------------+
//| Weekend / maintenance gap rule (replaces the gold Friday close)  |
//| Uses the broker trade-session table (server time), merged over   |
//| three weeks so wrap-around and 24/7 sessions are handled.        |
//+------------------------------------------------------------------+
#define BTCAI_WEEK 604800

void BuildWeekSessions()
  {
   ArrayResize(g_week_from, 0);
   ArrayResize(g_week_to, 0);
   int f[];
   int t[];
   int n = 0;
   for(int d = 0; d < 7; d++)
     {
      for(uint i = 0; i < 10; i++)
        {
         datetime from = 0, to = 0;
         if(!SymbolInfoSessionTrade(g_sym, (ENUM_DAY_OF_WEEK)d, i, from, to))
            break;
         int fs = (int)from;
         int ts = (int)to;
         if(ts <= fs)
            ts = 86400;
         if(ts > 86400)
            ts = 86400;
         for(int w = 0; w < 3; w++)
           {
            ArrayResize(f, n + 1);
            ArrayResize(t, n + 1);
            f[n] = w * BTCAI_WEEK + d * 86400 + fs;
            t[n] = w * BTCAI_WEEK + d * 86400 + ts;
            n++;
           }
        }
     }
   // insertion sort by start
   for(int i = 1; i < n; i++)
     {
      const int kf = f[i], kt = t[i];
      int j = i - 1;
      while(j >= 0 && f[j] > kf)
        {
         f[j + 1] = f[j];
         t[j + 1] = t[j];
         j--;
        }
      f[j + 1] = kf;
      t[j + 1] = kt;
     }
   // merge touching / overlapping
   int m = 0;
   for(int i = 0; i < n; i++)
     {
      if(m > 0 && f[i] <= g_week_to[m - 1])
        {
         if(t[i] > g_week_to[m - 1])
            g_week_to[m - 1] = t[i];
         continue;
        }
      ArrayResize(g_week_from, m + 1);
      ArrayResize(g_week_to, m + 1);
      g_week_from[m] = f[i];
      g_week_to[m]   = t[i];
      m++;
     }
   g_week_built = TimeCurrent();
  }

//+------------------------------------------------------------------+
//| in_session: inside a session now. secs_to_end: seconds until the  |
//| current session ends (-1 = no end within 2 weeks, i.e. 24/7).    |
//| gap_len: length of the break that follows. secs_to_open: when    |
//| closed, seconds until the next session opens.                     |
//+------------------------------------------------------------------+
void SessionState(bool &in_session, int &secs_to_end, int &gap_len, int &secs_to_open)
  {
   in_session = true;
   secs_to_end = -1;
   gap_len = 0;
   secs_to_open = 0;
   if(g_week_built == 0 || TimeCurrent() - g_week_built > 3600)
      BuildWeekSessions();
   const int n = ArraySize(g_week_from);
   if(n == 0)
      return; // broker publishes no session table: assume open, tick-age check still applies
   MqlDateTime st;
   TimeToStruct(TimeCurrent(), st);
   const int now = BTCAI_WEEK + st.day_of_week * 86400 + st.hour * 3600 + st.min * 60 + st.sec;
   for(int i = 0; i < n; i++)
     {
      if(now >= g_week_from[i] && now < g_week_to[i])
        {
         if(g_week_to[i] - now > BTCAI_WEEK)
            return; // continuous (24/7)
         secs_to_end = g_week_to[i] - now;
         gap_len = (i + 1 < n ? g_week_from[i + 1] - g_week_to[i] : 0);
         return;
        }
      if(g_week_from[i] > now)
        {
         in_session = false;
         secs_to_open = g_week_from[i] - now;
         return;
        }
     }
   in_session = false;
  }

//+------------------------------------------------------------------+
bool TickTooOld(int &age)
  {
   age = 0;
   if(InpMaxTickAgeSec <= 0)
      return(false);
   MqlTick tk;
   if(!SymbolInfoTick(g_sym, tk) || tk.time == 0)
      return(true);
   age = (int)(TimeTradeServer() - tk.time);
   return(age > InpMaxTickAgeSec);
  }

//+------------------------------------------------------------------+
bool GapEntriesBlocked()
  {
   if(!InpGapNoEntries)
      return(false);
   bool in_s = true;
   int to_end = -1, gap = 0, to_open = 0;
   SessionState(in_s, to_end, gap, to_open);
   if(!in_s)
      return(true);
   int age = 0;
   if(TickTooOld(age))
      return(true);
   const int lead = (InpGapNoEntryLeadMin < 0 ? 0 : InpGapNoEntryLeadMin) * 60;
   if(to_end >= 0 && gap >= InpGapMinMinutes * 60 && to_end <= lead)
      return(true);
   return(false);
  }

//+------------------------------------------------------------------+
void ManageWeekendGap()
  {
   bool in_s = true;
   int to_end = -1, gap = 0, to_open = 0;
   SessionState(in_s, to_end, gap, to_open);
   int age = 0;
   const bool stale = TickTooOld(age);
   if(!in_s)
      g_gap_status = "session CLOSED, opens in " + IntegerToString(to_open / 60) + " min";
   else if(to_end < 0)
      g_gap_status = "24/7 session";
   else
      g_gap_status = "session ends in " + IntegerToString(to_end / 60) + " min (gap " +
                     IntegerToString(gap / 60) + " min)";
   if(stale)
      g_gap_status += " | last tick " + IntegerToString(age) + "s old";
   if(GapEntriesBlocked())
      g_gap_status += " | entries blocked";

   if(!InpWeekendFlattenEnabled || !in_s || to_end < 0)
      return;
   if(gap < InpWeekendFlattenMinHours * 3600)
      return;
   if(to_end > (InpWeekendFlattenLeadMin < 0 ? 0 : InpWeekendFlattenLeadMin) * 60)
      return;
   const datetime key = (datetime)(((long)TimeCurrent() + to_end) / 60 * 60);
   if(g_gap_flat_key == key)
      return;
   g_gap_flat_key = key;

   const int closed  = ClosePositionsByMagicFilter(InpWeekendFlattenManual, "weekend_gap_flatten");
   const int deleted = DeletePendingByMagicFilter(InpWeekendFlattenManual);
   g_gap_status += " | flattened " + IntegerToString(closed) + " pos, " + IntegerToString(deleted) + " pending";
   g_journal.Write("WEEKEND_FLATTEN", 0, g_sym, "", 0, 0, 0, 0, 0, 0, 0, 0, "",
                   "gap " + IntegerToString(gap / 60) + " min; closed " + IntegerToString(closed) +
                   ", deleted " + IntegerToString(deleted) + "; manual=" + (InpWeekendFlattenManual ? "yes" : "no"));
   Print("BTCAI ", g_gap_status);
   if(closed > 0 || deleted > 0)
      NotifyTelegramOnce("WEEKEND|" + TimeToString(key),
                         "BTCAI weekend-gap flatten\nClosed positions: " + IntegerToString(closed) +
                         "\nDeleted pending: " + IntegerToString(deleted) +
                         "\nGap length: " + IntegerToString(gap / 3600) + " h");
  }

//+------------------------------------------------------------------+
//| ATR(H1) band for the SL distance (replaces gold dollar limits)    |
//+------------------------------------------------------------------+
double SlAtrValue()
  {
   if(g_sl_atr_handle == INVALID_HANDLE)
      g_sl_atr_handle = iATR(g_sym, InpSlAtrTF, (InpSlAtrPeriod < 1 ? 14 : InpSlAtrPeriod));
   if(g_sl_atr_handle == INVALID_HANDLE)
      return(0.0);
   double buf[];
   if(CopyBuffer(g_sl_atr_handle, 0, 1, 1, buf) != 1)
      return(0.0);
   return(buf[0]);
  }

//+------------------------------------------------------------------+
double LastClosedSwing(const bool want_high)
  {
   const int side = (InpTrailSwingBars < 1 ? 1 : InpTrailSwingBars);
   const int need = side * 2 + 8;
   double buf[];
   ArraySetAsSeries(buf, true);
   const int copied = (want_high
                       ? CopyHigh(g_sym, InpTrailTF, 1, need, buf)
                       : CopyLow(g_sym, InpTrailTF, 1, need, buf));
   if(copied < side * 2 + 1)
      return(0.0);
   // buf[0] is the most recently closed bar (copy started at shift 1).
   for(int i = side; i <= copied - 1 - side; i++)
     {
      bool is_swing = true;
      for(int k = 1; k <= side; k++)
        {
         if(want_high)
           {
            if(!(buf[i] >= buf[i - k] && buf[i] > buf[i + k]))
              {
               is_swing = false;
               break;
              }
           }
         else
           {
            if(!(buf[i] <= buf[i - k] && buf[i] < buf[i + k]))
              {
               is_swing = false;
               break;
              }
           }
        }
      if(is_swing)
         return(buf[i]);
     }
   return(0.0);
  }

//+------------------------------------------------------------------+
int TrailAtrHandle()
  {
   const int period = (InpTrailATRPeriod < 1 ? 14 : InpTrailATRPeriod);
   if(g_atr_handle != INVALID_HANDLE && g_atr_period == period && g_atr_tf == InpTrailTF)
      return(g_atr_handle);
   if(g_atr_handle != INVALID_HANDLE)
     {
      IndicatorRelease(g_atr_handle);
      g_atr_handle = INVALID_HANDLE;
     }
   g_atr_period = period;
   g_atr_tf     = InpTrailTF;
   g_atr_handle = iATR(g_sym, InpTrailTF, period);
   return(g_atr_handle);
  }

//+------------------------------------------------------------------+
double CurrentATR()
  {
   const int handle = TrailAtrHandle();
   if(handle == INVALID_HANDLE)
      return(0.0);
   double buf[];
   ArraySetAsSeries(buf, true);
   const int copied = CopyBuffer(handle, 0, 1, 3, buf);
   if(copied < 1 || buf[0] <= 0.0)
      return(0.0);
   return(buf[0]);
  }

//+------------------------------------------------------------------+
//| Trail only tightens, only after TP1, and only if the new stop    |
//| stays a valid distance from the current bid/ask (StopsLevel).    |
//+------------------------------------------------------------------+
void TrailOpenPosition(const ulong ticket)
  {
   if(!InpTrailEnabled)
      return;
   if(!InpTrailUseSwing && !InpTrailUseATR)
      return;
   if(!PositionSelectByTicket(ticket))
      return;

   const long   type  = PositionGetInteger(POSITION_TYPE);
   const double sl    = PositionGetDouble(POSITION_SL);
   const double tp    = PositionGetDouble(POSITION_TP);
   const double bid   = SymbolInfoDouble(g_sym, SYMBOL_BID);
   const double ask   = SymbolInfoDouble(g_sym, SYMBOL_ASK);
   const double point = SymbolInfoDouble(g_sym, SYMBOL_POINT);
   if(point <= 0.0 || bid <= 0.0 || ask <= 0.0)
      return;

   const int min_pts = BTCAI_StopsLevelPoints(g_sym);
   const double min_dist = min_pts * point;
   const double step = (InpTrailMinStepPoints < 0 ? 0 : InpTrailMinStepPoints) * point;
   const bool is_buy = (type == POSITION_TYPE_BUY);
   const double market = (is_buy ? bid : ask);

   double candidate = 0.0;
   bool have = false;
   string how = "";

   if(InpTrailUseSwing)
     {
      const double sw = LastClosedSwing(!is_buy); // BUY: last swing low; SELL: last swing high
      if(sw > 0.0)
        {
         candidate = sw;
         have = true;
         how = "swing";
        }
     }
   if(InpTrailUseATR)
     {
      const double atr = CurrentATR();
      if(atr > 0.0)
        {
         const double k = (InpTrailATRMult > 0.0 ? InpTrailATRMult : 1.0);
         const double atr_sl = (is_buy ? bid - atr * k : ask + atr * k);
         if(!have)
           {
            candidate = atr_sl;
            have = true;
            how = "ATR";
           }
         else
           {
            // Both on: use the tighter (more protective) of the two.
            if(is_buy && atr_sl > candidate)
              {
               candidate = atr_sl;
               how = "ATR";
              }
            if(!is_buy && atr_sl < candidate)
              {
               candidate = atr_sl;
               how = "ATR";
              }
            if(how != "ATR" && how != "")
               how = "swing+ATR";
           }
        }
     }
   if(!have || candidate <= 0.0)
      return;

   candidate = BTCAI_NormalizePrice(g_sym, candidate);

   // Must stay on the correct side of the market and respect StopsLevel.
   if(is_buy)
     {
      const double max_sl = BTCAI_NormalizePrice(g_sym, bid - min_dist);
      if(candidate >= bid || (min_dist > 0.0 && candidate > max_sl))
         candidate = max_sl;
      if(candidate >= bid)
         return;
     }
   else
     {
      const double min_sl = BTCAI_NormalizePrice(g_sym, ask + min_dist);
      if(candidate <= ask || (min_dist > 0.0 && candidate < min_sl))
         candidate = min_sl;
      if(candidate <= ask)
         return;
     }

   // Only tighten (never loosen, never pull back through the current SL).
   if(is_buy)
     {
      if(sl != 0.0 && candidate <= sl + 1e-12)
         return;
      if(step > 0.0 && sl != 0.0 && (candidate - sl) < step)
         return;
     }
   else
     {
      if(sl != 0.0 && candidate >= sl - 1e-12)
         return;
      if(step > 0.0 && sl != 0.0 && (sl - candidate) < step)
         return;
     }

   // Re-check a trail stop against current price (not the original entry —
   // a profit-side trail will often sit beyond entry).
   if(MathAbs(market - candidate) < min_dist)
      return;

   if(!g_trade.PositionModify(ticket, candidate, tp))
     {
      Print("BTCAI trail modify failed ticket=", ticket,
            " ", g_trade.ResultRetcodeDescription());
      return;
     }

   g_last_trail_sl = candidate;
   Print("BTCAI trailed SL to ", DoubleToString(candidate, g_digits),
         " (", how, ") on ticket ", ticket);
   g_journal.Write("TRAIL",
                   ticket,
                   g_sym,
                   (is_buy ? "BUY" : "SELL"),
                   PositionGetDouble(POSITION_VOLUME),
                   market,
                   candidate, tp, 0.0,
                   0.0,
                   g_decision.confidence,
                   g_decision.generated_at,
                   g_decision.rationale,
                   "SL trailed after TP1 via " + how);

   const datetime now = TimeCurrent();
   const int gap = (InpTrailTelegramMinSec < 0 ? 0 : InpTrailTelegramMinSec);
   if(gap == 0 || g_last_trail_notify == 0 || (now - g_last_trail_notify) >= gap)
     {
      string msg = "BTCAI trailing stop\n";
      msg += (is_buy ? "BUY" : "SELL") + " ticket " + IntegerToString((long)ticket) + "\n";
      msg += "New SL: " + DoubleToString(candidate, g_digits);
      msg += "  (was " + DoubleToString(sl, g_digits) + ")\n";
      msg += "Method: " + how;
      if(NotifyTelegram(msg))
         g_last_trail_notify = now;
      else
         g_last_trail_notify = now; // still throttle even if send failed, to avoid a burst
     }
  }

//+------------------------------------------------------------------+
//| Handle kill switch and bias flips against an open position.      |
//+------------------------------------------------------------------+
void EnforceDecisionOnOpenTrade()
  {
   if(!g_have_decision || !g_decision.loaded)
      return;
   if(CountOurPositions() <= 0)
      return;

   if(g_decision.kill_switch && InpCloseOnKillSwitch)
     {
      LogUnique("KILL", "kill_switch is true - flattening BTCAI positions");
      NotifyTelegramOnce("KILL", "BTCAI error: kill switch is ON - flattening positions");
      CloseOurPositions("kill_switch");
      return;
     }

   if(!InpCloseOnBiasFlip)
      return;

   const int open_bias = OurOpenBias();
   if(open_bias != BTC_AI_BIAS_NONE && open_bias != g_decision.bias)
     {
      const string details = "open " + BTCAI_BiasText(open_bias) +
                             " vs decision " + g_decision.bias_text;
      LogUnique("BIAS_FLIP", details);
      CloseOurPositions("bias_flip: " + details);
     }
  }

//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   ulong ticket = 0;
   if(!SelectOurPosition(ticket))
      return;

   const long   type  = PositionGetInteger(POSITION_TYPE);
   const double volume = PositionGetDouble(POSITION_VOLUME);
   const double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
   const double sl     = PositionGetDouble(POSITION_SL);
   const double tp     = PositionGetDouble(POSITION_TP);
   const double bid    = SymbolInfoDouble(g_sym, SYMBOL_BID);
   const double ask    = SymbolInfoDouble(g_sym, SYMBOL_ASK);
   const double point  = SymbolInfoDouble(g_sym, SYMBOL_POINT);

   if(ticket == g_tp1_done_ticket)
     {
      TrailOpenPosition(ticket);
      return;
     }
   if(!g_have_decision || !BTCAI_HasPartialTp(g_decision))
      return;

   const double tp1 = BTCAI_NormalizePrice(g_sym, g_decision.tp1);
   bool hit = false;
   if(type == POSITION_TYPE_BUY && bid >= tp1)
      hit = true;
   if(type == POSITION_TYPE_SELL && ask <= tp1)
      hit = true;
   if(!hit)
      return;

   const double vmin = SymbolInfoDouble(g_sym, SYMBOL_VOLUME_MIN);
   double close_vol = BTCAI_NormalizeVolume(g_sym, volume * InpTP1CloseFraction);
   if(close_vol > 0.0 && (volume - close_vol) < vmin - 1e-12)
      close_vol = 0.0; // would leave less than min lot - skip the partial

   if(close_vol > 0.0 && close_vol < volume)
     {
      if(!g_trade.PositionClosePartial(ticket, close_vol))
        {
         Print("BTCAI TP1 partial failed ticket=", ticket,
               " ", g_trade.ResultRetcodeDescription());
         return;
        }
      g_journal.Write("TP1_PARTIAL",
                      ticket,
                      g_sym,
                      (type == POSITION_TYPE_BUY ? "BUY" : "SELL"),
                      close_vol,
                      (type == POSITION_TYPE_BUY ? bid : ask),
                      sl, g_decision.tp1, g_decision.tp2,
                      0.0,
                      g_decision.confidence,
                      g_decision.generated_at,
                      g_decision.rationale,
                      "closed fraction at TP1");
      Print("BTCAI TP1 partial close ", DoubleToString(close_vol, 4), " of ticket ", ticket);
     }

   // Move SL to breakeven (entry +/- optional offset), for the remainder.
   if(point <= 0.0)
     {
      PersistTp1(ticket);
      return;
     }
   double be = entry;
   if(type == POSITION_TYPE_BUY)
      be = entry + InpBreakevenOffsetPoints * point;
   else
      be = entry - InpBreakevenOffsetPoints * point;
   be = BTCAI_NormalizePrice(g_sym, be);

   // Re-select in case the ticket was refreshed after a partial
   if(!PositionSelectByTicket(ticket))
     {
      PersistTp1(ticket);
      return;
     }
   const double cur_sl = PositionGetDouble(POSITION_SL);
   const double cur_tp = PositionGetDouble(POSITION_TP);
   bool should_move = false;
   if(type == POSITION_TYPE_BUY && (cur_sl == 0.0 || be > cur_sl))
      should_move = true;
   if(type == POSITION_TYPE_SELL && (cur_sl == 0.0 || be < cur_sl))
      should_move = true;

   if(should_move)
     {
      string reason = "";
      const ENUM_ORDER_TYPE ot = (type == POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      const double cur_price = (type == POSITION_TYPE_BUY ? bid : ask);
      if(BTCAI_StopsAreValid(g_sym, ot, cur_price, be, cur_tp, reason))
        {
         if(g_trade.PositionModify(ticket, be, cur_tp))
           {
            Print("BTCAI moved SL to breakeven ", DoubleToString(be, g_digits),
                  " on ticket ", ticket);
            g_journal.Write("BE_MOVE",
                            ticket,
                            g_sym,
                            (type == POSITION_TYPE_BUY ? "BUY" : "SELL"),
                            PositionGetDouble(POSITION_VOLUME),
                            cur_price,
                            be, g_decision.tp1, g_decision.tp2,
                            0.0,
                            g_decision.confidence,
                            g_decision.generated_at,
                            g_decision.rationale,
                            "SL moved to breakeven after TP1");
           }
         else
           {
            Print("BTCAI BE modify failed ticket=", ticket,
                  " ", g_trade.ResultRetcodeDescription());
           }
        }
      else
         Print("BTCAI BE skip: ", reason);
     }

   PersistTp1(ticket);

   {
    const string side = (type == POSITION_TYPE_BUY ? "BUY" : "SELL");
    string msg = "BTCAI TP1 partial close + BE\n";
    msg += side + " ticket " + IntegerToString((long)ticket);
    if(close_vol > 0.0 && close_vol < volume)
       msg += "\nClosed: " + DoubleToString(close_vol, 4) + " lots";
    else
       msg += "\nPartial skipped (remainder would be below min lot)";
    msg += "\nSL moved to breakeven " + DoubleToString(be, g_digits);
    NotifyTelegram(msg);
   }
  }

//+------------------------------------------------------------------+
//| Attempt a market entry if every hard rule and the zone pass.     |
//+------------------------------------------------------------------+
void TryOpenTrade()
  {
   if(g_trade_locked)
     {
      g_status = "BLOCKED: " + g_lock_reason;
      return;
     }
   if(RealAccountBlocked())
     {
      g_status = "BLOCKED: non-demo account (AllowLiveAccount is false)";
      LogUnique("REJECT", g_status);
      return;
     }
   if(ServerBlocked())
     {
      g_status = "BLOCKED: server " + AccountInfoString(ACCOUNT_SERVER) + " not in AllowedServers";
      LogUnique("REJECT", g_status);
      return;
     }
   if(g_paused)
     {
      g_status = "PAUSED via Telegram - no new entries (/resume to allow)";
      return;
     }
   string pg_why = "";
   if(PropEntriesBlocked(pg_why))
     {
      g_status = "PROP GUARD: " + pg_why;
      LogUnique("PROP_GUARD_BLOCK", g_status);
      return;
     }
   string pn_why = "";
   int pn_idx = -1;
   if(PropNewsFlatActive(pn_why, pn_idx))
     {
      g_status = "PROP NEWS FLAT: " + pn_why;
      LogUnique("PROP_NEWS_BLOCK", g_status);
      return;
     }
   if(!g_have_decision || !g_decision.loaded)
     {
      g_status = "waiting for a valid decision file";
      return;
     }
   if(g_decision.kill_switch)
     {
      g_status = "KILL SWITCH is on - no new trades";
      return;
     }
   if(GapEntriesBlocked())
     {
      g_status = "MARKET GAP: new entries blocked (" + g_gap_status + ")";
      return;
     }

   const datetime now = TimeGMT();
   if(BTCAI_DecisionIsStale(g_decision, now))
     {
      g_status = "STALE decision (valid_until " + BTCAI_TimeToIsoUtc(g_decision.valid_until) + ")";
      LogUnique("STALE", g_status);
      return;
     }

   string blackout_reason = "";
   if(BTCAI_InBlackout(g_decision, now, blackout_reason))
     {
      g_status = "NEWS BLACKOUT" + (blackout_reason == "" ? "" : (": " + blackout_reason));
      LogUnique("BLACKOUT", g_status);
      return;
     }

   if(DailyLossHit())
     {
      g_status = "BLOCKED: max daily loss reached (" +
                 DoubleToString(DailyLossPct(), 2) + "% / cap " +
                 DoubleToString(InpMaxDailyLossPct, 2) + "%)";
      LogUnique("DAILY_LOSS", g_status);
      NotifyTelegramOnce("DAILY_LOSS", "BTCAI error: daily loss stop\n" + g_status);
      return;
     }

   if(g_decision.bias == BTC_AI_BIAS_NONE)
     {
      g_status = "FLAT (bias NONE) - no trade";
      return;
     }

   if(g_decision.confidence < InpMinConfidence)
     {
      g_status = "LOW CONFIDENCE " + IntegerToString(g_decision.confidence) +
                 " < min " + IntegerToString(InpMinConfidence);
      LogUnique("LOW_CONFIDENCE", g_status);
      return;
     }

   string news_why = "";
   int news_idx = -1;
   if(NewsBlocked(news_why, news_idx))
     {
      g_status = "NEWS AUTO-BLACKOUT: " + news_why;
      LogUnique("NEWS_BLOCK", g_status);
      NotifyNewsBlock(news_idx, news_why);
      return;
     }

   const string expected = (InpExpectedSymbol == "" ? "BTCUSD" : InpExpectedSymbol);
   if(!BTCAI_SymbolsMatch(g_decision.symbol, g_sym) ||
      !BTCAI_SymbolsMatch(expected, g_sym))
     {
      g_status = "SYMBOL MISMATCH file=" + g_decision.symbol +
                 " chart=" + g_sym + " expected=" + expected;
      LogUnique("SYMBOL_MISMATCH", g_status);
      return;
     }

   string geom = "";
   if(!BTCAI_DecisionGeometryOk(g_decision, geom))
     {
      g_status = "BAD GEOMETRY: " + geom;
      LogUnique("REJECT", g_status);
      return;
     }

   if(CountOurPositions() >= InpMaxOpenTrades)
     {
      g_status = "IN TRADE - managing the open position (no new entry)";
      return;
     }

   const int spread = BTCAI_CurrentSpreadPoints(g_sym);
   const double spread_px = SymbolInfoDouble(g_sym, SYMBOL_ASK) - SymbolInfoDouble(g_sym, SYMBOL_BID);
   if(InpMaxSpreadPrice > 0.0 && spread_px > InpMaxSpreadPrice)
     {
      g_status = "SPREAD $" + DoubleToString(spread_px, 2) + " > max $" + DoubleToString(InpMaxSpreadPrice, 2);
      LogUnique("SPREAD", g_status);
      return;
     }
   if(InpMaxSpreadPoints > 0 && spread > InpMaxSpreadPoints)
     {
      g_status = "SPREAD " + IntegerToString(spread) +
                 " > max " + IntegerToString(InpMaxSpreadPoints) + " points";
      LogUnique("SPREAD", g_status);
      return;
     }

   const bool is_buy = (g_decision.bias == BTC_AI_BIAS_BUY);
   const double ask  = SymbolInfoDouble(g_sym, SYMBOL_ASK);
   const double bid  = SymbolInfoDouble(g_sym, SYMBOL_BID);
   const double entry_price = (is_buy ? ask : bid);

   if(!BTCAI_PriceInZone(g_decision, entry_price))
     {
      g_status = "WAITING for price to enter zone " +
                 DoubleToString(g_decision.zone_low, g_digits) + " - " +
                 DoubleToString(g_decision.zone_high, g_digits) +
                 " (now " + DoubleToString(entry_price, g_digits) + ")";
      return;
     }

   const ENUM_ORDER_TYPE otype = (is_buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const double sl = BTCAI_NormalizePrice(g_sym, g_decision.stop_loss);
   const double tp = BTCAI_NormalizePrice(g_sym, BTCAI_OrderTakeProfit(g_decision));

   string reason = "";
   if(!BTCAI_StopsAreValid(g_sym, otype, entry_price, sl, tp, reason))
     {
      g_status = "STOPS REJECTED: " + reason;
      LogUnique("REJECT", g_status);
      return;
     }
   if(sl <= 0.0)
     {
      g_status = "STOPS REJECTED: hard SL is mandatory";
      LogUnique("REJECT", g_status);
      return;
     }
   if(InpSlAtrCheckEnabled)
     {
      const double atr = SlAtrValue();
      if(atr <= 0.0)
        {
         g_status = "ATR(" + IntegerToString(InpSlAtrPeriod) + ") not ready - entry skipped";
         LogUnique("REJECT", g_status);
         return;
        }
      const double sl_dist = MathAbs(entry_price - sl);
      const double lo = atr * InpSlAtrMinMult;
      const double hi = atr * InpSlAtrMaxMult;
      if((InpSlAtrMinMult > 0.0 && sl_dist < lo) || (InpSlAtrMaxMult > 0.0 && sl_dist > hi))
        {
         g_status = "SL WIDTH " + DoubleToString(sl_dist, g_digits) + " outside ATR band " +
                    DoubleToString(lo, g_digits) + " - " + DoubleToString(hi, g_digits) +
                    " (ATR " + DoubleToString(atr, g_digits) + ")";
         LogUnique("REJECT", g_status);
         return;
        }
     }

   const double risk_pct   = EffectiveRiskPct();
   const double risk_money = AccountInfoDouble(ACCOUNT_EQUITY) * risk_pct / 100.0;
   if(InpPropGuardEnabled)
     {
      string fit_why = "";
      if(!BTCAI_PropRiskFits(AccountInfoDouble(ACCOUNT_EQUITY), PropDayBase(), PropDailyAllowance(),
                              PropDDFloor(), risk_money, InpPropHeadroomMult, fit_why))
        {
         g_status = "PROP GUARD: trade would not fit (" + fit_why + ")";
         LogUnique("PROP_GUARD_FIT", g_status);
         return;
        }
     }
   const double lots = BTCAI_LotsForRisk(g_sym, otype, entry_price, sl, risk_money, reason);
   if(lots <= 0.0)
     {
      g_status = "LOT SIZE REJECTED: " + reason;
      LogUnique("REJECT", g_status);
      return;
     }
   if(!BTCAI_EnoughMargin(g_sym, otype, lots, entry_price, reason))
     {
      g_status = "MARGIN REJECTED: " + reason;
      LogUnique("REJECT", g_status);
      return;
     }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints((uint)(InpSlippagePoints < 0 ? 0 : InpSlippagePoints));
   g_trade.SetTypeFillingBySymbol(g_sym);

   const string comment = BTCAI_Truncate("BTCAI|" + g_decision.bias_text, 31);
   bool sent = false;
   if(is_buy)
      sent = g_trade.Buy(lots, g_sym, entry_price, sl, tp, comment);
   else
      sent = g_trade.Sell(lots, g_sym, entry_price, sl, tp, comment);

   if(!sent)
     {
      g_status = "ORDER FAILED: " + g_trade.ResultRetcodeDescription();
      LogUnique("REJECT", g_status);
      return;
     }

   ulong ticket = 0;
   if(!SelectOurPosition(ticket) || ticket == 0)
      ticket = g_trade.ResultDeal();
   if(ticket == 0)
      ticket = g_trade.ResultOrder();
   PersistTp1(0);
   g_status = "OPENED " + g_decision.bias_text + " " + DoubleToString(lots, 4) +
              " @ " + DoubleToString(entry_price, g_digits) + " ticket=" + IntegerToString((long)ticket);
   Print("BTCAI ", g_status);
   NotifyTelegram("BTCAI " + g_decision.bias_text + " opened\nLots: " +
                  DoubleToString(lots, 4) +
                  "\nEntry: " + DoubleToString(entry_price, g_digits) +
                  "\nSL: " + DoubleToString(sl, g_digits) +
                  "\nTP: " + DoubleToString(g_decision.tp1, g_digits) +
                  " / " + DoubleToString(g_decision.tp2, g_digits) +
                  "\nTicket: " + IntegerToString((long)ticket));
   g_journal.Write("ENTRY",
                   ticket,
                   g_sym,
                   g_decision.bias_text,
                   lots,
                   entry_price,
                   sl,
                   g_decision.tp1,
                   g_decision.tp2,
                   0.0,
                   g_decision.confidence,
                   g_decision.generated_at,
                   g_decision.rationale,
                   "market entry inside zone");
  }

//+------------------------------------------------------------------+
//| v1.03 News auto-blackout                                         |
//+------------------------------------------------------------------+
void NewsCopy(BTCAINewsEvent &dst, const BTCAINewsEvent &src)
  {
   dst.event_utc = src.event_utc;
   dst.start_utc = src.start_utc;
   dst.end_utc   = src.end_utc;
   dst.name      = src.name;
   dst.source    = src.source;
  }

//+------------------------------------------------------------------+
void NewsMergeInto(BTCAINewsEvent &dst[], const BTCAINewsEvent &src[])
  {
   for(int i = 0; i < ArraySize(src); i++)
     {
      bool merged = false;
      for(int j = 0; j < ArraySize(dst); j++)
        {
         if(dst[j].event_utc != src[i].event_utc)
            continue;
         if(src[i].start_utc < dst[j].start_utc)
            dst[j].start_utc = src[i].start_utc;
         if(src[i].end_utc > dst[j].end_utc)
            dst[j].end_utc = src[i].end_utc;
         if(StringFind(dst[j].source, src[i].source) < 0)
            dst[j].source += "+" + src[i].source;
         merged = true;
         break;
        }
      if(merged)
         continue;
      const int k = ArraySize(dst);
      if(k >= BTC_AI_MAX_NEWS * 2)
         break;
      ArrayResize(dst, k + 1);
      NewsCopy(dst[k], src[i]);
     }
  }

//+------------------------------------------------------------------+
void NewsRebuild()
  {
   ArrayResize(g_news, 0);
   NewsMergeInto(g_news, g_news_cal);
   NewsMergeInto(g_news, g_news_file);
   const int nx = BTCAI_NewsNext(g_news, TimeGMT());
   const string summary = "cal=" + IntegerToString(ArraySize(g_news_cal)) +
                          " file=" + IntegerToString(ArraySize(g_news_file)) +
                          " merged=" + IntegerToString(ArraySize(g_news)) +
                          (nx >= 0 ? (" next=" + BTCAI_NewsWindowText(g_news[nx])) : " next=none");
   if(summary != g_news_last_summary)
     {
      g_news_last_summary = summary;
      Print("BTCAI news windows: ", summary);
     }
  }

//+------------------------------------------------------------------+
string NewsCacheFileName()
  {
   return("BTCAI_" + IntegerToString(InpMagicNumber) + "_news_cache.json");
  }

//+------------------------------------------------------------------+
bool HttpGetText(const string base_url, const int timeout_ms, string &body, int &status, string &err)
  {
   body = "";
   err  = "";
   string url = base_url;
   StringTrimLeft(url);
   StringTrimRight(url);
   if(url == "")
     {
      err = "empty URL";
      status = -1;
      return(false);
     }
   url += (StringFind(url, "?") >= 0 ? "&t=" : "?t=") + IntegerToString((long)TimeGMT());
   char data[];
   char result[];
   string result_headers;
   const string headers = "User-Agent: MetaTrader5-BTCAIBridge/1.03\r\nCache-Control: no-cache\r\n";
   ResetLastError();
   status = WebRequest("GET", url, headers, timeout_ms, data, result, result_headers);
   if(status == -1)
     {
      const int le = GetLastError();
      err = (le == 4014 ? "4014 URL not allowed (add the host to Allow WebRequest)" :
             "WebRequest failed last_error=" + IntegerToString(le));
      return(false);
     }
   body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   if(status != 200)
     {
      err = "HTTP " + IntegerToString(status);
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
bool ReadTextFile(const string name, string &body)
  {
   body = "";
   const int h = FileOpen(name, FILE_READ | FILE_BIN);
   if(h == INVALID_HANDLE)
      return(false);
   const ulong size = FileSize(h);
   if(size == 0)
     {
      FileClose(h);
      return(false);
     }
   uchar bytes[];
   ArrayResize(bytes, (int)size);
   const uint got = FileReadArray(h, bytes, 0, (int)size);
   FileClose(h);
   if(got == 0)
      return(false);
   body = CharArrayToString(bytes, 0, WHOLE_ARRAY, CP_UTF8);
   return(true);
  }

//+------------------------------------------------------------------+
void WriteTextFile(const string name, const string body)
  {
   const int h = FileOpen(name, FILE_WRITE | FILE_BIN);
   if(h == INVALID_HANDLE)
      return;
   uchar bytes[];
   const int n = StringToCharArray(body, bytes, 0, WHOLE_ARRAY, CP_UTF8);
   if(n > 1)
      FileWriteArray(h, bytes, 0, n - 1);
   FileClose(h);
  }

//+------------------------------------------------------------------+
void RefreshNews(const bool force)
  {
   if(!InpNewsBlackoutEnabled && !InpPropNewsFlatEnabled)
      return;
   const datetime now = TimeGMT();
   const int interval = (InpNewsRefreshMinutes < 5 ? 5 : InpNewsRefreshMinutes) * 60;
   bool changed = false;

   if(InpNewsUseCalendar && (force || g_news_cal_at == 0 || (now - g_news_cal_at) >= interval))
     {
      g_news_cal_at = now;
      BTCAINewsEvent tmp[];
      string err = "";
      const int n = BTCAI_NewsFromCalendar(tmp,
                                            InpNewsKeywords,
                                            InpNewsMinImportance,
                                            InpNewsAllHighUSD,
                                            InpNewsBlackoutBeforeMin,
                                            InpNewsBlackoutAfterMin,
                                            InpNewsLookaheadDays,
                                            err);
      if(n >= 0)
        {
         ArrayResize(g_news_cal, ArraySize(tmp));
         for(int i = 0; i < ArraySize(tmp); i++)
            NewsCopy(g_news_cal[i], tmp[i]);
         g_news_cal_status = "OK " + IntegerToString(ArraySize(g_news_cal)) + " " + g_BTCAI_cal_tz_info;
        }
      else
        {
         // Keep the last good calendar windows; news.json still applies.
         g_news_cal_status = "FAIL (" + err + ")";
         LogUnique("NEWS_CAL_ERROR", g_news_cal_status);
        }
      changed = true;
     }

   if(InpNewsUseFile && (force || g_news_file_at == 0 || (now - g_news_file_at) >= interval))
     {
      g_news_file_at = now;
      string body = "", err = "";
      int status = 0;
      bool from_cache = false;
      bool have = HttpGetText(InpNewsURL, InpWebTimeoutMs, body, status, err);
      if(!have)
        {
         string cached = "";
         if(ReadTextFile(NewsCacheFileName(), cached))
           {
            body = cached;
            have = true;
            from_cache = true;
           }
        }
      if(have)
        {
         BTCAINewsEvent tmp[];
         string perr = "";
         const int n = BTCAI_NewsFromJson(tmp, body, InpNewsBlackoutBeforeMin, InpNewsBlackoutAfterMin, perr);
         if(n >= 0)
           {
            ArrayResize(g_news_file, ArraySize(tmp));
            for(int i = 0; i < ArraySize(tmp); i++)
               NewsCopy(g_news_file[i], tmp[i]);
            if(!from_cache)
               WriteTextFile(NewsCacheFileName(), body);
            g_news_file_status = (from_cache ? "CACHE " : "OK ") + IntegerToString(ArraySize(g_news_file)) +
                                 (from_cache ? (" (fetch " + err + ")") : "");
           }
         else
            g_news_file_status = "PARSE FAIL (" + perr + ")";
        }
      else
         g_news_file_status = "FAIL (" + err + ")";
      if(StringFind(g_news_file_status, "OK") != 0)
         LogUnique("NEWS_FILE_STATUS", g_news_file_status);
      changed = true;
     }

   if(changed)
      NewsRebuild();
  }

//+------------------------------------------------------------------+
bool NewsBlocked(string &why, int &idx)
  {
   why = "";
   idx = -1;
   if(!InpNewsBlackoutEnabled)
      return(false);
   if(!BTCAI_NewsActive(g_news, TimeGMT(), idx))
      return(false);
   why = BTCAI_NewsWindowText(g_news[idx]);
   return(true);
  }

//+------------------------------------------------------------------+
void NotifyNewsBlock(const int idx, const string why)
  {
   const datetime now = TimeGMT();
   const string key = g_last_fingerprint + "|" + (idx >= 0 ? IntegerToString((long)g_news[idx].event_utc) : why);
   if(key == g_news_alert_key)
      return;
   const int min_gap = (InpNewsAlertMinMinutes < 0 ? 0 : InpNewsAlertMinMinutes) * 60;
   if(g_news_alert_at > 0 && (now - g_news_alert_at) < min_gap)
      return;
   g_news_alert_key = key;
   g_news_alert_at  = now;
   NotifyTelegram("BTCAI entry blocked by news\nDecision: " +
                  (g_have_decision ? g_decision.bias_text : "?") +
                  "\nWindow: " + why +
                  "\nOpen positions are not touched.");
  }

//+------------------------------------------------------------------+
string NewsPanelText()
  {
   if(!InpNewsBlackoutEnabled)
      return("off");
   const datetime now = TimeGMT();
   int idx = -1;
   if(BTCAI_NewsActive(g_news, now, idx))
      return("BLOCKING " + BTCAI_NewsWindowText(g_news[idx]));
   const int nx = BTCAI_NewsNext(g_news, now);
   if(nx < 0)
      return("no window loaded");
   return("next " + BTCAI_NewsWindowText(g_news[nx]));
  }

//+------------------------------------------------------------------+
//| v1.04 Prop-firm guard                                            |
//+------------------------------------------------------------------+
string PgName(const string key)
  {
   return("BTCAI_" + IntegerToString(InpMagicNumber) + "_" +
          IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "_pg_" + key);
  }

double PgGet(const string key, const double def)
  {
   const string n = PgName(key);
   if(GlobalVariableCheck(n))
      return(GlobalVariableGet(n));
   return(def);
  }

void PgSet(const string key, const double v)
  {
   GlobalVariableSet(PgName(key), v);
  }

//+------------------------------------------------------------------+
double PropDayBase()
  {
   return(BTCAI_PropDayBase((int)InpPropDayBase, g_pg_day_balance, g_pg_day_equity));
  }

double PropDailyAllowance()
  {
   return(BTCAI_PropDailyAllowance(InpPropDailyLossPct, InpPropDailyPctOfInitial, g_pg_initial, PropDayBase()));
  }

double PropDDFloor()
  {
   return(BTCAI_PropDDFloor(InpPropMaxDDPct, g_pg_initial, g_pg_peak, InpPropDDTrailing, InpPropDDTrailLock));
  }

//+------------------------------------------------------------------+
//| Balance at the day reset, rebuilt from deal history (all deals,  |
//| incl. manual and balance operations) when the EA missed the      |
//| reset instant.                                                   |
//+------------------------------------------------------------------+
double PropBalanceAt(const datetime start_utc)
  {
   const double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   const datetime from_srv = start_utc + (datetime)BTCAI_ServerGmtOffset();
   if(!HistorySelect(from_srv, TimeTradeServer() + 3600))
      return(bal);
   double sum = 0.0;
   const int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
     {
      const ulong d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      if((datetime)HistoryDealGetInteger(d, DEAL_TIME) < from_srv)
         continue;
      sum += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) +
             HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_FEE);
     }
   return(bal - sum);
  }

//+------------------------------------------------------------------+
void PropRollDay(const bool at_init)
  {
   const datetime now = TimeGMT();
   const datetime day = BTCAI_PropDayStartUtc(now, (int)InpPropResetTz, InpPropResetHour, BTCAI_ServerGmtOffset());
   if(day == g_pg_day && g_pg_day_balance > 0.0)
      return;
   const double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   const double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   string how = "live snapshot";
   if((now - day) <= 300)
     {
      g_pg_day_balance = bal;
      g_pg_day_equity  = eq;
     }
   else
     {
      // Missed the reset (EA started later): rebuild balance from history.
      // Equity at the reset is unknown -> use the higher of the rebuilt
      // balance and current equity (conservative for the MAX/EQUITY bases).
      g_pg_day_balance = PropBalanceAt(day);
      g_pg_day_equity  = MathMax(g_pg_day_balance, eq);
      how = "rebuilt from history (late " + IntegerToString((int)((now - day) / 60)) + " min)";
     }
   g_pg_day = day;
   PgSet("day", (double)g_pg_day);
   PgSet("dbal", g_pg_day_balance);
   PgSet("deq", g_pg_day_equity);
   Print("BTCAI prop guard: new prop day from ", BTCAI_TimeToIsoUtc(day), " base bal=",
         DoubleToString(g_pg_day_balance, 2), " eq=", DoubleToString(g_pg_day_equity, 2), " (", how, ")",
         (at_init ? " [init]" : ""));
  }

//+------------------------------------------------------------------+
void PropGuardInit()
  {
   g_pg_status = "off";
   if(!InpPropGuardEnabled)
      return;
   g_pg_initial = PgGet("init", 0.0);
   if(InpPropInitialBalance > 0.0)
      g_pg_initial = InpPropInitialBalance;
   if(g_pg_initial <= 0.0)
     {
      g_pg_initial = AccountInfoDouble(ACCOUNT_BALANCE);
      Print("BTCAI prop guard: initial balance captured from the account: ", DoubleToString(g_pg_initial, 2),
            " (set PropInitialBalance to the firm account size to be exact)");
     }
   PgSet("init", g_pg_initial);
   g_pg_peak = MathMax(PgGet("peak", g_pg_initial), g_pg_initial);
   PgSet("peak", g_pg_peak);
   g_pg_day          = (datetime)PgGet("day", 0.0);
   g_pg_day_balance  = PgGet("dbal", 0.0);
   g_pg_day_equity   = PgGet("deq", 0.0);
   g_pg_dd_latched   = (PgGet("ddlatch", 0.0) > 0.5);
   g_pg_daily_trip_day = (datetime)PgGet("dtrip", 0.0);
   g_pg_profit_cap_day = (datetime)PgGet("pcap", 0.0);
   g_pg_warn_day       = (datetime)PgGet("warn", 0.0);
   if(InpPropResetDDLatch && g_pg_dd_latched)
     {
      g_pg_dd_latched = false;
      PgSet("ddlatch", 0.0);
      Print("BTCAI prop guard: DD latch CLEARED by PropResetDDLatch=true. Set it back to false.");
     }
   PropRollDay(true);
   if(InpPropFirmDailyLossPct > 0.0 && InpPropDailyLossPct >= InpPropFirmDailyLossPct)
      Print("BTCAI prop guard WARNING: guard daily ", DoubleToString(InpPropDailyLossPct, 2),
            "% is not below the firm limit ", DoubleToString(InpPropFirmDailyLossPct, 2), "%");
   if(InpPropFirmMaxDDPct > 0.0 && InpPropMaxDDPct >= InpPropFirmMaxDDPct)
      Print("BTCAI prop guard WARNING: guard DD ", DoubleToString(InpPropMaxDDPct, 2),
            "% is not below the firm limit ", DoubleToString(InpPropFirmMaxDDPct, 2), "%");
   Print("BTCAI prop guard ON: initial=", DoubleToString(g_pg_initial, 2),
         " daily guard ", DoubleToString(InpPropDailyLossPct, 2), "% (firm ", DoubleToString(InpPropFirmDailyLossPct, 2),
         "%), DD guard ", DoubleToString(InpPropMaxDDPct, 2), "% (firm ", DoubleToString(InpPropFirmMaxDDPct, 2),
         "%) ", (InpPropDDTrailing ? "trailing" : "static"), ", reset ", EnumToString(InpPropResetTz), " ",
         IntegerToString(InpPropResetHour), ":00, DD latch=", (g_pg_dd_latched ? "TRIPPED" : "clear"));
  }

//+------------------------------------------------------------------+
//| Close positions (any symbol) for the EA magic and optionally     |
//| magic-0 manual ones; delete EA pending orders.                    |
//+------------------------------------------------------------------+
string PropFlatten(const bool include_manual, const string reason)
  {
   int closed = 0, failed = 0, deleted = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      const long magic = PositionGetInteger(POSITION_MAGIC);
      const bool ours = (magic == InpMagicNumber);
      if(!ours && !(include_manual && magic == 0))
         continue;
      if(ours)
         g_pending_exit_reason = reason;
      if(g_trade.PositionClose(ticket))
        {
         closed++;
         if(ours && g_tp1_done_ticket == ticket)
            PersistTp1(0);
        }
      else
        {
         failed++;
         Print("BTCAI ", reason, " close failed ticket=", ticket, " ret=", g_trade.ResultRetcode(),
               " ", g_trade.ResultRetcodeDescription());
        }
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || OrderGetInteger(ORDER_MAGIC) != InpMagicNumber)
         continue;
      if(g_trade.OrderDelete(ticket))
         deleted++;
     }
   const string res = "closed " + IntegerToString(closed) + ", failed " + IntegerToString(failed) +
                      ", pending deleted " + IntegerToString(deleted) + (include_manual ? " (manual incl.)" : "");
   if(closed > 0 || failed > 0 || deleted > 0)
     {
      Print("BTCAI ", reason, ": ", res);
      g_journal.Write("PROP_FLATTEN", 0, g_sym, "", 0, 0, 0, 0, 0, 0, 0, 0, "", reason + ": " + res);
     }
   return(res);
  }

//+------------------------------------------------------------------+
string PropLevelsText()
  {
   const double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   const double base = PropDayBase();
   const double allow = PropDailyAllowance();
   const double floor = PropDDFloor();
   string t = "day P/L $" + DoubleToString(eq - base, 2);
   if(allow > 0.0)
      t += " (guard -$" + DoubleToString(allow, 2) + ", room $" + DoubleToString(allow - (base - eq), 2) + ")";
   if(floor > 0.0)
      t += ", DD floor $" + DoubleToString(floor, 2) + " (room $" + DoubleToString(eq - floor, 2) + ")";
   return(t);
  }

//+------------------------------------------------------------------+
void PropGuardCheck()
  {
   if(!InpPropGuardEnabled)
     {
      g_pg_status = "off";
      return;
     }
   if(g_pg_initial <= 0.0)
     {
      g_pg_status = "NOT READY (no initial balance)";
      return;
     }
   PropRollDay(false);
   const double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   const double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   const double hw = MathMax(bal, eq);
   if(hw > g_pg_peak)
     {
      g_pg_peak = hw;
      PgSet("peak", g_pg_peak);
     }
   const double dd_amount = (InpPropMaxDDPct > 0.0 ? InpPropMaxDDPct / 100.0 * g_pg_initial : 0.0);
   g_pg_flags = BTCAI_PropEvaluate(eq, PropDayBase(), PropDailyAllowance(), PropDDFloor(), dd_amount,
                                    InpPropDailyProfitCapPct, InpPropWarnFraction);

   // Overall drawdown: permanent latch.
   if((g_pg_flags & BTCAI_PG_DD_TRIP) != 0 && !g_pg_dd_latched)
     {
      g_pg_dd_latched = true;
      PgSet("ddlatch", 1.0);
      string res = "flatten off";
      if(InpPropFlattenOnTrip)
         res = PropFlatten(InpPropFlattenManual, "prop_dd_guard");
      LogUnique("PROP_DD_TRIP", PropLevelsText() + " | " + res);
      NotifyTelegram("BTCAI PROP GUARD TRIPPED: max drawdown\nEquity $" + DoubleToString(eq, 2) +
                     " <= floor $" + DoubleToString(PropDDFloor(), 2) +
                     " (guard " + DoubleToString(InpPropMaxDDPct, 2) + "%, firm " + DoubleToString(InpPropFirmMaxDDPct, 2) + "%)\n" +
                     res + "\nNew entries are blocked until the latch is reset manually.");
     }
   // Daily loss: blocked until the next prop day.
   if((g_pg_flags & BTCAI_PG_DAILY_TRIP) != 0 && g_pg_daily_trip_day != g_pg_day)
     {
      g_pg_daily_trip_day = g_pg_day;
      PgSet("dtrip", (double)g_pg_daily_trip_day);
      string res = "flatten off";
      if(InpPropFlattenOnTrip)
         res = PropFlatten(InpPropFlattenManual, "prop_daily_guard");
      LogUnique("PROP_DAILY_TRIP", PropLevelsText() + " | " + res);
      NotifyTelegram("BTCAI PROP GUARD TRIPPED: daily loss\n" + PropLevelsText() +
                     "\nGuard " + DoubleToString(InpPropDailyLossPct, 2) + "% vs firm " +
                     DoubleToString(InpPropFirmDailyLossPct, 2) + "%\n" + res +
                     "\nNo new entries until the next reset (" + EnumToString(InpPropResetTz) + " " +
                     IntegerToString(InpPropResetHour) + ":00).");
     }
   // Daily profit cap.
   if((g_pg_flags & BTCAI_PG_PROFIT_CAP) != 0 && g_pg_profit_cap_day != g_pg_day)
     {
      g_pg_profit_cap_day = g_pg_day;
      PgSet("pcap", (double)g_pg_profit_cap_day);
      string res = "positions kept";
      if(InpPropProfitCapFlatten)
         res = PropFlatten(false, "prop_profit_cap");
      LogUnique("PROP_PROFIT_CAP", PropLevelsText() + " | " + res);
      NotifyTelegram("BTCAI prop daily profit cap reached (" + DoubleToString(InpPropDailyProfitCapPct, 2) +
                     "%)\n" + PropLevelsText() + "\n" + res + "\nNo new entries until the next reset.");
     }
   // One warning per day.
   if((g_pg_flags & BTCAI_PG_WARN) != 0 && g_pg_warn_day != g_pg_day &&
      (g_pg_flags & (BTCAI_PG_DD_TRIP | BTCAI_PG_DAILY_TRIP)) == 0)
     {
      g_pg_warn_day = g_pg_day;
      PgSet("warn", (double)g_pg_warn_day);
      LogUnique("PROP_WARN", PropLevelsText());
      NotifyTelegram("BTCAI prop guard WARNING: " + DoubleToString(InpPropWarnFraction * 100.0, 0) +
                     "% of an allowance used\n" + PropLevelsText());
     }
   // Keep EA positions flat while a loss guard is tripped (retries failed closes).
   const bool tripped = (g_pg_dd_latched || g_pg_daily_trip_day == g_pg_day);
   if(tripped && InpPropFlattenOnTrip && (CountEaPositionsAnySymbol() > 0 || CountEaPendingAnySymbol() > 0))
      PropFlatten(false, "prop_guard_hold_flat");

   string st = "";
   if(g_pg_dd_latched)
      st = "DD LATCHED";
   else if(g_pg_daily_trip_day == g_pg_day)
      st = "DAILY TRIPPED";
   else if(g_pg_profit_cap_day == g_pg_day)
      st = "PROFIT CAP";
   else
      st = ((g_pg_flags & BTCAI_PG_WARN) != 0 ? "WARN" : "OK");
   g_pg_status = st + " | " + PropLevelsText();
  }

//+------------------------------------------------------------------+
bool PropEntriesBlocked(string &why)
  {
   why = "";
   if(!InpPropGuardEnabled)
      return(false);
   if(g_pg_initial <= 0.0)
     {
      why = "no initial balance";
      return(true);
     }
   if(g_pg_dd_latched)
     {
      why = "max drawdown guard latched (" + PropLevelsText() + ")";
      return(true);
     }
   if(g_pg_daily_trip_day == g_pg_day && g_pg_day > 0)
     {
      why = "daily loss guard tripped (" + PropLevelsText() + ")";
      return(true);
     }
   if(g_pg_profit_cap_day == g_pg_day && g_pg_day > 0)
     {
      why = "daily profit cap reached";
      return(true);
     }
   if(InpPropMaxOpenPositions > 0 && CountEaPositionsAnySymbol() >= InpPropMaxOpenPositions)
     {
      why = "max open EA positions " + IntegerToString(InpPropMaxOpenPositions);
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Prop news mode: is now inside a flat window of a listed event?   |
//+------------------------------------------------------------------+
bool PropNewsFlatActive(string &why, int &idx)
  {
   why = "";
   idx = -1;
   if(!InpPropNewsFlatEnabled)
      return(false);
   const datetime now = TimeGMT();
   datetime best_from = 0, best_to = 0;
   for(int i = 0; i < ArraySize(g_news); i++)
     {
      datetime f = 0, t = 0;
      if(BTCAI_PropNewsFlatWindow(now, g_news[i].start_utc, g_news[i].end_utc,
                                   InpNewsBlackoutBeforeMin, InpNewsBlackoutAfterMin,
                                   InpPropNewsFlatBeforeMin, InpPropNewsFlatAfterMin, f, t))
        {
         if(idx < 0 || g_news[i].event_utc < g_news[idx].event_utc)
           {
            idx = i;
            best_from = f;
            best_to = t;
           }
        }
     }
   if(idx < 0)
      return(false);
   why = g_news[idx].name + " @ " + BTCAI_TimeToIsoUtc(g_news[idx].event_utc) + " (flat " +
         StringSubstr(BTCAI_TimeToIsoUtc(best_from), 11, 5) + "-" + StringSubstr(BTCAI_TimeToIsoUtc(best_to), 11, 5) + "Z)";
   return(true);
  }

//+------------------------------------------------------------------+
void ManagePropNewsFlat()
  {
   g_pnews_status = "";
   if(!InpPropNewsFlatEnabled)
      return;
   string why = "";
   int idx = -1;
   if(!PropNewsFlatActive(why, idx))
     {
      g_pnews_status = "armed";
      return;
     }
   g_pnews_status = "FLAT WINDOW " + why;
   const bool have_ea = (CountEaPositionsAnySymbol() > 0 || CountEaPendingAnySymbol() > 0);
   const string key = IntegerToString((long)g_news[idx].event_utc);
   if(!have_ea && !(InpPropNewsFlatManual && key != g_pnews_key))
      return;
   const bool manual = (InpPropNewsFlatManual && key != g_pnews_key);
   const string res = PropFlatten(manual, "prop_news_flat");
   if(key != g_pnews_key && (have_ea || StringFind(res, "closed 0,") < 0))
     {
      g_pnews_key = key;
      LogUnique("PROP_NEWS_FLAT", why + " | " + res);
      NotifyTelegram("BTCAI prop news mode: flat before news\n" + why + "\n" + res +
                     "\nNo new entries until the window ends.");
     }
  }

//+------------------------------------------------------------------+
//| v1.03 Telegram commands                                           |
//+------------------------------------------------------------------+
string GvPausedName()
  {
   return("BTCAI_" + IntegerToString(InpMagicNumber) + "_paused");
  }

//+------------------------------------------------------------------+
string TgOffsetFileName()
  {
   return("BTCAI_" + IntegerToString(InpMagicNumber) + "_tg_offset.txt");
  }

//+------------------------------------------------------------------+
void LoadTgOffset()
  {
   g_tg_offset = 0;
   const int h = FileOpen(TgOffsetFileName(), FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   g_tg_offset = StringToInteger(FileReadString(h));
   FileClose(h);
  }

//+------------------------------------------------------------------+
void SaveTgOffset()
  {
   const int h = FileOpen(TgOffsetFileName(), FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return;
   FileWriteString(h, IntegerToString(g_tg_offset));
   FileClose(h);
  }

//+------------------------------------------------------------------+
bool TgReply(const string text)
  {
   int status = 0;
   string err = "";
   const bool ok = BTCAI_TelegramSend(InpEnableTelegram, InpTelegramToken, InpTgAllowedChatId,
                                       InpWebTimeoutMs, text, status, err);
   if(!ok)
      Print("BTCAI telegram reply failed: ", err, " (HTTP ", status, ")");
   return(ok);
  }

//+------------------------------------------------------------------+
void SetPaused(const bool paused)
  {
   g_paused = paused;
   GlobalVariableSet(GvPausedName(), paused ? 1.0 : 0.0);
   LogUnique(paused ? "TG_PAUSE" : "TG_RESUME",
             paused ? "new entries paused via Telegram" : "new entries resumed via Telegram");
  }

//+------------------------------------------------------------------+
int CountEaPositionsAnySymbol()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t != 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
int CountEaPendingAnySymbol()
  {
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      const ulong t = OrderGetTicket(i);
      if(t != 0 && OrderGetInteger(ORDER_MAGIC) == InpMagicNumber)
         n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
//| Close ONLY positions/orders carrying this EA's magic number.     |
//+------------------------------------------------------------------+
string CloseAllEaPositions()
  {
   int closed = 0, failed = 0, deleted = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;
      g_pending_exit_reason = "telegram_closeall";
      if(g_trade.PositionClose(ticket))
        {
         closed++;
         Print("BTCAI telegram /closeall closed ticket=", ticket);
         if(g_tp1_done_ticket == ticket)
            PersistTp1(0);
        }
      else
        {
         failed++;
         Print("BTCAI telegram /closeall failed ticket=", ticket,
               " ret=", g_trade.ResultRetcode(), " ", g_trade.ResultRetcodeDescription());
        }
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagicNumber)
         continue;
      if(g_trade.OrderDelete(ticket))
         deleted++;
     }
   const string res = "closed " + IntegerToString(closed) + ", failed " + IntegerToString(failed) +
                      ", pending deleted " + IntegerToString(deleted);
   LogUnique("TG_CLOSEALL", res);
   return(res);
  }

//+------------------------------------------------------------------+
string StatusText()
  {
   const int digits = g_digits;
   string t = "BTCAI v1.04 status\n";
   t += "Account: " + BTCAI_AccountModeText() + "  server " + AccountInfoString(ACCOUNT_SERVER) + "\n";
   t += "Balance: $" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) +
        "  Equity: $" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";
   t += "Day P/L: " + DoubleToString(-DailyLossPct(), 2) + "% (cap -" + DoubleToString(InpMaxDailyLossPct, 2) + "%)\n";
   t += "Entries: " + (g_paused ? "PAUSED (/resume)" : "allowed") + "\n";
   t += "EA state: " + BTCAI_Truncate(g_status, 160) + "\n";

   int n = 0;
   string pos = "";
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;
      n++;
      const string sym = PositionGetString(POSITION_SYMBOL);
      const int d = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      pos += "- " + (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY " : "SELL ") +
             DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + " " + sym +
             " @ " + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), d) +
             " SL " + DoubleToString(PositionGetDouble(POSITION_SL), d) +
             " TP " + DoubleToString(PositionGetDouble(POSITION_TP), d) +
             " P&L $" + DoubleToString(PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP), 2) + "\n";
     }
   t += "EA positions: " + IntegerToString(n) + (n > 0 ? "\n" + pos : "\n");

   if(g_have_decision && g_decision.loaded)
     {
      t += "Decision: " + g_decision.bias_text + " conf " + IntegerToString(g_decision.confidence);
      if(g_decision.bias != BTC_AI_BIAS_NONE)
         t += "\nZone " + DoubleToString(g_decision.zone_low, digits) + "-" + DoubleToString(g_decision.zone_high, digits) +
              " SL " + DoubleToString(g_decision.stop_loss, digits) +
              " TP1 " + DoubleToString(g_decision.tp1, digits) +
              " TP2 " + DoubleToString(g_decision.tp2, digits);
      t += "\nValid until " + BTCAI_TimeToIsoUtc(g_decision.valid_until) +
           (g_decision.kill_switch ? "  KILL SWITCH ON" : "") + "\n";
     }
   else
      t += "Decision: none loaded (" + g_poll_status + ")\n";

   t += "News: " + NewsPanelText() + "\n";
   if(InpNewsBlackoutEnabled)
      t += "News sources: calendar " + g_news_cal_status + ", file " + g_news_file_status + "\n";
   t += "Symbol: " + g_sym + "\n";
   t += "Market gaps: " + g_gap_status + (InpWeekendFlattenEnabled ? " (weekend flatten ON)" : "") + "\n";
   t += "Prop guard: " + g_pg_status + "\n";
   t += "Prop news mode: " + (InpPropNewsFlatEnabled ? g_pnews_status : "off");
   return(t);
  }

//+------------------------------------------------------------------+
string HelpText()
  {
   return("BTCAI commands:\n" +
          "/status - balance, equity, EA positions, decision, next news window\n" +
          "/pause - stop NEW entries (open trades still managed)\n" +
          "/resume - allow new entries again\n" +
          "/closeall - close ONLY EA positions (magic " + IntegerToString(InpMagicNumber) + "), needs /confirm <code> within " +
          IntegerToString(InpTgConfirmSeconds) + "s\n" +
          "/guard - prop-firm guard state\n" +
          "/help - this list");
  }

//+------------------------------------------------------------------+
void HandleTgCommand(const string text_in)
  {
   string text = text_in;
   StringTrimLeft(text);
   StringTrimRight(text);
   if(StringLen(text) < 2 || StringGetCharacter(text, 0) != '/')
      return; // plain chat text is ignored
   string parts[];
   const int np = StringSplit(text, ' ', parts);
   string cmd = (np > 0 ? parts[0] : text);
   const int at = StringFind(cmd, "@");
   if(at > 0)
      cmd = StringSubstr(cmd, 0, at);
   StringToLower(cmd);
   string arg = "";
   for(int i = 1; i < np; i++)
      if(parts[i] != "")
        {
         arg = parts[i];
         break;
        }

   Print("BTCAI telegram command: ", cmd);
   const datetime now = TimeGMT();

   if(cmd == "/help" || cmd == "/start")
     {
      TgReply(HelpText());
      return;
     }
   if(cmd == "/status")
     {
      TgReply(StatusText());
      return;
     }
   if(cmd == "/guard")
     {
      PropGuardCheck();
      TgReply("BTCAI prop guard: " + g_pg_status +
              (InpPropGuardEnabled ? ("\nInitial $" + DoubleToString(g_pg_initial, 2) +
                                     "  peak $" + DoubleToString(g_pg_peak, 2) +
                                     "\nDay from " + BTCAI_TimeToIsoUtc(g_pg_day) +
                                     "  base $" + DoubleToString(PropDayBase(), 2) +
                                     "\nDaily guard " + DoubleToString(InpPropDailyLossPct, 2) + "% (firm " + DoubleToString(InpPropFirmDailyLossPct, 2) +
                                     "%), DD guard " + DoubleToString(InpPropMaxDDPct, 2) + "% (firm " + DoubleToString(InpPropFirmMaxDDPct, 2) + "%)" +
                                     (InpPropDailyProfitCapPct > 0.0 ? ("\nProfit cap " + DoubleToString(InpPropDailyProfitCapPct, 2) + "%") : ""))
                                  : "") +
              "\nNews mode: " + (InpPropNewsFlatEnabled ? g_pnews_status : "off"));
      return;
     }
   if(cmd == "/pause")
     {
      SetPaused(true);
      UpdatePanel(true);
      TgReply("BTCAI: new entries PAUSED. Open EA trades are still managed (SL/TP/trail/weekend rule). Send /resume to allow entries.");
      return;
     }
   if(cmd == "/resume")
     {
      SetPaused(false);
      UpdatePanel(true);
      TgReply("BTCAI: new entries ALLOWED again. All risk rules, news blackout and the gap rule still apply.");
      return;
     }
   if(cmd == "/closeall")
     {
      const int np_ = CountEaPositionsAnySymbol();
      const int no_ = CountEaPendingAnySymbol();
      if(np_ == 0 && no_ == 0)
        {
         g_confirm_code = "";
         TgReply("BTCAI: no open EA positions or orders (magic " + IntegerToString(InpMagicNumber) + "). Nothing to close.");
         return;
        }
      g_confirm_code  = IntegerToString(1000 + MathRand() % 9000);
      g_confirm_until = now + (InpTgConfirmSeconds < 10 ? 10 : InpTgConfirmSeconds);
      TgReply("BTCAI: close " + IntegerToString(np_) + " EA position(s) and " + IntegerToString(no_) +
              " EA order(s)? Manual trades are NOT touched.\nReply /confirm " + g_confirm_code +
              " within " + IntegerToString((int)(g_confirm_until - now)) + "s.");
      return;
     }
   if(cmd == "/confirm")
     {
      if(g_confirm_code == "" || now > g_confirm_until)
        {
         g_confirm_code = "";
         TgReply("BTCAI: no pending /closeall, or the code expired. Nothing closed.");
         return;
        }
      if(arg != g_confirm_code)
        {
         g_confirm_code = "";
         TgReply("BTCAI: wrong code. Nothing closed. Send /closeall again.");
         return;
        }
      g_confirm_code = "";
      const string res = CloseAllEaPositions();
      UpdatePanel(true);
      TgReply("BTCAI /closeall done: " + res + ".\nNew entries are " + (g_paused ? "PAUSED" : "still allowed (send /pause to stop them)") + ".");
      return;
     }
   TgReply("BTCAI: unknown command. Send /help");
  }

//+------------------------------------------------------------------+
void PollTelegramCommands()
  {
   if(!InpTgCommandsEnabled || !InpEnableTelegram)
      return;
   if(InpTelegramToken == "" || InpTgAllowedChatId == "")
      return;
   if(MQLInfoInteger(MQL_TESTER))
      return;
   const datetime now = TimeGMT();
   const int every = (InpTgPollSeconds < 2 ? 2 : InpTgPollSeconds);
   if((now - g_tg_last_poll) < every)
      return;
   g_tg_last_poll = now;

   string body = "timeout=0&limit=20&allowed_updates=" + BTCAI_UrlEncode("[\"message\"]");
   if(g_tg_offset > 0)
      body += "&offset=" + IntegerToString(g_tg_offset);
   string resp = "", err = "";
   int status = 0;
   if(!BTCAI_TelegramCall(InpTelegramToken, "getUpdates", body,
                           (InpTgPollTimeoutMs < 500 ? 500 : InpTgPollTimeoutMs),
                           resp, status, err))
     {
      // Throttle: log a given error at most every 10 minutes.
      if(err != g_tg_last_err || (now - g_tg_last_err_at) >= 600)
        {
         g_tg_last_err    = err;
         g_tg_last_err_at = now;
         Print("BTCAI telegram getUpdates failed: ", err,
               (status == 409 ? " (another getUpdates poller or a webhook is active on this bot)" : ""));
        }
      return;
     }
   g_tg_last_err = "";

   const string arr = JsonGetArray(resp, "result");
   if(arr == "")
      return;
   string items[];
   bool   flags[];
   const int n = JsonSplitArray(arr, items, flags);
   const long old_offset = g_tg_offset;
   for(int i = 0; i < n; i++)
     {
      if(flags[i])
         continue;
      string raw = "";
      bool is_str = false;
      if(!JsonGet(items[i], "update_id", raw, is_str))
         continue;
      const long uid = StringToInteger(raw);
      if(uid + 1 > g_tg_offset)
         g_tg_offset = uid + 1;

      const string msg = JsonGetObject(items[i], "message");
      if(msg == "")
         continue;
      const string chat = JsonGetObject(msg, "chat");
      string cid = "";
      if(chat == "" || !JsonGet(chat, "id", cid, is_str))
         continue;
      StringTrimLeft(cid);
      StringTrimRight(cid);
      string allowed = InpTgAllowedChatId;
      StringTrimLeft(allowed);
      StringTrimRight(allowed);
      if(cid != allowed)
        {
         Print("BTCAI telegram: ignored an update from a non-allowed chat");
         continue;
        }
      const long msg_date = (long)JsonGetNumberDef(msg, "date", 0.0);
      if(msg_date > 0 && msg_date < (long)g_start_gmt - 5)
        {
         Print("BTCAI telegram: ignored a command sent before this EA start");
         continue;
        }
      HandleTgCommand(JsonGetString(msg, "text", ""));
     }
   if(g_tg_offset != old_offset)
      SaveTgOffset();
  }

//+------------------------------------------------------------------+
void UpdatePanel(const bool force)
  {
   const datetime now = TimeGMT();
   if(!force && g_last_panel == now)
      return;
   g_last_panel = now;

   const int digits = g_digits;
   string lines = "";
   lines += "====== BTCAI Bridge v1.04 ======\n";
   lines += "Account:  " + BTCAI_AccountModeText() +
            "  #" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) +
            "  " + AccountInfoString(ACCOUNT_CURRENCY) + "\n";
   lines += "Symbol:   " + g_sym +
            "  (expect " + InpExpectedSymbol + ")\n";
   lines += "Spread:   " + IntegerToString(BTCAI_CurrentSpreadPoints(g_sym)) +
            " points  (max " + IntegerToString(InpMaxSpreadPoints) + ")\n";
   lines += "Server:   " + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS) +
            "   GMT " + BTCAI_TimeToIsoUtc(now) + "\n";
   lines += "--- Decision ---\n";
   lines += "Poll:     " + (g_last_poll > 0 ? BTCAI_TimeToIsoUtc(g_last_poll) : "never") +
            "  " + g_poll_status + "\n";

   if(g_have_decision && g_decision.loaded)
     {
      lines += "Valid:    until " + BTCAI_TimeToIsoUtc(g_decision.valid_until) +
               "  (" + BTCAI_TimeLeftText(g_decision.valid_until) + ")\n";
      lines += "Bias:     " + g_decision.bias_text +
               "    conf " + IntegerToString(g_decision.confidence) +
               "/" + IntegerToString(InpMinConfidence) + " min\n";
      lines += "Zone:     " + DoubleToString(g_decision.zone_low, digits) +
               " - " + DoubleToString(g_decision.zone_high, digits) + "\n";
      lines += "SL:       " + DoubleToString(g_decision.stop_loss, digits) + "\n";
      lines += "TP1/TP2:  " + DoubleToString(g_decision.tp1, digits) +
               " / " + DoubleToString(g_decision.tp2, digits) + "\n";
      lines += "Risk:     " + DoubleToString(EffectiveRiskPct(), 2) +
               "%  (EA cap " + DoubleToString(InpRiskPercentPerTrade, 2) +
               "%, file " + DoubleToString(g_decision.max_risk_pct, 2) + "%)\n";
      lines += "Kill:     " + (g_decision.kill_switch ? "ON" : "off") + "\n";
      string br = "";
      const bool in_bl = BTCAI_InBlackout(g_decision, now, br);
      lines += "Blackout: " + (in_bl ? ("YES " + br) : "no") + "\n";
      lines += "Why:      " + BTCAI_Truncate(g_decision.rationale, 90) + "\n";
     }
   else
     {
      lines += "(no usable decision cached)\n";
     }

   lines += "--- Status ---\n";
   lines += g_status + "\n";
   lines += "Daily P/L: " + DoubleToString(-DailyLossPct(), 2) +
            "% of start equity  (cap -" + DoubleToString(InpMaxDailyLossPct, 2) + "%)\n";
   lines += "Telegram: " + ((InpEnableTelegram && InpTelegramToken != "" && InpTelegramChatId != "") ? "enabled" : "off") + "\n";
   lines += "Gaps:     " + g_gap_status + (InpWeekendFlattenEnabled ? "  [weekend flatten ON]" : "") + "\n";
   if(InpTrailEnabled)
      lines += "Trail:    after TP1  " +
               (InpTrailUseSwing ? "swing " : "") +
               (InpTrailUseATR ? ("ATR(" + IntegerToString(InpTrailATRPeriod) + ")*" + DoubleToString(InpTrailATRMult, 2) + " ") : "") +
               EnumToString(InpTrailTF) + "\n";
   else
      lines += "Trail:    off\n";

   ulong ticket = 0;
   if(SelectOurPosition(ticket))
     {
      const string side = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL");
      lines += "Open:     " + DoubleToString(PositionGetDouble(POSITION_VOLUME), 4) +
               " " + side + " @ " + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits) +
               "  sl " + DoubleToString(PositionGetDouble(POSITION_SL), digits) +
               "  tp " + DoubleToString(PositionGetDouble(POSITION_TP), digits) +
               (ticket == g_tp1_done_ticket ? "  (TP1 done)" : "  (TP1 pending)") + "\n";
     }
   else
      lines += "Open:     none\n";

   lines += "News:     " + NewsPanelText() + "\n";
   if(InpNewsBlackoutEnabled)
      lines += "News src: cal " + g_news_cal_status + " | file " + g_news_file_status + "\n";
   lines += "TG cmds:  " + ((InpTgCommandsEnabled && InpEnableTelegram && InpTelegramToken != "") ? "on" : "off") +
            (g_paused ? "   ENTRIES PAUSED (/resume)" : "") + "\n";

   lines += "Prop:     " + BTCAI_Truncate(g_pg_status, 110) + "\n";
   if(InpPropNewsFlatEnabled)
      lines += "PropNews: " + BTCAI_Truncate(g_pnews_status, 110) + "\n";
   if(g_trade_locked)
      lines += "LOCK:     " + g_lock_reason + "\n";

   Comment(lines);
  }

//+------------------------------------------------------------------+
void ManageAndMaybeEnter()
  {
   RefreshDailyWindow();
   PropGuardCheck();
   ManagePropNewsFlat();
   ManageWeekendGap();
   EnforceDecisionOnOpenTrade();
   ManageOpenPosition();
   TryOpenTrade();
   UpdatePanel(false);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   g_sym = ResolveTradeSymbol();
   if(g_sym == "")
     {
      Print("BTCAI: no BTCUSD symbol found (TradeSymbol='", InpTradeSymbol, "'). Check Market Watch / symbol name.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_digits = (int)SymbolInfoInteger(g_sym, SYMBOL_DIGITS);
   if(g_sym != _Symbol)
      Print("BTCAI WARNING: trading ", g_sym, " but attached to chart ", _Symbol,
            ". Attach to a ", g_sym, " chart so OnTick follows the traded symbol.");
   Print("BTCAI symbol ", g_sym, ": contract=", DoubleToString(SymbolInfoDouble(g_sym, SYMBOL_TRADE_CONTRACT_SIZE), 4),
         " tick_size=", DoubleToString(SymbolInfoDouble(g_sym, SYMBOL_TRADE_TICK_SIZE), 8),
         " tick_value=", DoubleToString(SymbolInfoDouble(g_sym, SYMBOL_TRADE_TICK_VALUE), 8),
         " vol min/step/max=", DoubleToString(SymbolInfoDouble(g_sym, SYMBOL_VOLUME_MIN), 4), "/",
         DoubleToString(SymbolInfoDouble(g_sym, SYMBOL_VOLUME_STEP), 4), "/",
         DoubleToString(SymbolInfoDouble(g_sym, SYMBOL_VOLUME_MAX), 2),
         " spread=", BTCAI_CurrentSpreadPoints(g_sym), " pts (max ", InpMaxSpreadPoints, ")");
   g_sl_atr_handle = iATR(g_sym, InpSlAtrTF, (InpSlAtrPeriod < 1 ? 14 : InpSlAtrPeriod));
   g_week_built = 0;
   BTCAI_DecisionClear(g_decision);
   g_have_decision = false;
   g_first_timer   = true;
   g_poll_status   = "not polled yet";
   g_status        = "initializing";

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints((uint)(InpSlippagePoints < 0 ? 0 : InpSlippagePoints));
   g_trade.SetAsyncMode(false);
   g_trade.SetTypeFillingBySymbol(g_sym);

   if(!g_journal.Init(InpJournalFile))
      Print("BTCAI warning: journal file could not be prepared");

   LoadPersistedState();
   RefreshDailyWindow();

   g_start_gmt = TimeGMT();
   MathSrand((uint)(GetTickCount() ^ (uint)TimeLocal()));
   g_paused = (GlobalVariableCheck(GvPausedName()) && GlobalVariableGet(GvPausedName()) > 0.5);
   if(g_paused)
      Print("BTCAI: entries are PAUSED (persisted from Telegram /pause). Send /resume to allow.");
   LoadTgOffset();
   g_news_cal_at  = 0;
   g_news_file_at = 0;
   g_last_manage  = 0;

   const string login_txt = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   Print("BTCAI v1.00 account: mode=", BTCAI_AccountModeText(),
         " server=", AccountInfoString(ACCOUNT_SERVER),
         " company=", AccountInfoString(ACCOUNT_COMPANY),
         " login=***", StringSubstr(login_txt, MathMax(0, StringLen(login_txt) - 3)),
         " currency=", AccountInfoString(ACCOUNT_CURRENCY),
         " AllowLiveAccount=", (InpAllowLiveAccount ? "true" : "false"),
         " AllowedServers='", InpAllowedServers, "'",
         " PropGuard=", (InpPropGuardEnabled ? "ON" : "off"),
         " PropNewsFlat=", (InpPropNewsFlatEnabled ? "ON" : "off"));
   g_trade_locked = false;
   g_lock_reason  = "";
   if(RealAccountBlocked())
     {
      g_trade_locked = true;
      g_lock_reason  = BTCAI_AccountModeText() + " account is blocked. Run on DEMO, or set AllowLiveAccount=true deliberately.";
      Print("BTCAI ", g_lock_reason);
     }
   if(ServerBlocked())
     {
      g_trade_locked = true;
      g_lock_reason  = "server " + AccountInfoString(ACCOUNT_SERVER) + " is not in AllowedServers '" + InpAllowedServers + "'";
      Print("BTCAI ", g_lock_reason);
     }
   if(!BTCAI_IsDemoAccount() && InpAllowLiveAccount && !InpPropGuardEnabled)
      Print("BTCAI WARNING: non-demo account allowed but the prop guard is OFF.");
   PropGuardInit();

   if(InpPollMinutes < 1)
      Print("BTCAI: PollMinutes < 1 is not allowed; will use 1 minute");

   if(!InpUseLocalFile)
     {
      string url = InpDecisionURL;
      StringTrimLeft(url);
      StringTrimRight(url);
      if(url == "" || StringFind(url, "USER/REPO") >= 0)
         Print("BTCAI: DecisionURL is empty or a placeholder. Set the raw HTTPS URL of btc/decisions/current.json, ",
               "or enable UseLocalFile and place current.json in MQL5/Files. See README.md.");
     }

   if(!EventSetTimer(1))
     {
      Print("BTCAI: EventSetTimer failed - will poll from OnTick as a fallback");
     }

   g_journal.Write("START",
                   0,
                   g_sym,
                   "",
                   0, 0, 0, 0, 0, 0, 0, 0,
                   "",
                   "EA attached, account=" + BTCAI_AccountModeText());

   LoadTelegramState();
   if(InpEnableTelegram)
     {
      int st = 0;
      string terr = "";
      const bool sent = BTCAI_TelegramSend(true,
                                            InpTelegramToken,
                                            InpTelegramChatId,
                                            InpWebTimeoutMs,
                                            "BTCAIBridge online (v1.00 on " + g_sym + ", " + BTCAI_AccountModeText() + ", prop guard " + (InpPropGuardEnabled ? "ON" : "off") + "). Send /help for commands.",
                                            st,
                                            terr);
      if(sent)
         Print("BTCAI telegram startup test sent, WebRequest HTTP ", st);
      else
         Print("BTCAI telegram startup test failed: ", terr, " (WebRequest HTTP ", st, ")");
     }
   else
      Print("BTCAI telegram disabled (EnableTelegram=false)");

   UpdatePanel(true);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_atr_handle != INVALID_HANDLE)
     {
      IndicatorRelease(g_atr_handle);
      g_atr_handle = INVALID_HANDLE;
     }
   if(g_sl_atr_handle != INVALID_HANDLE)
     {
      IndicatorRelease(g_sl_atr_handle);
      g_sl_atr_handle = INVALID_HANDLE;
     }
   Comment("");
   Print("BTCAI stopped, reason=", reason);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   // v1.03: 1-second heartbeat. Decision poll keeps its PollMinutes interval;
   // news refresh, Telegram command polling and management have their own gates.
   const datetime now = TimeGMT();
   const int interval = (InpPollMinutes < 1 ? 1 : InpPollMinutes) * 60;
   bool polled = false;
   if(g_first_timer || g_last_poll == 0 || (now - g_last_poll) >= interval)
     {
      g_first_timer = false;
      PollDecision();
      polled = true;
     }
   RefreshNews(false);
   PollTelegramCommands();
   if(polled || (now - g_last_manage) >= 5)
     {
      g_last_manage = now;
      ManageAndMaybeEnter();
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Timer is the main poller; OnTick is a fallback if the interval has lapsed.
   const int interval = (InpPollMinutes < 1 ? 1 : InpPollMinutes) * 60;
   if(g_last_poll == 0 || (TimeGMT() - g_last_poll) >= interval)
      PollDecision();
   ManageAndMaybeEnter();
  }

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   if(trans.deal == 0)
      return;
   if(!HistoryDealSelect(trans.deal))
      return;
   if((long)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagicNumber)
      return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != g_sym)
      return;

   const long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT && entry != DEAL_ENTRY_OUT_BY)
      return;

   const ulong  pos_id = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   bool still_open = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong t = PositionGetTicket(i);
      if(t == 0)
         continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER) == pos_id)
        {
         still_open = true;
         break;
        }
     }
   if(still_open)
      return; // partial close - already journaled as TP1_PARTIAL when we initiated it

   const double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
                         + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
                         + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   const double volume = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   const double price  = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   const long   dtype  = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   const string bias   = (dtype == DEAL_TYPE_SELL ? "BUY" : (dtype == DEAL_TYPE_BUY ? "SELL" : ""));
   // A closing SELL deal exits a BUY position, and vice versa.

   const string pending_reason = g_pending_exit_reason;
   string details = pending_reason;
   if(details == "")
      details = "deal out, reason=" + IntegerToString((int)HistoryDealGetInteger(trans.deal, DEAL_REASON));
   g_pending_exit_reason = "";

   const ulong ticket = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   g_journal.Write("EXIT",
                   ticket,
                   g_sym,
                   bias,
                   volume,
                   price,
                   0.0,
                   (g_have_decision ? g_decision.tp1 : 0.0),
                   (g_have_decision ? g_decision.tp2 : 0.0),
                   profit,
                   (g_have_decision ? g_decision.confidence : 0),
                   (g_have_decision ? g_decision.generated_at : 0),
                   (g_have_decision ? g_decision.rationale : ""),
                   details);
   Print("BTCAI EXIT ticket=", ticket, " pnl=", DoubleToString(profit, 2), " ", details);
   {
    const long deal_reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
    const string reason_txt = BTCAI_DealCloseReason(deal_reason, pending_reason);
    const double net = BTCAI_PositionNetPnl(pos_id, profit);
    string pnl_txt = DoubleToString(net, 2);
    if(net > 0.0)
       pnl_txt = "+" + pnl_txt;
    NotifyTelegram("BTCAI position closed\nReason: " + reason_txt +
                   "\nP&L: $" + pnl_txt +
                   "\nTicket: " + IntegerToString((long)ticket));
   }
   if(g_tp1_done_ticket != 0)
      PersistTp1(0);
   UpdatePanel(true);
  }

//+------------------------------------------------------------------+

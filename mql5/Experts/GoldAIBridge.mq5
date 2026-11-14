//+------------------------------------------------------------------+
//| GoldAIBridge.mq5                                                 |
//| AI-directed gold EA for MetaTrader 5.                            |
//|                                                                  |
//| The assistant researches gold and writes a JSON decision file.   |
//| This EA polls that file and will only open a trade when price    |
//| is inside the AI entry zone. Hard risk limits stay locked here.  |
//|                                                                  |
//| Demo only by default. WebRequest must be allowed for the URL     |
//| (Tools > Options > Expert Advisors). See mql5/docs/SETUP.md.     |
//+------------------------------------------------------------------+
#property copyright   "Gold Algo / Rishi Jangid"
#property version     "1.03"
#property description "AI-directed gold EA. Polls a decision JSON and trades only inside the AI zone."
#property description "Hard risk rules (risk %, daily loss, spread, max trades, demo lock) stay in the EA."
#property description "v1.02: Friday auto-close before the weekly gold close, and structure/ATR trailing after TP1."
#property description "v1.03: news auto-blackout (MT5 calendar + news.json) and Telegram commands (/status /pause /resume /closeall)."
#property description "DEMO only unless AllowRealAccount is explicitly enabled. See SETUP.md."

#include <Trade\Trade.mqh>
#include <GoldAIDecision.mqh>
#include <GoldAIJournal.mqh>
#include <GoldAITelegram.mqh>
#include <GoldAINews.mqh>

//+------------------------------------------------------------------+
//| Inputs                                                             |
//+------------------------------------------------------------------+
input group "Connection"
input string InpDecisionURL     = "https://raw.githubusercontent.com/USER/REPO/main/decisions/current.json"; // Placeholder until hosting is decided
input int    InpPollMinutes     = 5;                 // Poll interval in minutes (min 1)
input int    InpWebTimeoutMs    = 8000;              // HTTP timeout (milliseconds)
input bool   InpUseLocalFile    = false;             // Read from MQL5/Files instead of the URL
input string InpLocalFileName   = "current.json";    // Local filename inside MQL5/Files

input group "Symbol"
input string InpExpectedSymbol  = "XAUUSD";          // Logical symbol in the decision file

input group "Risk (locked in the EA)"
input double InpRiskPercentPerTrade = 0.50;          // Max % of equity risked per trade
input double InpMaxDailyLossPct     = 2.00;          // Stop new trades after this daily equity drop
input int    InpMaxOpenTrades       = 1;             // Max open GoldAI positions on this symbol
input int    InpMaxSpreadPoints     = 50;            // Block entry if spread (points) is wider
input int    InpMinConfidence       = 60;            // Ignore decisions below this confidence
input long   InpMagicNumber         = 26011301;      // Magic number for this EA's orders
input int    InpSlippagePoints      = 30;            // Max deviation for market orders (points)

input group "Safety"
input bool   InpAllowRealAccount    = false;         // UNSAFE: allow a real account (leave false)

input group "Trade management"
input double InpTP1CloseFraction    = 0.50;          // Fraction to close at TP1 (then SL -> breakeven)
input int    InpBreakevenOffsetPoints = 0;           // Extra points beyond entry for the BE stop
input bool   InpCloseOnBiasFlip     = true;          // Close if a new decision flips bias or goes NONE
input bool   InpCloseOnKillSwitch   = true;          // Close if the file raises kill_switch

input group "Friday close"
input bool   InpFridayCloseEnabled   = true;         // Flatten GoldAI trades before the weekly close
input int    InpFridayCloseHHMM      = 0;            // Flatten at this server HHMM; 0 = 45 min before Friday session end
input int    InpFridayNoEntryMinutes = 120;          // Block new entries this many minutes before the flatten time
input bool   InpFridayCloseManual    = false;        // Also flatten magic-0 manual positions/orders on this symbol

input group "Trailing after TP1"
input bool             InpTrailEnabled        = true;     // Trail the remaining half after TP1 + breakeven
input bool             InpTrailUseSwing       = true;     // Trail behind the last closed M15 swing high/low
input bool             InpTrailUseATR         = true;     // Also consider ATR(period) * multiplier
input ENUM_TIMEFRAMES  InpTrailTF             = PERIOD_M15; // Timeframe for swing and ATR
input int              InpTrailSwingBars      = 2;        // Bars on each side to confirm a swing
input int              InpTrailATRPeriod      = 14;       // ATR period
input double           InpTrailATRMult        = 1.0;      // ATR multiplier
input int              InpTrailMinStepPoints  = 20;       // Ignore a trail tighter than this (points)
input int              InpTrailTelegramMinSec = 300;      // Min seconds between trail Telegram alerts

input group "Journal"
input string InpJournalFile         = "GoldAI_journal.csv"; // Written under MQL5/Files

input group "Telegram"
input bool   InpEnableTelegram      = true;              // EnableTelegram
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
input string InpNewsURL               = "https://raw.githubusercontent.com/rishijangid165/GoldAlgoManager/main/decisions/news.json"; // Static news list URL
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
CGoldAIJournal  g_journal;
GoldAIDecision  g_decision;

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
datetime        g_friday_flat_day    = 0;
datetime        g_last_trail_notify  = 0;
double          g_last_trail_sl      = 0.0;
string          g_friday_status      = "";
int             g_atr_handle         = INVALID_HANDLE;
int             g_atr_period         = 0;
ENUM_TIMEFRAMES g_atr_tf             = PERIOD_CURRENT;
string          g_last_tg_key        = "";
string          g_tg_decision_fp     = "";

datetime        g_day_start          = 0;
double          g_day_start_equity   = 0.0;
ulong           g_tp1_done_ticket    = 0;

// v1.03 news blackout state
GoldAINewsEvent g_news_cal[];
GoldAINewsEvent g_news_file[];
GoldAINewsEvent g_news[];
datetime        g_news_cal_at        = 0;
datetime        g_news_file_at       = 0;
string          g_news_cal_status    = "not loaded";
string          g_news_file_status   = "not loaded";
string          g_news_alert_key     = "";
datetime        g_news_alert_at      = 0;
string          g_news_last_summary  = "";

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
   return("GoldAI_" + IntegerToString(InpMagicNumber) + "_day");
  }

string GvDayEquityName()
  {
   return("GoldAI_" + IntegerToString(InpMagicNumber) + "_eq");
  }

string GvTp1Name()
  {
   return("GoldAI_" + IntegerToString(InpMagicNumber) + "_tp1");
  }

//+------------------------------------------------------------------+
string GoldAI_Truncate(const string text, const int max_chars)
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
   Print("GoldAI ", event, ": ", details);
   g_journal.Write(event,
                   0,
                   _Symbol,
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
   return("GoldAI_" + IntegerToString(InpMagicNumber) + "_tg_fp.txt");
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
      Print("GoldAI telegram: could not save decision fingerprint");
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
   const bool ok = GoldAI_TelegramSend(InpEnableTelegram,
                                       InpTelegramToken,
                                       InpTelegramChatId,
                                       InpWebTimeoutMs,
                                       text,
                                       status,
                                       err);
   if(ok)
     {
      Print("GoldAI telegram sent, WebRequest HTTP ", status);
      return(true);
     }
   if(err == "telegram disabled" || err == "telegram token or chat id is empty")
     {
      // Quiet when the feature is off or not configured.
      return(false);
     }
   Print("GoldAI telegram failed: ", err, " (WebRequest HTTP ", status, ")");
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
      Print("GoldAI new trading day (server). Start equity=",
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
   if(InpAllowRealAccount)
      return(false);
   return(!GoldAI_IsDemoAccount());
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
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
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
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
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
      return(GOLD_AI_BIAS_NONE);
   const long type = PositionGetInteger(POSITION_TYPE);
   if(type == POSITION_TYPE_BUY)
      return(GOLD_AI_BIAS_BUY);
   if(type == POSITION_TYPE_SELL)
      return(GOLD_AI_BIAS_SELL);
   return(GOLD_AI_BIAS_NONE);
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
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if(!g_trade.PositionClose(ticket))
        {
         Print("GoldAI close failed ticket=", ticket,
               " ret=", g_trade.ResultRetcode(),
               " ", g_trade.ResultRetcodeDescription());
        }
      else
        {
         Print("GoldAI closed ticket=", ticket, " reason=", reason);
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
   const string headers = "User-Agent: MetaTrader5-GoldAIBridge/1.00\r\nCache-Control: no-cache\r\n";
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
                            "GoldAI error: WebRequest failure\n" + g_poll_status);
         return(false);
        }
     }

   g_last_http = status;
   GoldAIDecision fresh;
   if(!GoldAI_DecisionParse(body, fresh))
     {
      g_poll_status = "PARSE FAIL: " + fresh.parse_error;
      g_last_poll   = TimeGMT();
      LogUnique("PARSE_ERROR", g_poll_status);
      return(false);
     }

   const string fp = GoldAI_DecisionFingerprint(fresh);
   const bool changed = (fp != g_last_fingerprint);
   g_decision       = fresh;
   g_have_decision  = true;
   g_last_poll      = TimeGMT();
   g_poll_status    = InpUseLocalFile ? "OK (local file)" : "OK";

   if(changed)
     {
      g_last_fingerprint = fp;
      g_last_reject      = "";
      Print("GoldAI new decision: ", fp, " | ", fresh.rationale);
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
         string msg = "GoldAI new decision\nBias: " + fresh.bias_text +
                      "\nZone: " + DoubleToString(fresh.zone_low, _Digits) +
                      " - " + DoubleToString(fresh.zone_high, _Digits) +
                      "\nSL: " + DoubleToString(fresh.stop_loss, _Digits) +
                      "  TP1: " + DoubleToString(fresh.tp1, _Digits) +
                      "  TP2: " + DoubleToString(fresh.tp2, _Digits);
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
//| Friday auto-close and post-TP1 trailing                            |
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
//| Last trade-session end on Friday, in seconds from midnight.      |
//| 86400 means the session runs to Friday 24:00 / Saturday 00:00.   |
//+------------------------------------------------------------------+
int FridaySessionEndSeconds()
  {
   int last = -1;
   for(uint i = 0; i < 8; i++)
     {
      datetime from = 0;
      datetime to   = 0;
      if(!SymbolInfoSessionTrade(_Symbol, FRIDAY, i, from, to))
         break;
      int sec = (int)to;
      if(sec >= 86400)
         sec = 86400;
      else
         sec = (int)(to % 86400);
      if(sec == 0 && from < to)
         sec = 86400;
      if(sec > last)
         last = sec;
     }
   if(last <= 0)
      last = 86400;
   return(last);
  }

//+------------------------------------------------------------------+
int FridayFlattenSeconds()
  {
   if(InpFridayCloseHHMM > 0)
     {
      const int hh = InpFridayCloseHHMM / 100;
      const int mm = InpFridayCloseHHMM % 100;
      if(hh >= 0 && hh <= 23 && mm >= 0 && mm <= 59)
         return(hh * 3600 + mm * 60);
     }
   int end = FridaySessionEndSeconds();
   int flat = end - 45 * 60;
   if(flat < 0)
      flat = 0;
   return(flat);
  }

//+------------------------------------------------------------------+
string FormatHHMMSS(const int sec_in)
  {
   int sec = sec_in;
   if(sec >= 86400)
      return("24:00");
   if(sec < 0)
      sec = 0;
   const int hh = sec / 3600;
   const int mm = (sec % 3600) / 60;
   return(StringFormat("%02d:%02d", hh, mm));
  }

//+------------------------------------------------------------------+
bool IsFridayOrEarlySaturday(const datetime t, int &dow, int &nowsec)
  {
   MqlDateTime st;
   TimeToStruct(t, st);
   dow = st.day_of_week;
   nowsec = st.hour * 3600 + st.min * 60 + st.sec;
   if(dow == FRIDAY)
      return(true);
   // Catch-up window: early Saturday, before the weekly close has long passed.
   if(dow == SATURDAY && nowsec < 6 * 3600)
      return(true);
   return(false);
  }

//+------------------------------------------------------------------+
bool FridayEntriesBlocked()
  {
   if(!InpFridayCloseEnabled)
      return(false);
   const datetime now = TimeCurrent();
   int dow = 0, nowsec = 0;
   if(!IsFridayOrEarlySaturday(now, dow, nowsec))
      return(false);
   const int flatten = FridayFlattenSeconds();
   const int lead = (InpFridayNoEntryMinutes < 0 ? 0 : InpFridayNoEntryMinutes) * 60;
   int cutoff = flatten - lead;
   if(dow == SATURDAY)
      return(true);
   return(nowsec >= cutoff);
  }

//+------------------------------------------------------------------+
bool FridayFlattenDue()
  {
   if(!InpFridayCloseEnabled)
      return(false);
   const datetime now = TimeCurrent();
   int dow = 0, nowsec = 0;
   if(!IsFridayOrEarlySaturday(now, dow, nowsec))
      return(false);
   const datetime today = DayStartOf(now);
   const datetime friday_day = (dow == SATURDAY ? today - 86400 : today);
   if(g_friday_flat_day == friday_day)
      return(false);
   if(dow == SATURDAY)
      return(true);
   return(nowsec >= FridayFlattenSeconds());
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
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
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
         Print("GoldAI Friday close failed ticket=", ticket,
               " ret=", g_trade.ResultRetcode(),
               " ", g_trade.ResultRetcodeDescription());
        }
      else
        {
         closed++;
         Print("GoldAI Friday closed ticket=", ticket, " magic=", magic, " reason=", reason);
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
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;
      const long magic = OrderGetInteger(ORDER_MAGIC);
      const bool ours = (magic == InpMagicNumber);
      const bool manual = (include_manual && magic == 0);
      if(!ours && !manual)
         continue;
      if(!g_trade.OrderDelete(ticket))
         Print("GoldAI Friday pending-delete failed ticket=", ticket,
               " ", g_trade.ResultRetcodeDescription());
      else
        {
         removed++;
         Print("GoldAI Friday deleted pending ticket=", ticket, " magic=", magic);
        }
     }
   return(removed);
  }

//+------------------------------------------------------------------+
void ManageFridayClose()
  {
   g_friday_status = "";
   if(!InpFridayCloseEnabled)
      return;

   const int flatten = FridayFlattenSeconds();
   const int lead = (InpFridayNoEntryMinutes < 0 ? 0 : InpFridayNoEntryMinutes) * 60;
   int cutoff = flatten - lead;
   if(cutoff < 0)
      cutoff = 0;
   g_friday_status = "flatten " + FormatHHMMSS(flatten) +
                     (InpFridayCloseHHMM > 0 ? " (manual HHMM)" : " (auto, 45m before session end)") +
                     ", no entries after " + FormatHHMMSS(cutoff);

   if(FridayEntriesBlocked())
      g_friday_status += " | entries blocked";

   if(!FridayFlattenDue())
      return;

   const int closed  = ClosePositionsByMagicFilter(InpFridayCloseManual, "friday_auto_close");
   const int deleted = DeletePendingByMagicFilter(InpFridayCloseManual);
   MqlDateTime st;
   TimeToStruct(TimeCurrent(), st);
   const datetime today = DayStartOf(TimeCurrent());
   const datetime friday_day = (st.day_of_week == SATURDAY ? today - 86400 : today);
   g_friday_flat_day = friday_day;
   g_friday_status += " | flattened " + IntegerToString(closed) +
                      " pos, " + IntegerToString(deleted) + " pending";

   const string details = "flattened " + IntegerToString(closed) +
                          " positions, deleted " + IntegerToString(deleted) +
                          " pending; manual=" + (InpFridayCloseManual ? "yes" : "no");
   g_journal.Write("FRIDAY_CLOSE",
                   0,
                   _Symbol,
                   "",
                   0, 0, 0, 0, 0, 0, 0, 0,
                   "",
                   details);
   Print("GoldAI ", g_friday_status);
   if(closed > 0 || deleted > 0)
     {
      string msg = "GoldAI Friday auto-close\n";
      msg += "Closed positions: " + IntegerToString(closed) + "\n";
      msg += "Deleted pending: " + IntegerToString(deleted) + "\n";
      msg += "Manual (magic 0) included: " + (InpFridayCloseManual ? "yes" : "no") + "\n";
      msg += "New entries blocked until after the weekend.";
      const string key = "FRIDAY_CLOSE|" + TimeToString(friday_day, TIME_DATE);
      NotifyTelegramOnce(key, msg);
     }
  }

//+------------------------------------------------------------------+
double LastClosedSwing(const bool want_high)
  {
   const int side = (InpTrailSwingBars < 1 ? 1 : InpTrailSwingBars);
   const int need = side * 2 + 8;
   double buf[];
   ArraySetAsSeries(buf, true);
   const int copied = (want_high
                       ? CopyHigh(_Symbol, InpTrailTF, 1, need, buf)
                       : CopyLow(_Symbol, InpTrailTF, 1, need, buf));
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
   g_atr_handle = iATR(_Symbol, InpTrailTF, period);
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
   const double bid   = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double ask   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0 || bid <= 0.0 || ask <= 0.0)
      return;

   const int min_pts = GoldAI_StopsLevelPoints(_Symbol);
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

   candidate = GoldAI_NormalizePrice(_Symbol, candidate);

   // Must stay on the correct side of the market and respect StopsLevel.
   if(is_buy)
     {
      const double max_sl = GoldAI_NormalizePrice(_Symbol, bid - min_dist);
      if(candidate >= bid || (min_dist > 0.0 && candidate > max_sl))
         candidate = max_sl;
      if(candidate >= bid)
         return;
     }
   else
     {
      const double min_sl = GoldAI_NormalizePrice(_Symbol, ask + min_dist);
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
      Print("GoldAI trail modify failed ticket=", ticket,
            " ", g_trade.ResultRetcodeDescription());
      return;
     }

   g_last_trail_sl = candidate;
   Print("GoldAI trailed SL to ", DoubleToString(candidate, _Digits),
         " (", how, ") on ticket ", ticket);
   g_journal.Write("TRAIL",
                   ticket,
                   _Symbol,
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
      string msg = "GoldAI trailing stop\n";
      msg += (is_buy ? "BUY" : "SELL") + " ticket " + IntegerToString((long)ticket) + "\n";
      msg += "New SL: " + DoubleToString(candidate, _Digits);
      msg += "  (was " + DoubleToString(sl, _Digits) + ")\n";
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
      LogUnique("KILL", "kill_switch is true - flattening GoldAI positions");
      NotifyTelegramOnce("KILL", "GoldAI error: kill switch is ON - flattening positions");
      CloseOurPositions("kill_switch");
      return;
     }

   if(!InpCloseOnBiasFlip)
      return;

   const int open_bias = OurOpenBias();
   if(open_bias != GOLD_AI_BIAS_NONE && open_bias != g_decision.bias)
     {
      const string details = "open " + GoldAI_BiasText(open_bias) +
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
   const double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(ticket == g_tp1_done_ticket)
     {
      TrailOpenPosition(ticket);
      return;
     }
   if(!g_have_decision || !GoldAI_HasPartialTp(g_decision))
      return;

   const double tp1 = GoldAI_NormalizePrice(_Symbol, g_decision.tp1);
   bool hit = false;
   if(type == POSITION_TYPE_BUY && bid >= tp1)
      hit = true;
   if(type == POSITION_TYPE_SELL && ask <= tp1)
      hit = true;
   if(!hit)
      return;

   const double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double close_vol = GoldAI_NormalizeVolume(_Symbol, volume * InpTP1CloseFraction);
   if(close_vol > 0.0 && (volume - close_vol) < vmin - 1e-12)
      close_vol = 0.0; // would leave less than min lot - skip the partial

   if(close_vol > 0.0 && close_vol < volume)
     {
      if(!g_trade.PositionClosePartial(ticket, close_vol))
        {
         Print("GoldAI TP1 partial failed ticket=", ticket,
               " ", g_trade.ResultRetcodeDescription());
         return;
        }
      g_journal.Write("TP1_PARTIAL",
                      ticket,
                      _Symbol,
                      (type == POSITION_TYPE_BUY ? "BUY" : "SELL"),
                      close_vol,
                      (type == POSITION_TYPE_BUY ? bid : ask),
                      sl, g_decision.tp1, g_decision.tp2,
                      0.0,
                      g_decision.confidence,
                      g_decision.generated_at,
                      g_decision.rationale,
                      "closed fraction at TP1");
      Print("GoldAI TP1 partial close ", DoubleToString(close_vol, 4), " of ticket ", ticket);
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
   be = GoldAI_NormalizePrice(_Symbol, be);

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
      if(GoldAI_StopsAreValid(_Symbol, ot, cur_price, be, cur_tp, reason))
        {
         if(g_trade.PositionModify(ticket, be, cur_tp))
           {
            Print("GoldAI moved SL to breakeven ", DoubleToString(be, _Digits),
                  " on ticket ", ticket);
            g_journal.Write("BE_MOVE",
                            ticket,
                            _Symbol,
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
            Print("GoldAI BE modify failed ticket=", ticket,
                  " ", g_trade.ResultRetcodeDescription());
           }
        }
      else
         Print("GoldAI BE skip: ", reason);
     }

   PersistTp1(ticket);

   {
    const string side = (type == POSITION_TYPE_BUY ? "BUY" : "SELL");
    string msg = "GoldAI TP1 partial close + BE\n";
    msg += side + " ticket " + IntegerToString((long)ticket);
    if(close_vol > 0.0 && close_vol < volume)
       msg += "\nClosed: " + DoubleToString(close_vol, 4) + " lots";
    else
       msg += "\nPartial skipped (remainder would be below min lot)";
    msg += "\nSL moved to breakeven " + DoubleToString(be, _Digits);
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
      g_status = "BLOCKED: real account (AllowRealAccount is false)";
      LogUnique("REJECT", g_status);
      return;
     }
   if(g_paused)
     {
      g_status = "PAUSED via Telegram - no new entries (/resume to allow)";
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
   if(FridayEntriesBlocked())
     {
      g_status = "FRIDAY CLOSE: new entries blocked (" + g_friday_status + ")";
      return;
     }

   const datetime now = TimeGMT();
   if(GoldAI_DecisionIsStale(g_decision, now))
     {
      g_status = "STALE decision (valid_until " + GoldAI_TimeToIsoUtc(g_decision.valid_until) + ")";
      LogUnique("STALE", g_status);
      return;
     }

   string blackout_reason = "";
   if(GoldAI_InBlackout(g_decision, now, blackout_reason))
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
      NotifyTelegramOnce("DAILY_LOSS", "GoldAI error: daily loss stop\n" + g_status);
      return;
     }

   if(g_decision.bias == GOLD_AI_BIAS_NONE)
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

   const string expected = (InpExpectedSymbol == "" ? "XAUUSD" : InpExpectedSymbol);
   if(!GoldAI_SymbolsMatch(g_decision.symbol, _Symbol) ||
      !GoldAI_SymbolsMatch(expected, _Symbol))
     {
      g_status = "SYMBOL MISMATCH file=" + g_decision.symbol +
                 " chart=" + _Symbol + " expected=" + expected;
      LogUnique("SYMBOL_MISMATCH", g_status);
      return;
     }

   string geom = "";
   if(!GoldAI_DecisionGeometryOk(g_decision, geom))
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

   const int spread = GoldAI_CurrentSpreadPoints(_Symbol);
   if(InpMaxSpreadPoints > 0 && spread > InpMaxSpreadPoints)
     {
      g_status = "SPREAD " + IntegerToString(spread) +
                 " > max " + IntegerToString(InpMaxSpreadPoints) + " points";
      LogUnique("SPREAD", g_status);
      return;
     }

   const bool is_buy = (g_decision.bias == GOLD_AI_BIAS_BUY);
   const double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double entry_price = (is_buy ? ask : bid);

   if(!GoldAI_PriceInZone(g_decision, entry_price))
     {
      g_status = "WAITING for price to enter zone " +
                 DoubleToString(g_decision.zone_low, _Digits) + " - " +
                 DoubleToString(g_decision.zone_high, _Digits) +
                 " (now " + DoubleToString(entry_price, _Digits) + ")";
      return;
     }

   const ENUM_ORDER_TYPE otype = (is_buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const double sl = GoldAI_NormalizePrice(_Symbol, g_decision.stop_loss);
   const double tp = GoldAI_NormalizePrice(_Symbol, GoldAI_OrderTakeProfit(g_decision));

   string reason = "";
   if(!GoldAI_StopsAreValid(_Symbol, otype, entry_price, sl, tp, reason))
     {
      g_status = "STOPS REJECTED: " + reason;
      LogUnique("REJECT", g_status);
      return;
     }

   const double risk_pct   = EffectiveRiskPct();
   const double risk_money = AccountInfoDouble(ACCOUNT_EQUITY) * risk_pct / 100.0;
   const double lots = GoldAI_LotsForRisk(_Symbol, otype, entry_price, sl, risk_money, reason);
   if(lots <= 0.0)
     {
      g_status = "LOT SIZE REJECTED: " + reason;
      LogUnique("REJECT", g_status);
      return;
     }
   if(!GoldAI_EnoughMargin(_Symbol, otype, lots, entry_price, reason))
     {
      g_status = "MARGIN REJECTED: " + reason;
      LogUnique("REJECT", g_status);
      return;
     }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints((uint)(InpSlippagePoints < 0 ? 0 : InpSlippagePoints));
   g_trade.SetTypeFillingBySymbol(_Symbol);

   const string comment = GoldAI_Truncate("GoldAI|" + g_decision.bias_text, 31);
   bool sent = false;
   if(is_buy)
      sent = g_trade.Buy(lots, _Symbol, entry_price, sl, tp, comment);
   else
      sent = g_trade.Sell(lots, _Symbol, entry_price, sl, tp, comment);

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
              " @ " + DoubleToString(entry_price, _Digits) + " ticket=" + IntegerToString((long)ticket);
   Print("GoldAI ", g_status);
   NotifyTelegram("GoldAI " + g_decision.bias_text + " opened\nLots: " +
                  DoubleToString(lots, 4) +
                  "\nEntry: " + DoubleToString(entry_price, _Digits) +
                  "\nSL: " + DoubleToString(sl, _Digits) +
                  "\nTP: " + DoubleToString(g_decision.tp1, _Digits) +
                  " / " + DoubleToString(g_decision.tp2, _Digits) +
                  "\nTicket: " + IntegerToString((long)ticket));
   g_journal.Write("ENTRY",
                   ticket,
                   _Symbol,
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
void NewsCopy(GoldAINewsEvent &dst, const GoldAINewsEvent &src)
  {
   dst.event_utc = src.event_utc;
   dst.start_utc = src.start_utc;
   dst.end_utc   = src.end_utc;
   dst.name      = src.name;
   dst.source    = src.source;
  }

//+------------------------------------------------------------------+
void NewsMergeInto(GoldAINewsEvent &dst[], const GoldAINewsEvent &src[])
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
      if(k >= GOLD_AI_MAX_NEWS * 2)
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
   const int nx = GoldAI_NewsNext(g_news, TimeGMT());
   const string summary = "cal=" + IntegerToString(ArraySize(g_news_cal)) +
                          " file=" + IntegerToString(ArraySize(g_news_file)) +
                          " merged=" + IntegerToString(ArraySize(g_news)) +
                          (nx >= 0 ? (" next=" + GoldAI_NewsWindowText(g_news[nx])) : " next=none");
   if(summary != g_news_last_summary)
     {
      g_news_last_summary = summary;
      Print("GoldAI news windows: ", summary);
     }
  }

//+------------------------------------------------------------------+
string NewsCacheFileName()
  {
   return("GoldAI_" + IntegerToString(InpMagicNumber) + "_news_cache.json");
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
   const string headers = "User-Agent: MetaTrader5-GoldAIBridge/1.03\r\nCache-Control: no-cache\r\n";
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
   if(!InpNewsBlackoutEnabled)
      return;
   const datetime now = TimeGMT();
   const int interval = (InpNewsRefreshMinutes < 5 ? 5 : InpNewsRefreshMinutes) * 60;
   bool changed = false;

   if(InpNewsUseCalendar && (force || g_news_cal_at == 0 || (now - g_news_cal_at) >= interval))
     {
      g_news_cal_at = now;
      GoldAINewsEvent tmp[];
      string err = "";
      const int n = GoldAI_NewsFromCalendar(tmp,
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
         g_news_cal_status = "OK " + IntegerToString(ArraySize(g_news_cal));
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
         GoldAINewsEvent tmp[];
         string perr = "";
         const int n = GoldAI_NewsFromJson(tmp, body, InpNewsBlackoutBeforeMin, InpNewsBlackoutAfterMin, perr);
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
   if(!GoldAI_NewsActive(g_news, TimeGMT(), idx))
      return(false);
   why = GoldAI_NewsWindowText(g_news[idx]);
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
   NotifyTelegram("GoldAI entry blocked by news\nDecision: " +
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
   if(GoldAI_NewsActive(g_news, now, idx))
      return("BLOCKING " + GoldAI_NewsWindowText(g_news[idx]));
   const int nx = GoldAI_NewsNext(g_news, now);
   if(nx < 0)
      return("no window loaded");
   return("next " + GoldAI_NewsWindowText(g_news[nx]));
  }

//+------------------------------------------------------------------+
//| v1.03 Telegram commands                                           |
//+------------------------------------------------------------------+
string GvPausedName()
  {
   return("GoldAI_" + IntegerToString(InpMagicNumber) + "_paused");
  }

//+------------------------------------------------------------------+
string TgOffsetFileName()
  {
   return("GoldAI_" + IntegerToString(InpMagicNumber) + "_tg_offset.txt");
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
   const bool ok = GoldAI_TelegramSend(InpEnableTelegram, InpTelegramToken, InpTgAllowedChatId,
                                       InpWebTimeoutMs, text, status, err);
   if(!ok)
      Print("GoldAI telegram reply failed: ", err, " (HTTP ", status, ")");
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
         Print("GoldAI telegram /closeall closed ticket=", ticket);
         if(g_tp1_done_ticket == ticket)
            PersistTp1(0);
        }
      else
        {
         failed++;
         Print("GoldAI telegram /closeall failed ticket=", ticket,
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
   const int digits = _Digits;
   string t = "GoldAI v1.03 status\n";
   t += "Account: " + GoldAI_AccountModeText() + "\n";
   t += "Balance: $" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) +
        "  Equity: $" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";
   t += "Day P/L: " + DoubleToString(-DailyLossPct(), 2) + "% (cap -" + DoubleToString(InpMaxDailyLossPct, 2) + "%)\n";
   t += "Entries: " + (g_paused ? "PAUSED (/resume)" : "allowed") + "\n";
   t += "EA state: " + GoldAI_Truncate(g_status, 160) + "\n";

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
      if(g_decision.bias != GOLD_AI_BIAS_NONE)
         t += "\nZone " + DoubleToString(g_decision.zone_low, digits) + "-" + DoubleToString(g_decision.zone_high, digits) +
              " SL " + DoubleToString(g_decision.stop_loss, digits) +
              " TP1 " + DoubleToString(g_decision.tp1, digits) +
              " TP2 " + DoubleToString(g_decision.tp2, digits);
      t += "\nValid until " + GoldAI_TimeToIsoUtc(g_decision.valid_until) +
           (g_decision.kill_switch ? "  KILL SWITCH ON" : "") + "\n";
     }
   else
      t += "Decision: none loaded (" + g_poll_status + ")\n";

   t += "News: " + NewsPanelText() + "\n";
   if(InpNewsBlackoutEnabled)
      t += "News sources: calendar " + g_news_cal_status + ", file " + g_news_file_status + "\n";
   t += "Friday close: " + (InpFridayCloseEnabled ? (g_friday_status == "" ? "armed" : g_friday_status) : "off");
   return(t);
  }

//+------------------------------------------------------------------+
string HelpText()
  {
   return("GoldAI commands:\n" +
          "/status - balance, equity, EA positions, decision, next news window\n" +
          "/pause - stop NEW entries (open trades still managed)\n" +
          "/resume - allow new entries again\n" +
          "/closeall - close ONLY EA positions (magic " + IntegerToString(InpMagicNumber) + "), needs /confirm <code> within " +
          IntegerToString(InpTgConfirmSeconds) + "s\n" +
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

   Print("GoldAI telegram command: ", cmd);
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
   if(cmd == "/pause")
     {
      SetPaused(true);
      UpdatePanel(true);
      TgReply("GoldAI: new entries PAUSED. Open EA trades are still managed (SL/TP/trail/Friday close). Send /resume to allow entries.");
      return;
     }
   if(cmd == "/resume")
     {
      SetPaused(false);
      UpdatePanel(true);
      TgReply("GoldAI: new entries ALLOWED again. All risk rules, news blackout and Friday cutoff still apply.");
      return;
     }
   if(cmd == "/closeall")
     {
      const int np_ = CountEaPositionsAnySymbol();
      const int no_ = CountEaPendingAnySymbol();
      if(np_ == 0 && no_ == 0)
        {
         g_confirm_code = "";
         TgReply("GoldAI: no open EA positions or orders (magic " + IntegerToString(InpMagicNumber) + "). Nothing to close.");
         return;
        }
      g_confirm_code  = IntegerToString(1000 + MathRand() % 9000);
      g_confirm_until = now + (InpTgConfirmSeconds < 10 ? 10 : InpTgConfirmSeconds);
      TgReply("GoldAI: close " + IntegerToString(np_) + " EA position(s) and " + IntegerToString(no_) +
              " EA order(s)? Manual trades are NOT touched.\nReply /confirm " + g_confirm_code +
              " within " + IntegerToString((int)(g_confirm_until - now)) + "s.");
      return;
     }
   if(cmd == "/confirm")
     {
      if(g_confirm_code == "" || now > g_confirm_until)
        {
         g_confirm_code = "";
         TgReply("GoldAI: no pending /closeall, or the code expired. Nothing closed.");
         return;
        }
      if(arg != g_confirm_code)
        {
         g_confirm_code = "";
         TgReply("GoldAI: wrong code. Nothing closed. Send /closeall again.");
         return;
        }
      g_confirm_code = "";
      const string res = CloseAllEaPositions();
      UpdatePanel(true);
      TgReply("GoldAI /closeall done: " + res + ".\nNew entries are " + (g_paused ? "PAUSED" : "still allowed (send /pause to stop them)") + ".");
      return;
     }
   TgReply("GoldAI: unknown command. Send /help");
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

   string body = "timeout=0&limit=20&allowed_updates=" + GoldAI_UrlEncode("[\"message\"]");
   if(g_tg_offset > 0)
      body += "&offset=" + IntegerToString(g_tg_offset);
   string resp = "", err = "";
   int status = 0;
   if(!GoldAI_TelegramCall(InpTelegramToken, "getUpdates", body,
                           (InpTgPollTimeoutMs < 500 ? 500 : InpTgPollTimeoutMs),
                           resp, status, err))
     {
      // Throttle: log a given error at most every 10 minutes.
      if(err != g_tg_last_err || (now - g_tg_last_err_at) >= 600)
        {
         g_tg_last_err    = err;
         g_tg_last_err_at = now;
         Print("GoldAI telegram getUpdates failed: ", err,
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
         Print("GoldAI telegram: ignored an update from a non-allowed chat");
         continue;
        }
      const long msg_date = (long)JsonGetNumberDef(msg, "date", 0.0);
      if(msg_date > 0 && msg_date < (long)g_start_gmt - 5)
        {
         Print("GoldAI telegram: ignored a command sent before this EA start");
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

   const int digits = _Digits;
   string lines = "";
   lines += "======= GoldAI Bridge v1.03 =======\n";
   lines += "Account:  " + GoldAI_AccountModeText() +
            "  #" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) +
            "  " + AccountInfoString(ACCOUNT_CURRENCY) + "\n";
   lines += "Symbol:   " + _Symbol +
            "  (expect " + InpExpectedSymbol + ")\n";
   lines += "Spread:   " + IntegerToString(GoldAI_CurrentSpreadPoints(_Symbol)) +
            " points  (max " + IntegerToString(InpMaxSpreadPoints) + ")\n";
   lines += "Server:   " + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS) +
            "   GMT " + GoldAI_TimeToIsoUtc(now) + "\n";
   lines += "--- Decision ---\n";
   lines += "Poll:     " + (g_last_poll > 0 ? GoldAI_TimeToIsoUtc(g_last_poll) : "never") +
            "  " + g_poll_status + "\n";

   if(g_have_decision && g_decision.loaded)
     {
      lines += "Valid:    until " + GoldAI_TimeToIsoUtc(g_decision.valid_until) +
               "  (" + GoldAI_TimeLeftText(g_decision.valid_until) + ")\n";
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
      const bool in_bl = GoldAI_InBlackout(g_decision, now, br);
      lines += "Blackout: " + (in_bl ? ("YES " + br) : "no") + "\n";
      lines += "Why:      " + GoldAI_Truncate(g_decision.rationale, 90) + "\n";
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
   if(InpFridayCloseEnabled)
      lines += "Friday:   " + (g_friday_status == "" ? "armed" : g_friday_status) + "\n";
   else
      lines += "Friday:   off\n";
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

   if(g_trade_locked)
      lines += "LOCK:     " + g_lock_reason + "\n";

   Comment(lines);
  }

//+------------------------------------------------------------------+
void ManageAndMaybeEnter()
  {
   RefreshDailyWindow();
   ManageFridayClose();
   EnforceDecisionOnOpenTrade();
   ManageOpenPosition();
   TryOpenTrade();
   UpdatePanel(false);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   GoldAI_DecisionClear(g_decision);
   g_have_decision = false;
   g_first_timer   = true;
   g_poll_status   = "not polled yet";
   g_status        = "initializing";

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints((uint)(InpSlippagePoints < 0 ? 0 : InpSlippagePoints));
   g_trade.SetAsyncMode(false);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   if(!g_journal.Init(InpJournalFile))
      Print("GoldAI warning: journal file could not be prepared");

   LoadPersistedState();
   RefreshDailyWindow();

   g_start_gmt = TimeGMT();
   MathSrand((uint)(GetTickCount() ^ (uint)TimeLocal()));
   g_paused = (GlobalVariableCheck(GvPausedName()) && GlobalVariableGet(GvPausedName()) > 0.5);
   if(g_paused)
      Print("GoldAI: entries are PAUSED (persisted from Telegram /pause). Send /resume to allow.");
   LoadTgOffset();
   g_news_cal_at  = 0;
   g_news_file_at = 0;
   g_last_manage  = 0;

   if(RealAccountBlocked())
     {
      g_trade_locked = true;
      g_lock_reason  = "REAL account is blocked. Run on DEMO, or set AllowRealAccount=true (unsafe).";
      Print("GoldAI ", g_lock_reason);
     }

   if(InpPollMinutes < 1)
      Print("GoldAI: PollMinutes < 1 is not allowed; will use 1 minute");

   if(!InpUseLocalFile)
     {
      string url = InpDecisionURL;
      StringTrimLeft(url);
      StringTrimRight(url);
      if(url == "" || StringFind(url, "USER/REPO") >= 0)
         Print("GoldAI: DecisionURL is still the placeholder. Set a real raw HTTPS URL, ",
               "or enable UseLocalFile and place current.json in MQL5/Files. See SETUP.md.");
     }

   if(!EventSetTimer(1))
     {
      Print("GoldAI: EventSetTimer failed - will poll from OnTick as a fallback");
     }

   g_journal.Write("START",
                   0,
                   _Symbol,
                   "",
                   0, 0, 0, 0, 0, 0, 0, 0,
                   "",
                   "EA attached, account=" + GoldAI_AccountModeText());

   LoadTelegramState();
   if(InpEnableTelegram)
     {
      int st = 0;
      string terr = "";
      const bool sent = GoldAI_TelegramSend(true,
                                            InpTelegramToken,
                                            InpTelegramChatId,
                                            InpWebTimeoutMs,
                                            "GoldAIBridge online (v1.03). Send /help for commands.",
                                            st,
                                            terr);
      if(sent)
         Print("GoldAI telegram startup test sent, WebRequest HTTP ", st);
      else
         Print("GoldAI telegram startup test failed: ", terr, " (WebRequest HTTP ", st, ")");
     }
   else
      Print("GoldAI telegram disabled (EnableTelegram=false)");

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
   Comment("");
   Print("GoldAI stopped, reason=", reason);
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
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol)
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
                   _Symbol,
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
   Print("GoldAI EXIT ticket=", ticket, " pnl=", DoubleToString(profit, 2), " ", details);
   {
    const long deal_reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
    const string reason_txt = GoldAI_DealCloseReason(deal_reason, pending_reason);
    const double net = GoldAI_PositionNetPnl(pos_id, profit);
    string pnl_txt = DoubleToString(net, 2);
    if(net > 0.0)
       pnl_txt = "+" + pnl_txt;
    NotifyTelegram("GoldAI position closed\nReason: " + reason_txt +
                   "\nP&L: $" + pnl_txt +
                   "\nTicket: " + IntegerToString((long)ticket));
   }
   if(g_tp1_done_ticket != 0)
      PersistTp1(0);
   UpdatePanel(true);
  }

//+------------------------------------------------------------------+

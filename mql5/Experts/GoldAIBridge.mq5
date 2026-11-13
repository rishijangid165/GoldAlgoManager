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
#property version     "1.00"
#property description "AI-directed gold EA. Polls a decision JSON and trades only inside the AI zone."
#property description "Hard risk rules (risk %, daily loss, spread, max trades, demo lock) stay in the EA."
#property description "DEMO only unless AllowRealAccount is explicitly enabled. See SETUP.md."

#include <Trade\Trade.mqh>
#include <GoldAIDecision.mqh>
#include <GoldAIJournal.mqh>

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

input group "Journal"
input string InpJournalFile         = "GoldAI_journal.csv"; // Written under MQL5/Files

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

datetime        g_day_start          = 0;
double          g_day_start_equity   = 0.0;
ulong           g_tp1_done_ticket    = 0;

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

   if(!g_have_decision || !GoldAI_HasPartialTp(g_decision))
      return;
   if(ticket == g_tp1_done_ticket)
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
void UpdatePanel(const bool force)
  {
   const datetime now = TimeGMT();
   if(!force && g_last_panel == now)
      return;
   g_last_panel = now;

   const int digits = _Digits;
   string lines = "";
   lines += "======= GoldAI Bridge v1.00 =======\n";
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

   if(g_trade_locked)
      lines += "LOCK:     " + g_lock_reason + "\n";

   Comment(lines);
  }

//+------------------------------------------------------------------+
void ManageAndMaybeEnter()
  {
   RefreshDailyWindow();
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

   UpdatePanel(true);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
   Print("GoldAI stopped, reason=", reason);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   PollDecision();
   ManageAndMaybeEnter();
   if(g_first_timer)
     {
      g_first_timer = false;
      EventKillTimer();
      const int minutes = (InpPollMinutes < 1 ? 1 : InpPollMinutes);
      if(!EventSetTimer(minutes * 60))
         Print("GoldAI: could not arm the ", minutes, "-minute poll timer");
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

   string details = g_pending_exit_reason;
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
   if(g_tp1_done_ticket != 0)
      PersistTp1(0);
   UpdatePanel(true);
  }

//+------------------------------------------------------------------+

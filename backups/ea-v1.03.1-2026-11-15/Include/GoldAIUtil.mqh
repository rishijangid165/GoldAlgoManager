//+------------------------------------------------------------------+
//| GoldAIUtil.mqh                                                   |
//| Time, symbol, volume, and price helpers for GoldAIBridge.        |
//+------------------------------------------------------------------+
#ifndef GOLD_AI_UTIL_MQH
#define GOLD_AI_UTIL_MQH

//+------------------------------------------------------------------+
//| Parse an ISO-8601 timestamp as UTC.                              |
//| Accepts: 2026-11-13T06:30:00Z                                    |
//|          2026-11-13T06:30:00.000Z                                |
//|          2026-11-13T06:30:00+00:00                               |
//|          2026-11-13T12:00:00+05:30  (offset is applied)          |
//|          2026-11-13 06:30:00   (treated as UTC)                  |
//| The returned datetime has those UTC clock components, so it      |
//| can be compared directly with TimeGMT().                         |
//| Returns 0 on failure.                                            |
//+------------------------------------------------------------------+
datetime GoldAI_ParseIsoUtc(const string iso)
  {
   string s = iso;
   StringTrimLeft(s);
   StringTrimRight(s);
   if(StringLen(s) < 8)
      return(0);

   StringReplace(s, "T", " ");
   StringReplace(s, "t", " ");

   int offset_sec = 0;
   bool has_offset = false;

   // Trailing Z / z means UTC
   const int len0 = StringLen(s);
   if(len0 > 0)
     {
      const ushort last = StringGetCharacter(s, len0 - 1);
      if(last == 'Z' || last == 'z')
        {
         s = StringSubstr(s, 0, len0 - 1);
         has_offset = true;
         offset_sec = 0;
        }
     }

   // Timezone offset +HH:MM or -HH:MM (or +HHMM) after the time
   if(!has_offset)
     {
      const int space = StringFind(s, " ");
      int search_from = (space >= 0 ? space + 1 : 0);
      int plus = StringFind(s, "+", search_from);
      int minus = -1;
      // Look for a '-' that starts the offset, not the date separators
      // After we replace T with space, date is YYYY-MM-DD or will be dotted.
      // Find the last '-' or '+' after the date part.
      for(int i = StringLen(s) - 1; i > 10; i--)
        {
         const ushort c = StringGetCharacter(s, i);
         if(c == '+')
           {
            plus = i;
            break;
           }
         if(c == '-')
           {
            // A date dash would be at positions 4 and 7 (0-based) if
            // still hyphenated. An offset dash sits after the time,
            // usually around index 19.
            minus = i;
            break;
           }
        }

      int sign_pos = -1;
      int sign = 1;
      if(plus >= 10)
        {
         sign_pos = plus;
         sign = 1;
        }
      else if(minus >= 11)
        {
         sign_pos = minus;
         sign = -1;
        }

      if(sign_pos >= 0)
        {
         string off = StringSubstr(s, sign_pos + 1);
         s = StringSubstr(s, 0, sign_pos);
         StringReplace(off, ":", "");
         // off is HHMM or HH
         int hh = 0;
         int mm = 0;
         const int ol = StringLen(off);
         if(ol >= 2)
            hh = (int)StringToInteger(StringSubstr(off, 0, 2));
         if(ol >= 4)
            mm = (int)StringToInteger(StringSubstr(off, 2, 2));
         offset_sec = sign * (hh * 3600 + mm * 60);
         has_offset = true;
        }
     }

   // Drop fractional seconds
   const int dot = StringFind(s, ".");
   if(dot >= 0)
      s = StringSubstr(s, 0, dot);

   StringTrimLeft(s);
   StringTrimRight(s);
   StringReplace(s, "-", ".");
   StringReplace(s, "/", ".");

   // StringToTime wants "yyyy.mm.dd hh:mi" or "yyyy.mm.dd hh:mi:ss"
   datetime wall = StringToTime(s);
   if(wall <= 0)
      return(0);

   // wall is the clock components encoded as a Unix-like datetime.
   // If the original had a +05:30 offset, those components are local
   // to that zone, so subtract the offset to reach UTC components.
   if(has_offset)
      wall -= offset_sec;
   return(wall);
  }

//+------------------------------------------------------------------+
string GoldAI_TimeToIsoUtc(const datetime gmt)
  {
   if(gmt <= 0)
      return("");
   string s = TimeToString(gmt, TIME_DATE | TIME_SECONDS);
   // yyyy.mm.dd hh:mi:ss  ->  yyyy-mm-ddThh:mi:ssZ
   StringReplace(s, ".", "-");
   StringReplace(s, " ", "T");
   return(s + "Z");
  }

//+------------------------------------------------------------------+
string GoldAI_KeepAlnumUpper(const string src)
  {
   string s = src;
   StringToUpper(s);
   string out = "";
   const int n = StringLen(s);
   for(int i = 0; i < n; i++)
     {
      const ushort c = StringGetCharacter(s, i);
      const bool letter = (c >= 'A' && c <= 'Z');
      const bool digit  = (c >= '0' && c <= '9');
      if(letter || digit)
         out += ShortToString(c);
     }
   return(out);
  }

//+------------------------------------------------------------------+
//| Strip common broker suffixes after a known gold base.            |
//+------------------------------------------------------------------+
string GoldAI_CanonicalSymbol(const string symbol)
  {
   string s = GoldAI_KeepAlnumUpper(symbol);

   // Known trailing tokens that brokers append
   string suffixes[] = {"MICRO","MINI","ECN","PRO","RAW","PRIME","MAX","MIN","STD","VIP","CENTCENT","CENT","CENTS"};
   for(int i = 0; i < ArraySize(suffixes); i++)
     {
      const int sl = StringLen(suffixes[i]);
      const int n  = StringLen(s);
      if(n > sl && StringSubstr(s, n - sl, sl) == suffixes[i])
         s = StringSubstr(s, 0, n - sl);
     }

   // Single-letter / short suffixes: M (micro), I, A, C, S
   string short_sfx[] = {"M","I","A","C","S"};
   string bases[] = {"XAUUSD","GOLD","XAU","XAUAUD","XAUGBP","XAUEUR"};
   for(int b = 0; b < ArraySize(bases); b++)
     {
      const int bl = StringLen(bases[b]);
      if(StringLen(s) > bl && StringSubstr(s, 0, bl) == bases[b])
        {
         const string rest = StringSubstr(s, bl);
         for(int k = 0; k < ArraySize(short_sfx); k++)
           {
            if(rest == short_sfx[k])
               return(bases[b]);
           }
        }
     }
   return(s);
  }

//+------------------------------------------------------------------+
bool GoldAI_IsGoldAlias(const string canonical)
  {
   return(canonical == "XAUUSD" || canonical == "GOLD" || canonical == "XAU");
  }

//+------------------------------------------------------------------+
//| True if the decision symbol and the chart symbol are the same    |
//| gold instrument (suffix / GOLD vs XAUUSD tolerant).              |
//+------------------------------------------------------------------+
bool GoldAI_SymbolsMatch(const string decision_symbol, const string chart_symbol)
  {
   const string a = GoldAI_CanonicalSymbol(decision_symbol);
   const string b = GoldAI_CanonicalSymbol(chart_symbol);
   if(a == "" || b == "")
      return(false);
   if(a == b)
      return(true);
   if(GoldAI_IsGoldAlias(a) && GoldAI_IsGoldAlias(b))
      return(true);
   return(false);
  }

//+------------------------------------------------------------------+
double GoldAI_NormalizePrice(const string symbol, const double price)
  {
   double tick = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0)
      tick = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(tick <= 0.0)
      return(price);
   const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   return(NormalizeDouble(MathRound(price / tick) * tick, digits));
  }

//+------------------------------------------------------------------+
//| Digits implied by a volume step (0.01 -> 2).                     |
//+------------------------------------------------------------------+
int GoldAI_VolumeDigits(const double step)
  {
   if(step >= 1.0)
      return(0);
   int digits = 0;
   double t = step;
   while(t < 1.0 - 1e-12 && digits < 8)
     {
      t *= 10.0;
      digits++;
     }
   return(digits);
  }

//+------------------------------------------------------------------+
//| Floor a volume to the symbol step. Returns 0 if below min.       |
//+------------------------------------------------------------------+
double GoldAI_NormalizeVolume(const string symbol, double volume)
  {
   const double vmin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double vmax = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0)
      step = 0.01;
   volume = MathFloor((volume / step) + 1e-12) * step;
   volume = NormalizeDouble(volume, GoldAI_VolumeDigits(step));
   if(volume < vmin - 1e-12)
      return(0.0);
   if(volume > vmax)
      volume = vmax;
   return(volume);
  }

//+------------------------------------------------------------------+
//| Lots from risk money and SL distance. Prefers OrderCalcProfit.   |
//| Returns 0 if the size cannot be computed safely.                 |
//+------------------------------------------------------------------+
double GoldAI_LotsForRisk(const string symbol,
                          const ENUM_ORDER_TYPE order_type,
                          const double entry_price,
                          const double stop_loss,
                          const double risk_money,
                          string &reason)
  {
   reason = "";
   const double sl_dist = MathAbs(entry_price - stop_loss);
   if(sl_dist <= 0.0 || risk_money <= 0.0)
     {
      reason = "invalid SL distance or risk money";
      return(0.0);
     }

   const double vmin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double loss_per_lot = 0.0;

   double profit = 0.0;
   if(OrderCalcProfit(order_type, symbol, 1.0, entry_price, stop_loss, profit) && profit != 0.0)
      loss_per_lot = MathAbs(profit);
   else
     {
      const double tick_size  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      const double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
      if(tick_size <= 0.0 || tick_value <= 0.0)
        {
         reason = "tick size/value unavailable and OrderCalcProfit failed";
         return(0.0);
        }
      loss_per_lot = (sl_dist / tick_size) * tick_value;
     }

   if(loss_per_lot <= 0.0)
     {
      reason = "could not estimate loss per lot";
      return(0.0);
     }

   double lots = GoldAI_NormalizeVolume(symbol, risk_money / loss_per_lot);
   if(lots <= 0.0)
     {
      reason = "risk size is below the broker minimum lot (" + DoubleToString(vmin, 3) + ")";
      return(0.0);
     }

   // If the floored lot would risk more than requested (should not, we floor),
   // still refuse if min lot itself exceeds the risk budget by a wide margin.
   double min_profit = 0.0;
   if(OrderCalcProfit(order_type, symbol, lots, entry_price, stop_loss, min_profit))
     {
      if(MathAbs(min_profit) > risk_money * 1.05)
        {
         reason = "even the computed lot exceeds the risk budget";
         return(0.0);
        }
     }
   return(lots);
  }

//+------------------------------------------------------------------+
bool GoldAI_EnoughMargin(const string symbol,
                         const ENUM_ORDER_TYPE order_type,
                         const double lots,
                         const double price,
                         string &reason)
  {
   reason = "";
   double margin = 0.0;
   if(!OrderCalcMargin(order_type, symbol, lots, price, margin))
     {
      reason = "OrderCalcMargin failed";
      return(false);
     }
   const double free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(margin > free)
     {
      reason = "not enough free margin";
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
int GoldAI_StopsLevelPoints(const string symbol)
  {
   int stops = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const int freeze = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   if(freeze > stops)
      stops = freeze;
   return(stops);
  }

//+------------------------------------------------------------------+
bool GoldAI_StopsAreValid(const string symbol,
                          const ENUM_ORDER_TYPE order_type,
                          const double entry,
                          const double sl,
                          const double tp,
                          string &reason)
  {
   reason = "";
   const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(point <= 0.0)
     {
      reason = "symbol point size is zero";
      return(false);
     }
   const int min_pts = GoldAI_StopsLevelPoints(symbol);
   const double min_dist = min_pts * point;

   if(sl != 0.0)
     {
      if(MathAbs(entry - sl) < min_dist)
        {
         reason = "SL closer than broker StopsLevel (" + IntegerToString(min_pts) + " points)";
         return(false);
        }
      if(order_type == ORDER_TYPE_BUY && sl >= entry)
        {
         reason = "BUY SL must be below entry";
         return(false);
        }
      if(order_type == ORDER_TYPE_SELL && sl <= entry)
        {
         reason = "SELL SL must be above entry";
         return(false);
        }
     }
   if(tp != 0.0)
     {
      if(MathAbs(tp - entry) < min_dist)
        {
         reason = "TP closer than broker StopsLevel (" + IntegerToString(min_pts) + " points)";
         return(false);
        }
      if(order_type == ORDER_TYPE_BUY && tp <= entry)
        {
         reason = "BUY TP must be above entry";
         return(false);
        }
      if(order_type == ORDER_TYPE_SELL && tp >= entry)
        {
         reason = "SELL TP must be below entry";
         return(false);
        }
     }
   return(true);
  }

//+------------------------------------------------------------------+
int GoldAI_CurrentSpreadPoints(const string symbol)
  {
   const double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   const double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(point <= 0.0)
      return(0);
   return((int)MathRound((ask - bid) / point));
  }

//+------------------------------------------------------------------+
bool GoldAI_IsDemoAccount()
  {
   const long mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   return(mode == ACCOUNT_TRADE_MODE_DEMO);
  }

//+------------------------------------------------------------------+
string GoldAI_AccountModeText()
  {
   const long mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(mode == ACCOUNT_TRADE_MODE_DEMO)
      return("DEMO");
   if(mode == ACCOUNT_TRADE_MODE_CONTEST)
      return("CONTEST");
   if(mode == ACCOUNT_TRADE_MODE_REAL)
      return("REAL");
   return("UNKNOWN");
  }

//+------------------------------------------------------------------+
//| Days / hours / minutes left until a UTC datetime.                |
//+------------------------------------------------------------------+
string GoldAI_TimeLeftText(const datetime until_utc)
  {
   const datetime now = TimeGMT();
   if(until_utc <= 0)
      return("n/a");
   if(until_utc <= now)
      return("EXPIRED");
   const long sec = (long)(until_utc - now);
   const long hrs = sec / 3600;
   const long mins = (sec % 3600) / 60;
   return(IntegerToString(hrs) + "h " + IntegerToString(mins) + "m left");
  }

#endif // GOLD_AI_UTIL_MQH
//+------------------------------------------------------------------+

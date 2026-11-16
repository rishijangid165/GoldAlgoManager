//+------------------------------------------------------------------+
//| BTCSymbolProbe.mq5 - READ-ONLY. Prints BTC symbol specs, spread  |
//| stats, ATR(14) H1 and the trade-session table to the Experts log  |
//| and MQL5/Files/BTCSymbolProbe.txt. Sends no orders.               |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version "1.00"
input string InpSymbol = "BTCUSD"; // Symbol to probe (variants are searched if missing)

string Find(const string want)
  {
   bool custom = false;
   if(SymbolExist(want, custom))
      return(want);
   string best = "";
   for(int i = 0; i < SymbolsTotal(false); i++)
     {
      string n = SymbolName(i, false);
      string u = n;
      StringToUpper(u);
      string p = SymbolInfoString(n, SYMBOL_PATH);
      StringToUpper(p);
      if(StringFind(p, "ETF") >= 0 || StringFind(p, "STOCK") >= 0 || StringFind(p, "NASDAQ") >= 0)
         continue;
      if(StringFind(u, "BTCUSD") == 0 || StringFind(u, "XBTUSD") == 0 || StringFind(u, "BITCOIN") == 0)
         if(best == "" || StringLen(n) < StringLen(best))
            best = n;
     }
   return(best);
  }

void OnStart()
  {
   string out = "server=" + AccountInfoString(ACCOUNT_SERVER) + " mode=" +
                (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" : "NOT-DEMO") + "\n";
   const string s = Find(InpSymbol);
   if(s == "")
     {
      out += "No BTCUSD-like symbol on this server.\n";
     }
   else
     {
      SymbolSelect(s, true);
      out += StringFormat("symbol=%s path=%s desc=%s base=%s profit=%s\n", s, SymbolInfoString(s, SYMBOL_PATH),
                          SymbolInfoString(s, SYMBOL_DESCRIPTION), SymbolInfoString(s, SYMBOL_CURRENCY_BASE),
                          SymbolInfoString(s, SYMBOL_CURRENCY_PROFIT));
      out += StringFormat("digits=%d point=%.8f contract=%.4f tick_size=%.8f tick_value=%.8f\n",
                          (int)SymbolInfoInteger(s, SYMBOL_DIGITS), SymbolInfoDouble(s, SYMBOL_POINT),
                          SymbolInfoDouble(s, SYMBOL_TRADE_CONTRACT_SIZE), SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE),
                          SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE));
      out += StringFormat("vol_min=%.4f vol_step=%.4f vol_max=%.4f stops_level=%d freeze=%d trade_mode=%d\n",
                          SymbolInfoDouble(s, SYMBOL_VOLUME_MIN), SymbolInfoDouble(s, SYMBOL_VOLUME_STEP),
                          SymbolInfoDouble(s, SYMBOL_VOLUME_MAX), (int)SymbolInfoInteger(s, SYMBOL_TRADE_STOPS_LEVEL),
                          (int)SymbolInfoInteger(s, SYMBOL_TRADE_FREEZE_LEVEL), (int)SymbolInfoInteger(s, SYMBOL_TRADE_MODE));
      out += StringFormat("spread_now=%d pts bid=%.2f ask=%.2f\n", (int)SymbolInfoInteger(s, SYMBOL_SPREAD),
                          SymbolInfoDouble(s, SYMBOL_BID), SymbolInfoDouble(s, SYMBOL_ASK));
      MqlRates r[];
      const int n = CopyRates(s, PERIOD_H1, 0, 500, r);
      if(n > 20)
        {
         int sp[];
         ArrayResize(sp, n);
         for(int i = 0; i < n; i++)
            sp[i] = r[i].spread;
         ArraySort(sp);
         double tr = 0;
         for(int i = n - 15; i < n - 1; i++)
            tr += MathMax(r[i].high - r[i].low, MathMax(MathAbs(r[i].high - r[i - 1].close), MathAbs(r[i].low - r[i - 1].close)));
         out += StringFormat("H1 spread pts (n=%d): min=%d median=%d p90=%d max=%d | ATR14 H1~%.2f\n",
                             n, sp[0], sp[n / 2], sp[(int)(n * 0.9)], sp[n - 1], tr / 14.0);
        }
      string days[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
      for(int d = 0; d < 7; d++)
        {
         string line = days[d] + ":";
         for(uint i = 0; i < 10; i++)
           {
            datetime f = 0, t = 0;
            if(!SymbolInfoSessionTrade(s, (ENUM_DAY_OF_WEEK)d, i, f, t))
               break;
            line += StringFormat(" %02d:%02d-%02d:%02d", (int)f / 3600, ((int)f % 3600) / 60, (int)t / 3600, ((int)t % 3600) / 60);
           }
         out += line + "\n";
        }
     }
   Print(out);
   const int h = FileOpen("BTCSymbolProbe.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE)
     {
      FileWriteString(h, out);
      FileClose(h);
     }
  }

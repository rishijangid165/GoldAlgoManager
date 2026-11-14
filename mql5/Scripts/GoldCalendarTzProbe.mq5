//+------------------------------------------------------------------+
//| GoldCalendarTzProbe.mq5 - read-only: how are calendar times      |
//| expressed? Logs clocks + raw calendar times over ~30 s.          |
//+------------------------------------------------------------------+
#property version "1.00"
void OnStart()
  {
   string out = "";
   for(int k = 0; k < 8; k++)
     {
      MqlCalendarValue v[];
      const int n = CalendarValueHistory(v, D'2026.11.16 00:00', D'2026.11.19 23:59', NULL, "USD");
      string rs = "", fm = "";
      for(int i = 0; i < n; i++)
        {
         MqlCalendarEvent ev;
         if(!CalendarEventById(v[i].event_id, ev)) continue;
         if(ev.name == "Retail Sales m/m") rs = TimeToString(v[i].time, TIME_DATE | TIME_MINUTES);
         if(ev.name == "FOMC Minutes") fm = TimeToString(v[i].time, TIME_DATE | TIME_MINUTES);
        }
      out += StringFormat("k=%d conn=%d local=%s gmt=%s tradeserver=%s current=%s gmtoffset=%d dst=%d | raw RetailSales=%s FOMCMinutes=%s\n",
                          k, (int)TerminalInfoInteger(TERMINAL_CONNECTED),
                          TimeToString(TimeLocal(), TIME_SECONDS), TimeToString(TimeGMT(), TIME_SECONDS),
                          TimeToString(TimeTradeServer(), TIME_SECONDS), TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
                          TimeGMTOffset(), TimeDaylightSavings(), rs, fm);
      Sleep(4000);
     }
   Print(out);
   const int h = FileOpen("GoldCalendarTzProbe.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE) { FileWriteString(h, out); FileClose(h); }
  }

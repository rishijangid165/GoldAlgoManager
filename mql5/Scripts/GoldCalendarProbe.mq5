//+------------------------------------------------------------------+
//| GoldCalendarProbe.mq5                                            |
//| Read-only probe: does the MT5 Economic Calendar return USD HIGH  |
//| events on this terminal? Writes MQL5/Files/GoldCalendarProbe.txt |
//| No trading calls.                                                |
//+------------------------------------------------------------------+
#property script_show_inputs false
#property version "1.00"

void OnStart()
  {
   const int h = FileOpen("GoldCalendarProbe.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   string out = "";
   out += "build=" + IntegerToString(TerminalInfoInteger(TERMINAL_BUILD)) +
          " connected=" + IntegerToString(TerminalInfoInteger(TERMINAL_CONNECTED)) +
          " server=" + AccountInfoString(ACCOUNT_SERVER) +
          " gmt=" + TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) +
          " servertime=" + TimeToString(TimeTradeServer(), TIME_DATE | TIME_SECONDS) + "\n";

   MqlCalendarEvent events[];
   ResetLastError();
   const int ne = CalendarEventByCountry("US", events);
   out += "CalendarEventByCountry(US)=" + IntegerToString(ne) + " err=" + IntegerToString(GetLastError()) + "\n";
   int high = 0;
   for(int i = 0; i < ne; i++)
      if(events[i].importance == CALENDAR_IMPORTANCE_HIGH)
        {
         high++;
         if(high <= 60)
            out += "  HIGH event id=" + IntegerToString((long)events[i].id) + " " + events[i].name + "\n";
        }
   out += "high_events=" + IntegerToString(high) + "\n";

   MqlCalendarValue values[];
   const datetime from = TimeTradeServer() - 2 * 86400;
   const datetime to   = TimeTradeServer() + 50 * 86400;
   ResetLastError();
   const int nv = CalendarValueHistory(values, from, to, NULL, "USD");
   out += "CalendarValueHistory(USD, -2d..+50d)=" + IntegerToString(nv) + " err=" + IntegerToString(GetLastError()) + "\n";
   int shown = 0;
   for(int i = 0; i < nv; i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev))
         continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH)
         continue;
      shown++;
      out += "  " + TimeToString(values[i].time, TIME_DATE | TIME_MINUTES) + " (server) " + ev.name + "\n";
     }
   out += "high_values=" + IntegerToString(shown) + "\n";
   Print(out);
   if(h != INVALID_HANDLE)
     {
      FileWriteString(h, out);
      FileClose(h);
     }
  }

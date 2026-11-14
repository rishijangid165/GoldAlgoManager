//+------------------------------------------------------------------+
//| GoldNewsSelfTest.mq5 - read-only self-test for v1.03 helpers.    |
//| Loads MT5 calendar windows + MQL5/Files/news.json, prints the    |
//| merged list, and parses a canned getUpdates payload. No trading, |
//| no network calls.                                                |
//+------------------------------------------------------------------+
#property version "1.00"
#include <GoldAINews.mqh>

void OnStart()
  {
   string out = "";
   GoldAINewsEvent cal[];
   string err = "";
   for(int pass = 0; pass < 2; pass++)
     {
      if(pass == 1)
         Sleep(10000);
      ArrayResize(cal, 0);
      out += "--- calendar pass " + IntegerToString(pass) + " connected=" + IntegerToString(TerminalInfoInteger(TERMINAL_CONNECTED)) +
             " tradeserver=" + TimeToString(TimeTradeServer(), TIME_SECONDS) + " gmt=" + TimeToString(TimeGMT(), TIME_SECONDS) + "\n";
      const int nc = GoldAI_NewsFromCalendar(cal,
         "Nonfarm Payrolls;Unemployment Rate;Average Hourly Earnings;CPI;PCE;GDP;PPI;Retail Sales;Fed Interest Rate Decision;FOMC Minutes;FOMC Meeting Minutes;FOMC Press Conference;FOMC Statement;FOMC Economic Projections;Fed Chair",
         2, false, 30, 90, 50, err);
      out += "calendar added=" + IntegerToString(nc) + " err=" + err + " server-clock offset=" + IntegerToString(GoldAI_ServerGmtOffset()) + " | " + g_GoldAI_cal_tz_info + "\n";
      out += "UsDst 2026-11-17=" + (string)GoldAI_UsDst(D'2026.11.17 13:30') + " 2026-07-01=" + (string)GoldAI_UsDst(D'2026.07.01 12:00') +
             " 2026-03-08 06:59Z=" + (string)GoldAI_UsDst(D'2026.03.08 06:59') + " 07:00Z=" + (string)GoldAI_UsDst(D'2026.03.08 07:00') +
             " 2026-11-01 05:59Z=" + (string)GoldAI_UsDst(D'2026.11.01 05:59') + " 06:00Z=" + (string)GoldAI_UsDst(D'2026.11.01 06:00') + "\n";
      for(int i = 0; i < ArraySize(cal); i++)
         out += "  CAL " + GoldAI_NewsWindowText(cal[i]) + "\n";

     }
   string body = "";
   const int h = FileOpen("news.json", FILE_READ | FILE_BIN);
   if(h != INVALID_HANDLE)
     {
      uchar b[];
      ArrayResize(b, (int)FileSize(h));
      FileReadArray(h, b, 0, (int)FileSize(h));
      FileClose(h);
      body = CharArrayToString(b, 0, WHOLE_ARRAY, CP_UTF8);
     }
   GoldAINewsEvent fl[];
   const int nf = GoldAI_NewsFromJson(fl, body, 30, 90, err);
   out += "file added=" + IntegerToString(nf) + " err=" + err + "\n";
   for(int i = 0; i < ArraySize(fl); i++)
      out += "  FILE " + GoldAI_NewsWindowText(fl[i]) + "\n";

   int idx = -1;
   const datetime probe = D'2026.11.18 18:45:00';
   out += "active at 2026-11-18 18:45Z (file)=" + (GoldAI_NewsActive(fl, probe, idx) ? GoldAI_NewsWindowText(fl[idx]) : "none") + "\n";
   out += "active at 2026-11-18 20:31Z (file)=" + (GoldAI_NewsActive(fl, D'2026.11.18 20:31:00', idx) ? "YES" : "none") + "\n";
   out += "next from now (cal)=" + (GoldAI_NewsNext(cal, TimeGMT()) >= 0 ? GoldAI_NewsWindowText(cal[GoldAI_NewsNext(cal, TimeGMT())]) : "none") + "\n";

   // getUpdates parse check (same calls as the EA)
   const string resp = "{\"ok\":true,\"result\":[{\"update_id\":123456789,\"message\":{\"message_id\":5,\"from\":{\"id\":730711407,\"is_bot\":false},\"chat\":{\"id\":730711407,\"type\":\"private\"},\"date\":1794643200,\"text\":\"/confirm 4821\"}},{\"update_id\":123456790,\"message\":{\"chat\":{\"id\":-100555,\"type\":\"group\"},\"date\":1794643201,\"text\":\"/closeall\"}}]}";
   string items[];
   bool flags[];
   const string arr = JsonGetArray(resp, "result");
   const int n = JsonSplitArray(arr, items, flags);
   for(int i = 0; i < n; i++)
     {
      string raw, cid;
      bool s;
      JsonGet(items[i], "update_id", raw, s);
      const string msg = JsonGetObject(items[i], "message");
      const string chat = JsonGetObject(msg, "chat");
      JsonGet(chat, "id", cid, s);
      out += "  upd=" + raw + " chat=" + cid + " allowed=" + (cid == "730711407" ? "yes" : "no") +
             " date=" + IntegerToString((long)JsonGetNumberDef(msg, "date", 0)) +
             " text=" + JsonGetString(msg, "text", "") + "\n";
     }
   Print(out);
   const int w = FileOpen("GoldNewsSelfTest.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(w != INVALID_HANDLE)
     {
      FileWriteString(w, out);
      FileClose(w);
     }
  }

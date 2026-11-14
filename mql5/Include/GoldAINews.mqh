//+------------------------------------------------------------------+
//| GoldAINews.mqh                                                   |
//| High-impact USD news windows for GoldAIBridge (v1.03).           |
//| Two sources, always merged (union):                              |
//|   1) MT5 built-in Economic Calendar (USD, keyword + importance)  |
//|   2) Static list decisions/news.json (times in UTC)              |
//| A window blocks NEW entries only. Open positions are untouched.  |
//+------------------------------------------------------------------+
#ifndef GOLD_AI_NEWS_MQH
#define GOLD_AI_NEWS_MQH

#include <GoldAIJson.mqh>
#include <GoldAIUtil.mqh>

#define GOLD_AI_MAX_NEWS 256

struct GoldAINewsEvent
  {
   datetime event_utc;   // release time (UTC)
   datetime start_utc;   // window start (UTC)
   datetime end_utc;     // window end (UTC)
   string   name;
   string   source;      // "calendar" or "file"
  };

//+------------------------------------------------------------------+
//| Split "a;b;c" (or "a,b,c") into trimmed upper-case keywords.     |
//+------------------------------------------------------------------+
int GoldAI_NewsKeywords(const string csv, string &out[])
  {
   ArrayResize(out, 0);
   string list = csv;
   StringReplace(list, ",", ";"); // accept ',' too (safer inside .set files)
   string parts[];
   const int n = StringSplit(list, ';', parts);
   for(int i = 0; i < n; i++)
     {
      string k = parts[i];
      StringTrimLeft(k);
      StringTrimRight(k);
      if(k == "")
         continue;
      StringToUpper(k);
      const int m = ArraySize(out);
      ArrayResize(out, m + 1);
      out[m] = k;
     }
   return(ArraySize(out));
  }

//+------------------------------------------------------------------+
bool GoldAI_NewsNameMatches(const string name, const string &keys[])
  {
   string up = name;
   StringToUpper(up);
   for(int i = 0; i < ArraySize(keys); i++)
      if(StringFind(up, keys[i]) >= 0)
         return(true);
   return(false);
  }

//+------------------------------------------------------------------+
//| Add an event, merging names that share the same release time.    |
//+------------------------------------------------------------------+
void GoldAI_NewsAdd(GoldAINewsEvent &arr[],
                    const datetime event_utc,
                    const string name,
                    const string source,
                    const int before_min,
                    const int after_min)
  {
   if(event_utc <= 0)
      return;
   const int n = ArraySize(arr);
   for(int i = 0; i < n; i++)
     {
      if(arr[i].event_utc == event_utc)
        {
         if(StringFind(arr[i].name, name) < 0 && StringLen(arr[i].name) < 90)
            arr[i].name += ", " + name;
         return;
        }
     }
   if(n >= GOLD_AI_MAX_NEWS)
      return;
   ArrayResize(arr, n + 1);
   arr[n].event_utc = event_utc;
   arr[n].start_utc = event_utc - (datetime)(MathMax(before_min, 0) * 60);
   arr[n].end_utc   = event_utc + (datetime)(MathMax(after_min, 0) * 60);
   arr[n].name      = name;
   arr[n].source    = source;
  }

//+------------------------------------------------------------------+
//| Server-minus-GMT offset in seconds, rounded to 15 minutes.        |
//+------------------------------------------------------------------+
long GoldAI_ServerGmtOffset()
  {
   const long raw = (long)TimeTradeServer() - (long)TimeGMT();
   return((long)MathRound((double)raw / 900.0) * 900);
  }

//+------------------------------------------------------------------+
//| Load USD events from the MT5 Economic Calendar.                  |
//| min_importance: 1=LOW 2=MODERATE 3=HIGH. A name keyword match    |
//| plus importance >= min_importance is required, unless            |
//| all_high is true (then every USD HIGH event is used as well).    |
//| Returns the number of events added, or -1 on calendar failure.   |
//+------------------------------------------------------------------+
int GoldAI_NewsFromCalendar(GoldAINewsEvent &arr[],
                            const string keywords_csv,
                            const int min_importance,
                            const bool all_high,
                            const int before_min,
                            const int after_min,
                            const int lookahead_days,
                            string &err)
  {
   err = "";
   string keys[];
   GoldAI_NewsKeywords(keywords_csv, keys);

   const long offset = GoldAI_ServerGmtOffset();
   const datetime now_srv = TimeTradeServer();
   const datetime from = now_srv - 86400;
   const datetime to   = now_srv + (datetime)(MathMax(lookahead_days, 1) * 86400);

   MqlCalendarValue values[];
   ResetLastError();
   const int nv = CalendarValueHistory(values, from, to, NULL, "USD");
   if(nv < 0)
     {
      err = "CalendarValueHistory failed err=" + IntegerToString(GetLastError());
      return(-1);
     }
   if(nv == 0)
     {
      err = "calendar returned 0 USD values (err=" + IntegerToString(GetLastError()) + ")";
      return(-1);
     }

   int added = 0;
   for(int i = 0; i < nv; i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev))
         continue;
      const int imp = (int)ev.importance;
      const bool high = (ev.importance == CALENDAR_IMPORTANCE_HIGH);
      bool take = false;
      if(all_high && high)
         take = true;
      if(!take && imp >= min_importance && GoldAI_NewsNameMatches(ev.name, keys))
         take = true;
      if(!take)
         continue;
      const datetime utc = (datetime)((long)values[i].time - offset);
      const int before = ArraySize(arr);
      GoldAI_NewsAdd(arr, utc, ev.name, "calendar", before_min, after_min);
      if(ArraySize(arr) > before)
         added++;
     }
   return(added);
  }

//+------------------------------------------------------------------+
//| Parse decisions/news.json. Format:                               |
//| {"version":1,"events":[{"time_utc":"2026-11-18T19:00:00Z",       |
//|   "name":"FOMC Minutes","currency":"USD"}, ...]}                 |
//| Optional per-event "before_min"/"after_min" override the inputs  |
//| only when they are LARGER (the file can widen, never shrink).    |
//| Returns events added, or -1 on a parse failure.                  |
//+------------------------------------------------------------------+
int GoldAI_NewsFromJson(GoldAINewsEvent &arr[],
                        const string body_in,
                        const int before_min,
                        const int after_min,
                        string &err)
  {
   err = "";
   const string body = JsonStripNoise(body_in);
   if(StringLen(body) < 2 || StringGetCharacter(body, 0) != '{')
     {
      err = "news.json is not a JSON object";
      return(-1);
     }
   const string list = JsonGetArray(body, "events");
   if(list == "")
     {
      err = "news.json has no events array";
      return(-1);
     }
   string items[];
   bool   flags[];
   const int n = JsonSplitArray(list, items, flags);
   int added = 0;
   for(int i = 0; i < n; i++)
     {
      if(flags[i] || StringLen(items[i]) < 2 || StringGetCharacter(items[i], 0) != '{')
         continue;
      string cur = JsonGetString(items[i], "currency", "USD");
      StringToUpper(cur);
      if(cur != "USD")
         continue;
      const datetime t = GoldAI_ParseIsoUtc(JsonGetString(items[i], "time_utc"));
      if(t <= 0)
         continue;
      int b = JsonGetIntDef(items[i], "before_min", before_min);
      int a = JsonGetIntDef(items[i], "after_min", after_min);
      if(b < before_min)
         b = before_min;
      if(a < after_min)
         a = after_min;
      const int sz = ArraySize(arr);
      GoldAI_NewsAdd(arr, t, JsonGetString(items[i], "name", "news"), "file", b, a);
      if(ArraySize(arr) > sz)
         added++;
     }
   return(added);
  }

//+------------------------------------------------------------------+
//| Active window at now_utc? Copies its description.                |
//+------------------------------------------------------------------+
bool GoldAI_NewsActive(const GoldAINewsEvent &arr[], const datetime now_utc, int &idx)
  {
   idx = -1;
   for(int i = 0; i < ArraySize(arr); i++)
     {
      if(now_utc >= arr[i].start_utc && now_utc < arr[i].end_utc)
        {
         if(idx < 0 || arr[i].event_utc < arr[idx].event_utc)
            idx = i;
        }
     }
   return(idx >= 0);
  }

//+------------------------------------------------------------------+
//| Next window that has not ended yet (active one counts).          |
//+------------------------------------------------------------------+
int GoldAI_NewsNext(const GoldAINewsEvent &arr[], const datetime now_utc)
  {
   int best = -1;
   for(int i = 0; i < ArraySize(arr); i++)
     {
      if(arr[i].end_utc <= now_utc)
         continue;
      if(best < 0 || arr[i].start_utc < arr[best].start_utc)
         best = i;
     }
   return(best);
  }

//+------------------------------------------------------------------+
string GoldAI_NewsWindowText(const GoldAINewsEvent &e)
  {
   return(e.name + " @ " + GoldAI_TimeToIsoUtc(e.event_utc) +
          " (block " + StringSubstr(GoldAI_TimeToIsoUtc(e.start_utc), 11, 5) +
          "-" + StringSubstr(GoldAI_TimeToIsoUtc(e.end_utc), 11, 5) + "Z, " + e.source + ")");
  }

#endif

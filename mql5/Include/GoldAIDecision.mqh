//+------------------------------------------------------------------+
//| GoldAIDecision.mqh                                               |
//| Decision struct, JSON parse, and validity checks.                |
//+------------------------------------------------------------------+
#ifndef GOLD_AI_DECISION_MQH
#define GOLD_AI_DECISION_MQH

#include "GoldAIJson.mqh"
#include "GoldAIUtil.mqh"

#define GOLD_AI_BIAS_NONE  0
#define GOLD_AI_BIAS_BUY   1
#define GOLD_AI_BIAS_SELL  2

#define GOLD_AI_MAX_BLACKOUTS 16

//+------------------------------------------------------------------+
struct GoldAINewsWindow
  {
   datetime start_time;
   datetime end_time;
   string   reason;
  };

//+------------------------------------------------------------------+
struct GoldAIDecision
  {
   bool     loaded;
   int      version;
   datetime generated_at;
   datetime valid_until;
   string   symbol;
   int      bias;          // GOLD_AI_BIAS_*
   string   bias_text;
   double   zone_low;
   double   zone_high;
   double   stop_loss;
   double   tp1;
   double   tp2;
   int      confidence;
   double   max_risk_pct;  // 0 = not provided / use EA default
   string   rationale;
   bool     kill_switch;
   int      blackout_count;
   GoldAINewsWindow blackouts[GOLD_AI_MAX_BLACKOUTS];
   string   parse_error;
   string   raw_json;
  };

//+------------------------------------------------------------------+
void GoldAI_DecisionClear(GoldAIDecision &d)
  {
   d.loaded        = false;
   d.version       = 0;
   d.generated_at  = 0;
   d.valid_until   = 0;
   d.symbol        = "";
   d.bias          = GOLD_AI_BIAS_NONE;
   d.bias_text     = "NONE";
   d.zone_low      = 0.0;
   d.zone_high     = 0.0;
   d.stop_loss     = 0.0;
   d.tp1           = 0.0;
   d.tp2           = 0.0;
   d.confidence    = 0;
   d.max_risk_pct  = 0.0;
   d.rationale     = "";
   d.kill_switch   = false;
   d.blackout_count = 0;
   d.parse_error   = "";
   d.raw_json      = "";
   for(int i = 0; i < GOLD_AI_MAX_BLACKOUTS; i++)
     {
      d.blackouts[i].start_time = 0;
      d.blackouts[i].end_time   = 0;
      d.blackouts[i].reason     = "";
     }
  }

//+------------------------------------------------------------------+
int GoldAI_ParseBias(const string text)
  {
   string t = text;
   StringTrimLeft(t);
   StringTrimRight(t);
   StringToUpper(t);
   if(t == "BUY" || t == "LONG")
      return(GOLD_AI_BIAS_BUY);
   if(t == "SELL" || t == "SHORT")
      return(GOLD_AI_BIAS_SELL);
   return(GOLD_AI_BIAS_NONE);
  }

//+------------------------------------------------------------------+
string GoldAI_BiasText(const int bias)
  {
   if(bias == GOLD_AI_BIAS_BUY)
      return("BUY");
   if(bias == GOLD_AI_BIAS_SELL)
      return("SELL");
   return("NONE");
  }

//+------------------------------------------------------------------+
//| Parse a decision JSON document into 'd'.                         |
//| Returns false on a hard parse failure (d.parse_error is set).    |
//+------------------------------------------------------------------+
bool GoldAI_DecisionParse(const string json_in, GoldAIDecision &d)
  {
   GoldAI_DecisionClear(d);
   const string json = JsonStripNoise(json_in);
   d.raw_json = json;
   if(StringLen(json) < 2)
     {
      d.parse_error = "empty body";
      return(false);
     }
   int pos = 0;
   JsonSkipWs(json, pos);
   if(pos >= StringLen(json) || StringGetCharacter(json, pos) != '{')
     {
      d.parse_error = "body is not a JSON object (is the URL a raw file, not an HTML page?)";
      return(false);
     }

   if(!JsonHasKey(json, "version") ||
      !JsonHasKey(json, "generated_at") ||
      !JsonHasKey(json, "valid_until") ||
      !JsonHasKey(json, "bias"))
     {
      d.parse_error = "missing required field (version, generated_at, valid_until, or bias)";
      return(false);
     }

   d.version = JsonGetIntDef(json, "version", 0);
   if(d.version < 1)
     {
      d.parse_error = "version must be >= 1";
      return(false);
     }

   d.generated_at = GoldAI_ParseIsoUtc(JsonGetString(json, "generated_at"));
   d.valid_until  = GoldAI_ParseIsoUtc(JsonGetString(json, "valid_until"));
   if(d.generated_at <= 0)
     {
      d.parse_error = "generated_at is not a valid UTC ISO timestamp";
      return(false);
     }
   if(d.valid_until <= 0)
     {
      d.parse_error = "valid_until is not a valid UTC ISO timestamp";
      return(false);
     }

   d.symbol    = JsonGetString(json, "symbol", "XAUUSD");
   d.bias_text = JsonGetString(json, "bias", "NONE");
   d.bias      = GoldAI_ParseBias(d.bias_text);
   d.bias_text = GoldAI_BiasText(d.bias);

   const string zone = JsonGetObject(json, "entry_zone");
   if(zone != "")
     {
      d.zone_low  = JsonGetNumberDef(zone, "low", 0.0);
      d.zone_high = JsonGetNumberDef(zone, "high", 0.0);
     }

   d.stop_loss    = JsonGetNumberDef(json, "stop_loss", 0.0);
   d.confidence   = JsonGetIntDef(json, "confidence", 0);
   d.max_risk_pct = JsonGetNumberDef(json, "max_risk_pct", 0.0);
   d.rationale    = JsonGetString(json, "rationale", "");
   d.kill_switch  = JsonGetBoolDef(json, "kill_switch", false);

   if(d.confidence < 0)
      d.confidence = 0;
   if(d.confidence > 100)
      d.confidence = 100;
   if(d.max_risk_pct < 0.0)
      d.max_risk_pct = 0.0;

   const string tps = JsonGetArray(json, "take_profits");
   if(tps != "")
     {
      string items[];
      bool   flags[];
      const int n = JsonSplitArray(tps, items, flags);
      if(n >= 1)
         d.tp1 = StringToDouble(items[0]);
      if(n >= 2)
         d.tp2 = StringToDouble(items[1]);
     }

   const string bl = JsonGetArray(json, "news_blackout");
   if(bl != "")
     {
      string items[];
      bool   flags[];
      const int n = JsonSplitArray(bl, items, flags);
      int stored = 0;
      for(int i = 0; i < n; i++)
        {
         if(flags[i])
            continue; // a bare string, not an object
         if(StringLen(items[i]) < 2 || StringGetCharacter(items[i], 0) != '{')
            continue;
         if(stored >= GOLD_AI_MAX_BLACKOUTS)
            break;
         const datetime st = GoldAI_ParseIsoUtc(JsonGetString(items[i], "start"));
         const datetime en = GoldAI_ParseIsoUtc(JsonGetString(items[i], "end"));
         if(st <= 0 || en <= 0 || en <= st)
            continue;
         d.blackouts[stored].start_time = st;
         d.blackouts[stored].end_time   = en;
         d.blackouts[stored].reason     = JsonGetString(items[i], "reason", "");
         stored++;
        }
      d.blackout_count = stored;
     }

   d.loaded = true;
   return(true);
  }

//+------------------------------------------------------------------+
bool GoldAI_DecisionIsStale(const GoldAIDecision &d, const datetime now_gmt)
  {
   if(!d.loaded)
      return(true);
   return(d.valid_until <= now_gmt);
  }

//+------------------------------------------------------------------+
//| If now is inside a blackout, copies the reason and returns true. |
//+------------------------------------------------------------------+
bool GoldAI_InBlackout(const GoldAIDecision &d, const datetime now_gmt, string &reason)
  {
   reason = "";
   if(!d.loaded)
      return(false);
   for(int i = 0; i < d.blackout_count; i++)
     {
      if(now_gmt >= d.blackouts[i].start_time && now_gmt < d.blackouts[i].end_time)
        {
         reason = d.blackouts[i].reason;
         return(true);
        }
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Check entry-zone geometry for a live (BUY/SELL) decision.        |
//+------------------------------------------------------------------+
bool GoldAI_DecisionGeometryOk(const GoldAIDecision &d, string &reason)
  {
   reason = "";
   if(d.bias == GOLD_AI_BIAS_NONE)
      return(true);
   if(d.zone_low >= d.zone_high)
     {
      reason = "entry_zone.low must be < entry_zone.high";
      return(false);
     }
   if(d.stop_loss == 0.0)
     {
      reason = "stop_loss is missing";
      return(false);
     }
   if(d.bias == GOLD_AI_BIAS_BUY)
     {
      if(!(d.stop_loss < d.zone_low))
        {
         reason = "BUY stop_loss must be below entry_zone.low";
         return(false);
        }
      if(d.tp1 == 0.0)
        {
         reason = "tp1 is missing";
         return(false);
        }
      if(!(d.tp1 > d.zone_high))
        {
         reason = "BUY tp1 must be above entry_zone.high";
         return(false);
        }
      if(d.tp2 != 0.0 && !(d.tp2 > d.tp1))
        {
         reason = "BUY tp2 must be above tp1";
         return(false);
        }
     }
   if(d.bias == GOLD_AI_BIAS_SELL)
     {
      if(!(d.stop_loss > d.zone_high))
        {
         reason = "SELL stop_loss must be above entry_zone.high";
         return(false);
        }
      if(d.tp1 == 0.0)
        {
         reason = "tp1 is missing";
         return(false);
        }
      if(!(d.tp1 < d.zone_low))
        {
         reason = "SELL tp1 must be below entry_zone.low";
         return(false);
        }
      if(d.tp2 != 0.0 && !(d.tp2 < d.tp1))
        {
         reason = "SELL tp2 must be below tp1";
         return(false);
        }
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Is the given market price inside the entry zone (inclusive)?     |
//+------------------------------------------------------------------+
bool GoldAI_PriceInZone(const GoldAIDecision &d, const double price)
  {
   if(!d.loaded || d.bias == GOLD_AI_BIAS_NONE)
      return(false);
   return(price >= d.zone_low && price <= d.zone_high);
  }

//+------------------------------------------------------------------+
//| Final order TP: tp2 if set, otherwise tp1.                       |
//+------------------------------------------------------------------+
double GoldAI_OrderTakeProfit(const GoldAIDecision &d)
  {
   if(d.tp2 != 0.0)
      return(d.tp2);
   return(d.tp1);
  }

//+------------------------------------------------------------------+
bool GoldAI_HasPartialTp(const GoldAIDecision &d)
  {
   return(d.tp1 != 0.0 && d.tp2 != 0.0 && d.tp1 != d.tp2);
  }

//+------------------------------------------------------------------+
//| A short fingerprint so we can log when a new file arrives.       |
//+------------------------------------------------------------------+
string GoldAI_DecisionFingerprint(const GoldAIDecision &d)
  {
   return(d.bias_text + "|" +
          GoldAI_TimeToIsoUtc(d.generated_at) + "|" +
          DoubleToString(d.zone_low, 2) + "-" + DoubleToString(d.zone_high, 2) + "|" +
          DoubleToString(d.stop_loss, 2) + "|" +
          DoubleToString(d.tp1, 2) + "/" + DoubleToString(d.tp2, 2) + "|" +
          IntegerToString(d.confidence) + "|" +
          (d.kill_switch ? "KILL" : "OK"));
  }

#endif // GOLD_AI_DECISION_MQH
//+------------------------------------------------------------------+

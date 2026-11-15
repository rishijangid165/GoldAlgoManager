//+------------------------------------------------------------------+
//| GoldPropGuardSelfTest.mq5 - offline unit test of the v1.04 prop  |
//| guard helpers (GoldAIPropGuard.mqh). No trading, no network.     |
//| Drop on any chart; results go to the Experts log and to          |
//| MQL5/Files/GoldPropGuardSelfTest.txt. Expect "ALL PASS".          |
//| Expected day-start values were cross-checked against Python      |
//| zoneinfo (Europe/Prague, America/New_York).                      |
//+------------------------------------------------------------------+
#property version "1.00"
#property script_show_inputs false
#include <GoldAIUtil.mqh>
#include <GoldAIPropGuard.mqh>

int    g_pass = 0;
int    g_fail = 0;
string g_out  = "";

void Check(const string name, const bool ok, const string detail = "")
  {
   if(ok) g_pass++; else g_fail++;
   const string line = (ok ? "PASS " : "FAIL ") + name + (detail == "" ? "" : (" | " + detail));
   Print(line);
   g_out += line + "\n";
  }

void CheckDay(const string name, const datetime now, const int tz, const int hour, const long so, const datetime expect)
  {
   const datetime got = GoldAI_PropDayStartUtc(now, tz, hour, so);
   Check(name, got == expect, "got " + TimeToString(got) + " expect " + TimeToString(expect));
  }

bool Near(const double a, const double b) { return(MathAbs(a - b) < 0.005); }

void OnStart()
  {
   // --- DST helpers
   Check("EU DST off 2026-03-29 00:59Z", !GoldAI_EuDst(D'2026.03.29 00:59'));
   Check("EU DST on  2026-03-29 01:00Z",  GoldAI_EuDst(D'2026.03.29 01:00'));
   Check("EU DST on  2026-10-25 00:59Z",  GoldAI_EuDst(D'2026.10.25 00:59'));
   Check("EU DST off 2026-10-25 01:00Z", !GoldAI_EuDst(D'2026.10.25 01:00'));
   Check("US DST on 2026-07-01",  GoldAI_PgUsDst(D'2026.07.01 12:00'));
   Check("US DST off 2026-11-17", !GoldAI_PgUsDst(D'2026.11.17 12:00'));

   // --- Day start (FTMO: CE(S)T midnight)
   CheckDay("CET winter",          D'2026.11.16 10:00', GOLDAI_TZ_CET, 0, 0, D'2026.11.15 23:00');
   CheckDay("CET summer 23:30loc", D'2026.07.01 21:30', GOLDAI_TZ_CET, 0, 0, D'2026.06.30 22:00');
   CheckDay("CET summer 00:30loc", D'2026.07.01 22:30', GOLDAI_TZ_CET, 0, 0, D'2026.07.01 22:00');
   CheckDay("CET DST-off day",     D'2026.10.25 12:00', GOLDAI_TZ_CET, 0, 0, D'2026.10.24 22:00');
   CheckDay("CET DST-on day",      D'2026.03.29 12:00', GOLDAI_TZ_CET, 0, 0, D'2026.03.28 23:00');
   // --- New York 17:00 reset
   CheckDay("NY 17:00 after",      D'2026.11.16 23:00', GOLDAI_TZ_NEWYORK, 17, 0, D'2026.11.16 22:00');
   CheckDay("NY 17:00 before",     D'2026.11.16 21:00', GOLDAI_TZ_NEWYORK, 17, 0, D'2026.11.15 22:00');
   CheckDay("NY 17:00 summer",     D'2026.07.15 20:59', GOLDAI_TZ_NEWYORK, 17, 0, D'2026.07.14 21:00');
   // --- Broker server (UTC+2 in winter) and UTC
   CheckDay("Server +2 23:59loc",  D'2026.11.16 21:59', GOLDAI_TZ_SERVER, 0, 7200, D'2026.11.15 22:00');
   CheckDay("Server +2 00:00loc",  D'2026.11.16 22:00', GOLDAI_TZ_SERVER, 0, 7200, D'2026.11.16 22:00');
   CheckDay("UTC midnight",        D'2026.11.16 00:00', GOLDAI_TZ_UTC, 0, 0, D'2026.11.16 00:00');

   // --- Day base
   Check("base balance", Near(GoldAI_PropDayBase(GOLDAI_BASE_BALANCE, 100000, 100500), 100000));
   Check("base equity",  Near(GoldAI_PropDayBase(GOLDAI_BASE_EQUITY, 100000, 100500), 100500));
   Check("base max",     Near(GoldAI_PropDayBase(GOLDAI_BASE_MAX, 100000, 100500), 100500));

   // --- Allowances / floors (FTMO 100k, guard 4% / 8%)
   const double allow = GoldAI_PropDailyAllowance(4.0, true, 100000, 101000);
   Check("daily allowance of initial", Near(allow, 4000));
   Check("daily allowance of base", Near(GoldAI_PropDailyAllowance(4.0, false, 100000, 101000), 4040));
   Check("static floor", Near(GoldAI_PropDDFloor(8.0, 100000, 105000, false, true), 92000));
   Check("trailing floor", Near(GoldAI_PropDDFloor(8.0, 100000, 105000, true, true), 97000));
   Check("trailing floor locked", Near(GoldAI_PropDDFloor(8.0, 100000, 110000, true, true), 100000));
   Check("trailing floor unlocked", Near(GoldAI_PropDDFloor(8.0, 100000, 110000, true, false), 102000));
   Check("floor off", Near(GoldAI_PropDDFloor(0.0, 100000, 100000, false, true), 0));

   // --- Evaluate (base 100k, allowance 4000, floor 92000, dd amount 8000, warn 0.75)
   Check("eval OK",          GoldAI_PropEvaluate(97100, 100000, 4000, 92000, 8000, 0, 0.75) == GOLDAI_PG_OK);
   Check("eval WARN daily",  GoldAI_PropEvaluate(96999, 100000, 4000, 92000, 8000, 0, 0.75) == GOLDAI_PG_WARN);
   Check("eval DAILY trip",  GoldAI_PropEvaluate(96000, 100000, 4000, 92000, 8000, 0, 0.75) == GOLDAI_PG_DAILY_TRIP);
   Check("eval DD trip",     (GoldAI_PropEvaluate(92000, 93000, 4000, 92000, 8000, 0, 0.75) & GOLDAI_PG_DD_TRIP) != 0);
   Check("eval DD warn",     GoldAI_PropEvaluate(93900, 94000, 4000, 92000, 8000, 0, 0.75) == GOLDAI_PG_WARN);
   Check("eval profit cap",  GoldAI_PropEvaluate(102000, 100000, 4000, 92000, 8000, 2.0, 0.75) == GOLDAI_PG_PROFIT_CAP);
   Check("eval below cap",   GoldAI_PropEvaluate(101900, 100000, 4000, 92000, 8000, 2.0, 0.75) == GOLDAI_PG_OK);

   // --- Pre-trade fit
   string why = "";
   Check("fit small risk",  GoldAI_PropRiskFits(97500, 100000, 4000, 92000, 500, 1.25, why));
   Check("no fit daily",   !GoldAI_PropRiskFits(97500, 100000, 4000, 92000, 1500, 1.25, why), why);
   Check("no fit DD",      !GoldAI_PropRiskFits(92400, 92400, 4000, 92000, 500, 1.25, why), why);

   // --- News flat window (blackout 30/90, flat 2/2 = FTMO funded Standard)
   const datetime ev = D'2026.12.04 13:30';
   datetime f = 0, t = 0;
   Check("news -1m flat",  GoldAI_PropNewsFlatWindow(ev - 60,  ev - 1800, ev + 5400, 30, 90, 2, 2, f, t));
   Check("news -3m free", !GoldAI_PropNewsFlatWindow(ev - 180, ev - 1800, ev + 5400, 30, 90, 2, 2, f, t));
   Check("news +1m flat",  GoldAI_PropNewsFlatWindow(ev + 60,  ev - 1800, ev + 5400, 30, 90, 2, 2, f, t));
   Check("news +2m free", !GoldAI_PropNewsFlatWindow(ev + 120, ev - 1800, ev + 5400, 30, 90, 2, 2, f, t));
   // widened (ambiguous calendar~) record: candidates ev and ev+2h
   Check("news widened mid", GoldAI_PropNewsFlatWindow(ev + 3600, ev - 1800, ev + 7200 + 5400, 30, 90, 2, 2, f, t),
         TimeToString(f) + " - " + TimeToString(t));
   Check("news widened bounds", f == ev - 120 && t == ev + 7200 + 120);

   const string summary = (g_fail == 0 ? "ALL PASS " : "FAILURES ") + IntegerToString(g_pass) + " passed, " +
                          IntegerToString(g_fail) + " failed";
   Print("GoldPropGuardSelfTest: ", summary);
   g_out += summary + "\n";
   const int h = FileOpen("GoldPropGuardSelfTest.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h != INVALID_HANDLE)
     {
      FileWriteString(h, g_out);
      FileClose(h);
     }
  }

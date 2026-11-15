//+------------------------------------------------------------------+
//| GoldAIPropGuard.mqh - v1.04 prop-firm risk guard helpers.        |
//| Pure functions (no trading, no globals) so they can be unit      |
//| tested by Scripts/GoldPropGuardSelfTest.mq5.                     |
//+------------------------------------------------------------------+
#ifndef GOLD_AI_PROP_GUARD_MQH
#define GOLD_AI_PROP_GUARD_MQH

// Time zone used to decide when the prop "trading day" resets.
enum ENUM_GOLDAI_RESET_TZ
  {
   GOLDAI_TZ_SERVER  = 0, // Broker server time
   GOLDAI_TZ_UTC     = 1, // UTC
   GOLDAI_TZ_CET     = 2, // CE(S)T, Europe/Prague (FTMO)
   GOLDAI_TZ_NEWYORK = 3  // New York ET (EST/EDT)
  };

// Which start-of-day value the daily loss is measured from.
enum ENUM_GOLDAI_DAY_BASE
  {
   GOLDAI_BASE_BALANCE = 0, // Balance at day reset (FTMO)
   GOLDAI_BASE_EQUITY  = 1, // Equity at day reset
   GOLDAI_BASE_MAX     = 2  // Higher of balance/equity (The5ers, E8 - most conservative)
  };

// Guard evaluation result (bit flags).
#define GOLDAI_PG_OK          0
#define GOLDAI_PG_WARN        1
#define GOLDAI_PG_DAILY_TRIP  2
#define GOLDAI_PG_DD_TRIP     4
#define GOLDAI_PG_PROFIT_CAP  8

//+------------------------------------------------------------------+
//| Last Sunday of a month at hour_utc (UTC).                         |
//+------------------------------------------------------------------+
datetime GoldAI_LastSundayUtc(const int year, const int month, const int hour_utc)
  {
   MqlDateTime st;
   st.year = (month == 12 ? year + 1 : year);
   st.mon  = (month == 12 ? 1 : month + 1);
   st.day  = 1;
   st.hour = 0; st.min = 0; st.sec = 0;
   const datetime first_next = StructToTime(st);
   const datetime last_day = first_next - 86400;
   TimeToStruct(last_day, st);
   return(last_day - (datetime)(st.day_of_week * 86400) + (datetime)(hour_utc * 3600));
  }

//+------------------------------------------------------------------+
//| EU summer time: last Sun Mar 01:00Z .. last Sun Oct 01:00Z.       |
//+------------------------------------------------------------------+
bool GoldAI_EuDst(const datetime utc)
  {
   MqlDateTime st;
   TimeToStruct(utc, st);
   const datetime on  = GoldAI_LastSundayUtc(st.year, 3, 1);
   const datetime off = GoldAI_LastSundayUtc(st.year, 10, 1);
   return(utc >= on && utc < off);
  }

//+------------------------------------------------------------------+
//| US DST: 2nd Sun Mar 07:00Z .. 1st Sun Nov 06:00Z.                 |
//+------------------------------------------------------------------+
datetime GoldAI_PgNthSundayUtc(const int year, const int month, const int nth, const int hour_utc)
  {
   MqlDateTime st;
   st.year = year; st.mon = month; st.day = 1;
   st.hour = 0; st.min = 0; st.sec = 0;
   datetime t = StructToTime(st);
   TimeToStruct(t, st);
   const int first_sunday = 1 + ((7 - st.day_of_week) % 7);
   return(t + (datetime)((first_sunday - 1 + 7 * (nth - 1)) * 86400 + hour_utc * 3600));
  }

bool GoldAI_PgUsDst(const datetime utc)
  {
   MqlDateTime st;
   TimeToStruct(utc, st);
   return(utc >= GoldAI_PgNthSundayUtc(st.year, 3, 2, 7) && utc < GoldAI_PgNthSundayUtc(st.year, 11, 1, 6));
  }

//+------------------------------------------------------------------+
//| Local-minus-UTC offset (seconds) for a zone at a UTC instant.     |
//+------------------------------------------------------------------+
long GoldAI_TzOffsetSec(const int tz, const datetime utc, const long server_offset_sec)
  {
   if(tz == GOLDAI_TZ_UTC)
      return(0);
   if(tz == GOLDAI_TZ_CET)
      return(GoldAI_EuDst(utc) ? 7200 : 3600);
   if(tz == GOLDAI_TZ_NEWYORK)
      return(GoldAI_PgUsDst(utc) ? -4 * 3600 : -5 * 3600);
   return(server_offset_sec);
  }

//+------------------------------------------------------------------+
//| UTC instant at which the current prop day started.               |
//| reset_hour is local hour in tz (0 = midnight).                    |
//+------------------------------------------------------------------+
datetime GoldAI_PropDayStartUtc(const datetime now_utc, const int tz, const int reset_hour_in,
                                const long server_offset_sec)
  {
   int reset_hour = reset_hour_in;
   if(reset_hour < 0 || reset_hour > 23)
      reset_hour = 0;
   const long off_now = GoldAI_TzOffsetSec(tz, now_utc, server_offset_sec);
   const long local = (long)now_utc + off_now;
   const long shifted = local - reset_hour * 3600;
   long day = shifted - (((shifted % 86400) + 86400) % 86400);
   const long start_local = day + reset_hour * 3600;
   long start_utc = start_local - off_now;
   // Re-evaluate the offset at the reset instant (DST change days).
   const long off_start = GoldAI_TzOffsetSec(tz, (datetime)start_utc, server_offset_sec);
   start_utc = start_local - off_start;
   if(start_utc > (long)now_utc)
      start_utc -= 86400;
   return((datetime)start_utc);
  }

//+------------------------------------------------------------------+
//| Start-of-day base value for the daily loss.                      |
//+------------------------------------------------------------------+
double GoldAI_PropDayBase(const int base_mode, const double day_balance, const double day_equity)
  {
   if(base_mode == GOLDAI_BASE_EQUITY)
      return(day_equity);
   if(base_mode == GOLDAI_BASE_MAX)
      return(MathMax(day_balance, day_equity));
   return(day_balance);
  }

//+------------------------------------------------------------------+
//| Daily loss allowance in money.                                   |
//| pct_of_initial=true: pct of initial balance (FTMO style).        |
//+------------------------------------------------------------------+
double GoldAI_PropDailyAllowance(const double pct, const bool pct_of_initial,
                                 const double initial_balance, const double day_base)
  {
   if(pct <= 0.0)
      return(0.0);
   return(pct / 100.0 * (pct_of_initial ? initial_balance : day_base));
  }

//+------------------------------------------------------------------+
//| Overall drawdown floor (equity must stay above it).              |
//| trailing: floor follows the high-water mark; lock_at_initial     |
//| stops the trailing floor at the initial balance.                 |
//+------------------------------------------------------------------+
double GoldAI_PropDDFloor(const double pct, const double initial_balance, const double peak,
                          const bool trailing, const bool lock_at_initial)
  {
   if(pct <= 0.0 || initial_balance <= 0.0)
      return(0.0);
   const double amount = pct / 100.0 * initial_balance;
   if(!trailing)
      return(initial_balance - amount);
   double floor = MathMax(peak, initial_balance) - amount;
   if(lock_at_initial && floor > initial_balance)
      floor = initial_balance;
   return(floor);
  }

//+------------------------------------------------------------------+
//| Evaluate the guard. Returns GOLDAI_PG_* flags.                    |
//| daily_loss_pct / dd_pct are the GUARD levels (e.g. 4 / 8).        |
//| profit_cap_pct is measured on day_base (0 = off).                |
//| dd_amount: money distance of the DD guard (pct * initial).       |
//| warn_frac: warn when used allowance >= warn_frac (e.g. 0.75).    |
//+------------------------------------------------------------------+
int GoldAI_PropEvaluate(const double equity,
                        const double day_base,
                        const double daily_allowance,
                        const double dd_floor,
                        const double dd_amount,
                        const double profit_cap_pct,
                        const double warn_frac)
  {
   int flags = GOLDAI_PG_OK;
   const double day_loss = day_base - equity;
   if(daily_allowance > 0.0)
     {
      if(day_loss >= daily_allowance)
         flags |= GOLDAI_PG_DAILY_TRIP;
      else if(warn_frac > 0.0 && day_loss >= daily_allowance * warn_frac)
         flags |= GOLDAI_PG_WARN;
     }
   if(dd_floor > 0.0)
     {
      if(equity <= dd_floor)
         flags |= GOLDAI_PG_DD_TRIP;
      else if(warn_frac > 0.0 && dd_amount > 0.0 && (equity - dd_floor) <= dd_amount * (1.0 - warn_frac))
         flags |= GOLDAI_PG_WARN;
     }
   if(profit_cap_pct > 0.0 && day_base > 0.0)
     {
      if((equity - day_base) >= profit_cap_pct / 100.0 * day_base)
         flags |= GOLDAI_PG_PROFIT_CAP;
     }
   return(flags);
  }

//+------------------------------------------------------------------+
//| Would a new trade risking risk_money (x headroom_mult) still fit  |
//| inside both allowances? Writes the reason when it does not.      |
//+------------------------------------------------------------------+
bool GoldAI_PropRiskFits(const double equity,
                         const double day_base,
                         const double daily_allowance,
                         const double dd_floor,
                         const double risk_money,
                         const double headroom_mult,
                         string &why)
  {
   why = "";
   const double need = risk_money * (headroom_mult < 1.0 ? 1.0 : headroom_mult);
   if(daily_allowance > 0.0)
     {
      const double room = daily_allowance - (day_base - equity);
      if(room < need)
        {
         why = "daily room $" + DoubleToString(room, 2) + " < needed $" + DoubleToString(need, 2);
         return(false);
        }
     }
   if(dd_floor > 0.0)
     {
      const double room = equity - dd_floor;
      if(room < need)
        {
         why = "drawdown room $" + DoubleToString(room, 2) + " < needed $" + DoubleToString(need, 2);
         return(false);
        }
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Prop news flat window for one event.                             |
//| earliest/latest release candidates come from the blackout window |
//| (start+before, end-after) so widened "calendar~" records are     |
//| covered on both candidate times.                                 |
//+------------------------------------------------------------------+
bool GoldAI_PropNewsFlatWindow(const datetime now_utc,
                               const datetime start_utc,
                               const datetime end_utc,
                               const int blackout_before_min,
                               const int blackout_after_min,
                               const int flat_before_min,
                               const int flat_after_min,
                               datetime &flat_from,
                               datetime &flat_to)
  {
   datetime earliest = start_utc + (datetime)(MathMax(blackout_before_min, 0) * 60);
   datetime latest   = end_utc   - (datetime)(MathMax(blackout_after_min, 0) * 60);
   if(latest < earliest)
      latest = earliest;
   flat_from = earliest - (datetime)(MathMax(flat_before_min, 0) * 60);
   flat_to   = latest   + (datetime)(MathMax(flat_after_min, 0) * 60);
   return(now_utc >= flat_from && now_utc < flat_to);
  }

//+------------------------------------------------------------------+
string GoldAI_PropFlagsText(const int flags)
  {
   if(flags == GOLDAI_PG_OK)
      return("OK");
   string s = "";
   if((flags & GOLDAI_PG_DD_TRIP) != 0)
      s += "DD-TRIP ";
   if((flags & GOLDAI_PG_DAILY_TRIP) != 0)
      s += "DAILY-TRIP ";
   if((flags & GOLDAI_PG_PROFIT_CAP) != 0)
      s += "PROFIT-CAP ";
   if((flags & GOLDAI_PG_WARN) != 0)
      s += "WARN ";
   StringTrimRight(s);
   return(s);
  }

#endif

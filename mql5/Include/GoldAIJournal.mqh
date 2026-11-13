//+------------------------------------------------------------------+
//| GoldAIJournal.mqh                                                |
//| CSV trade journal in MQL5/Files for later AI review.             |
//+------------------------------------------------------------------+
#ifndef GOLD_AI_JOURNAL_MQH
#define GOLD_AI_JOURNAL_MQH

#include "GoldAIUtil.mqh"

//+------------------------------------------------------------------+
class CGoldAIJournal
  {
private:
   string m_filename;
   bool   m_ready;

   bool EnsureHeader()
     {
      if(m_filename == "")
         return(false);
      // If the file already exists and is non-empty, leave the header alone.
      if(FileIsExist(m_filename))
        {
         const int chk = FileOpen(m_filename, FILE_READ | FILE_TXT | FILE_ANSI);
         if(chk != INVALID_HANDLE)
           {
            const ulong sz = FileSize(chk);
            FileClose(chk);
            if(sz > 0)
               return(true);
           }
        }
      const int h = FileOpen(m_filename, FILE_WRITE | FILE_CSV | FILE_ANSI);
      if(h == INVALID_HANDLE)
        {
         Print("GoldAI journal: cannot create ", m_filename, " err=", GetLastError());
         return(false);
        }
      FileWrite(h,
                "time_utc",
                "event",
                "ticket",
                "symbol",
                "bias",
                "volume",
                "price",
                "sl",
                "tp1",
                "tp2",
                "profit",
                "confidence",
                "decision_generated_at",
                "rationale",
                "details");
      FileClose(h);
      return(true);
     }

public:
   CGoldAIJournal(void)
     {
      m_filename = "";
      m_ready    = false;
     }

   bool Init(const string filename)
     {
      m_filename = filename;
      m_ready = EnsureHeader();
      return(m_ready);
     }

   bool Write(const string event,
              const ulong ticket,
              const string symbol,
              const string bias,
              const double volume,
              const double price,
              const double sl,
              const double tp1,
              const double tp2,
              const double profit,
              const int confidence,
              const datetime decision_generated_at,
              const string rationale,
              const string details)
     {
      if(!m_ready && !Init(m_filename))
         return(false);

      const int h = FileOpen(m_filename, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI);
      if(h == INVALID_HANDLE)
        {
         Print("GoldAI journal: cannot open ", m_filename, " err=", GetLastError());
         return(false);
        }
      FileSeek(h, 0, SEEK_END);
      FileWrite(h,
                GoldAI_TimeToIsoUtc(TimeGMT()),
                event,
                IntegerToString((long)ticket),
                symbol,
                bias,
                DoubleToString(volume, 4),
                DoubleToString(price, _Digits),
                DoubleToString(sl, _Digits),
                DoubleToString(tp1, _Digits),
                DoubleToString(tp2, _Digits),
                DoubleToString(profit, 2),
                IntegerToString(confidence),
                GoldAI_TimeToIsoUtc(decision_generated_at),
                rationale,
                details);
      FileClose(h);
      return(true);
     }
  };

#endif // GOLD_AI_JOURNAL_MQH
//+------------------------------------------------------------------+

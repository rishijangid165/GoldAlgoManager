//+------------------------------------------------------------------+
//| GoldAITelegram.mqh                                               |
//| Non-blocking Telegram alerts for GoldAIBridge.                   |
//| Never log the bot token or the full send URL.                    |
//+------------------------------------------------------------------+
#ifndef GOLD_AI_TELEGRAM_MQH
#define GOLD_AI_TELEGRAM_MQH

//+------------------------------------------------------------------+
string GoldAI_UrlEncode(const string src)
  {
   string out = "";
   const int n = StringLen(src);
   for(int i = 0; i < n; i++)
     {
      const ushort c = StringGetCharacter(src, i);
      const bool unreserved =
         (c >= 'A' && c <= 'Z') ||
         (c >= 'a' && c <= 'z') ||
         (c >= '0' && c <= '9') ||
         c == '-' || c == '_' || c == '.' || c == '~';
      if(unreserved)
        {
         out += ShortToString(c);
        }
      else
        {
         uchar tmp[];
         const string one = ShortToString(c);
         const int k = StringToCharArray(one, tmp, 0, WHOLE_ARRAY, CP_UTF8);
         for(int j = 0; j < k - 1; j++)
            out += StringFormat("%%%02X", tmp[j]);
        }
     }
   return(out);
  }

//+------------------------------------------------------------------+
//| POST sendMessage. Returns false on any failure (caller logs).    |
//| http_status is the WebRequest return (HTTP code, or -1).         |
//+------------------------------------------------------------------+
bool GoldAI_TelegramSend(const bool enabled,
                         const string token,
                         const string chat_id,
                         const int timeout_ms,
                         const string text,
                         int &http_status,
                         string &err)
  {
   http_status = 0;
   err         = "";

   if(!enabled)
     {
      err = "telegram disabled";
      return(false);
     }

   string tok = token;
   string chat = chat_id;
   StringTrimLeft(tok);
   StringTrimRight(tok);
   StringTrimLeft(chat);
   StringTrimRight(chat);
   if(tok == "" || chat == "")
     {
      err = "telegram token or chat id is empty";
      return(false);
     }

   const string url = "https://api.telegram.org/bot" + tok + "/sendMessage";
   const string body = "chat_id=" + GoldAI_UrlEncode(chat) +
                       "&text=" + GoldAI_UrlEncode(text) +
                       "&disable_web_page_preview=true";
   const string headers = "Content-Type: application/x-www-form-urlencoded\r\n";

   char post[];
   char result[];
   string result_headers;
   const int raw_len = StringToCharArray(body, post, 0, WHOLE_ARRAY, CP_UTF8);
   if(raw_len <= 1)
     {
      err = "could not encode telegram body";
      return(false);
     }
   ArrayResize(post, raw_len - 1);

   ResetLastError();
   http_status = WebRequest("POST", url, headers, timeout_ms, post, result, result_headers);
   if(http_status == -1)
     {
      const int le = GetLastError();
      if(le == 4014)
         err = "4014 URL not allowed - add https://api.telegram.org in Tools > Options > Expert Advisors > Allow WebRequest";
      else
         err = "WebRequest failed last_error=" + IntegerToString(le);
      return(false);
     }
   if(http_status != 200)
     {
      err = "HTTP " + IntegerToString(http_status);
      return(false);
     }

   const string resp = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   if(StringFind(resp, "\"ok\":true") < 0 && StringFind(resp, "\"ok\": true") < 0)
     {
      err = "telegram rejected the message";
      return(false);
     }
   return(true);
  }

//+------------------------------------------------------------------+
string GoldAI_DealCloseReason(const long deal_reason, const string pending)
  {
   if(pending != "")
     {
      const string p = pending;
      if(StringFind(p, "expir") >= 0 || StringFind(p, "stale") >= 0 || StringFind(p, "valid_until") >= 0)
         return("expiry");
      return(p);
     }

   if(deal_reason == DEAL_REASON_SL || deal_reason == DEAL_REASON_SO)
      return("SL");
   if(deal_reason == DEAL_REASON_TP)
      return("TP");
   if(deal_reason == DEAL_REASON_CLIENT ||
      deal_reason == DEAL_REASON_MOBILE ||
      deal_reason == DEAL_REASON_WEB)
      return("manual");
   if(deal_reason == DEAL_REASON_EXPERT)
      return("EA");
   return("other");
  }

//+------------------------------------------------------------------+
double GoldAI_PositionNetPnl(const ulong position_id, const double fallback)
  {
   if(position_id != 0 && HistorySelectByPosition(position_id))
     {
      double total = 0.0;
      const int n = HistoryDealsTotal();
      for(int i = 0; i < n; i++)
        {
         const ulong deal = HistoryDealGetTicket(i);
         if(deal == 0)
            continue;
         if((ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) != position_id)
            continue;
         total += HistoryDealGetDouble(deal, DEAL_PROFIT)
                  + HistoryDealGetDouble(deal, DEAL_SWAP)
                  + HistoryDealGetDouble(deal, DEAL_COMMISSION);
        }
      return(total);
     }
   return(fallback);
  }

#endif

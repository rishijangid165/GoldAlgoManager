//+------------------------------------------------------------------+
//| GoldDemoCloseOnce.mq5                                            |
//| Owner-requested one-shot close of demo ticket 11382667647.       |
//+------------------------------------------------------------------+
#property copyright "GoldAlgoManager"
#property version   "1.00"
#property script_show_confirm false
#property script_show_inputs  false

#include <Trade/Trade.mqh>

const long   kExpectedLogin  = <demo-login>;
const string kExpectedServer = "MetaQuotes-Demo";
const string kSymbol         = "XAUUSD";
const ulong  kTicket         = 11382667647;
const string kResultFile     = "GoldDemoCloseOnce_result.txt";

int OnStart()
  {
   string report = "";
   report += "time_utc=" + TimeToString(TimeGMT(), TIME_DATE|TIME_SECONDS) + "\n";
   report += "server_time=" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\n";

   const long login = AccountInfoInteger(ACCOUNT_LOGIN);
   const string server = AccountInfoString(ACCOUNT_SERVER);
   const long mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   report += "login=" + IntegerToString(login) + "\n";
   report += "server=" + server + "\n";
   report += "trade_mode=" + IntegerToString(mode) + " (0=demo,1=contest,2=real)\n";
   report += "company=" + AccountInfoString(ACCOUNT_COMPANY) + "\n";
   report += "balance_initial=" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n";
   report += "equity_initial=" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";

   if(mode != ACCOUNT_TRADE_MODE_DEMO)
     {
      report += "ABORT=not demo account\n";
      return WriteAndExit(report, 1);
     }
   if(login != kExpectedLogin)
     {
      report += "ABORT=unexpected login\n";
      return WriteAndExit(report, 1);
     }
   if(StringFind(server, kExpectedServer) < 0)
     {
      report += "ABORT=unexpected server\n";
      return WriteAndExit(report, 1);
     }

   bool ready = false;
   for(int w=0; w<60; ++w)
     {
      const bool connected = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
      const bool synced = SymbolSelect(kSymbol, true) && SymbolIsSynchronized(kSymbol);
      const double eq = AccountInfoDouble(ACCOUNT_EQUITY);
      if(connected && synced && eq > 1000.0 && AccountInfoInteger(ACCOUNT_LOGIN)==kExpectedLogin)
        {
         ready = true;
         report += "sync_wait_ms=" + IntegerToString(w*500) + "\n";
         break;
        }
      Sleep(500);
     }
   if(!ready)
     {
      report += "ABORT=account/symbol not synchronized (equity=" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),2) + ")\n";
      return WriteAndExit(report, 1);
     }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      report += "ABORT=algo trading not allowed\n";
      return WriteAndExit(report, 1);
     }

   report += "balance_synced=" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n";
   report += "equity_synced=" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";

   const int digits = (int)SymbolInfoInteger(kSymbol, SYMBOL_DIGITS);
   double bid=0, ask=0;
   SymbolInfoDouble(kSymbol, SYMBOL_BID, bid);
   SymbolInfoDouble(kSymbol, SYMBOL_ASK, ask);
   report += "bid=" + DoubleToString(bid, digits) + "\n";
   report += "ask=" + DoubleToString(ask, digits) + "\n";

   if(!PositionSelectByTicket(kTicket))
     {
      report += "position_not_open=1\n";
      DumpTicketHistory(report);
      // If already closed, treat as success if we can see the close deal
      if(StringFind(report, "CLOSE_PRICE=") >= 0)
        {
         report += "VERIFY=already closed before this script\n";
         return WriteAndExit(report, 0);
        }
      report += "ABORT=ticket not found in open positions or close history\n";
      return WriteAndExit(report, 1);
     }

   report += "OPEN_TICKET=" + IntegerToString((long)PositionGetInteger(POSITION_TICKET)) + "\n";
   report += "OPEN_SYMBOL=" + PositionGetString(POSITION_SYMBOL) + "\n";
   report += "OPEN_SIDE=" + (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_SELL ? "SELL" : "BUY") + "\n";
   report += "OPEN_VOLUME=" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + "\n";
   report += "OPEN_PRICE=" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits) + "\n";
   report += "OPEN_SL=" + DoubleToString(PositionGetDouble(POSITION_SL), digits) + "\n";
   report += "OPEN_TP=" + DoubleToString(PositionGetDouble(POSITION_TP), digits) + "\n";
   report += "OPEN_PROFIT=" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + "\n";
   report += "OPEN_SWAP=" + DoubleToString(PositionGetDouble(POSITION_SWAP), 2) + "\n";
   report += "OPEN_MAGIC=" + IntegerToString(PositionGetInteger(POSITION_MAGIC)) + "\n";
   report += "OPEN_COMMENT=" + PositionGetString(POSITION_COMMENT) + "\n";

   if(PositionGetString(POSITION_SYMBOL) != kSymbol)
     {
      report += "ABORT=ticket is not XAUUSD\n";
      return WriteAndExit(report, 1);
     }

   CTrade trade;
   trade.SetExpertMagicNumber(0);
   trade.SetDeviationInPoints(30);
   trade.SetTypeFillingBySymbol(kSymbol);
   trade.SetAsyncMode(false);

   const bool sent = trade.PositionClose(kTicket);
   const uint ret = trade.ResultRetcode();
   report += "sent=" + IntegerToString(sent ? 1 : 0) + "\n";
   report += "retcode=" + IntegerToString((int)ret) + " " + trade.ResultRetcodeDescription() + "\n";
   report += "close_order=" + IntegerToString((long)trade.ResultOrder()) + "\n";
   report += "close_deal=" + IntegerToString((long)trade.ResultDeal()) + "\n";
   report += "close_price_result=" + DoubleToString(trade.ResultPrice(), digits) + "\n";
   report += "close_volume=" + DoubleToString(trade.ResultVolume(), 2) + "\n";
   report += "close_comment=" + trade.ResultComment() + "\n";

   Sleep(800);
   const bool still_open = PositionSelectByTicket(kTicket);
   report += "still_open=" + IntegerToString(still_open ? 1 : 0) + "\n";
   report += "balance_after=" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n";
   report += "equity_after=" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";

   DumpTicketHistory(report);

   if(still_open)
     {
      report += "VERIFY=FAILED still open\n";
      return WriteAndExit(report, 2);
     }
   report += "VERIFY=closed\n";
   return WriteAndExit(report, 0);
  }

void DumpTicketHistory(string &report)
  {
   report += "---- history for ticket " + IntegerToString((long)kTicket) + " ----\n";
   const datetime from = D'2026.11.13 00:00:00';
   const datetime to   = TimeCurrent() + 86400;
   if(!HistorySelect(from, to))
     {
      report += "history_select=fail\n";
      return;
     }
   for(int i=0; i<HistoryDealsTotal(); ++i)
     {
      const ulong deal = HistoryDealGetTicket(i);
      if(deal == 0)
         continue;
      const ulong deal_order = (ulong)HistoryDealGetInteger(deal, DEAL_ORDER);
      const ulong deal_pos   = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      if(deal_order != kTicket && deal_pos != kTicket && deal != kTicket)
         continue;
      const datetime t = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
      const int entry = (int)HistoryDealGetInteger(deal, DEAL_ENTRY);
      const int reason = (int)HistoryDealGetInteger(deal, DEAL_REASON);
      const int typ = (int)HistoryDealGetInteger(deal, DEAL_TYPE);
      const string line =
                "deal=" + IntegerToString((long)deal) +
                " order=" + IntegerToString((long)deal_order) +
                " pos=" + IntegerToString((long)deal_pos) +
                " symbol=" + HistoryDealGetString(deal, DEAL_SYMBOL) +
                " type=" + IntegerToString(typ) +
                " entry=" + IntegerToString(entry) +
                " reason=" + IntegerToString(reason) +
                " vol=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_VOLUME), 2) +
                " price=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_PRICE), 2) +
                " profit=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_PROFIT), 2) +
                " swap=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_SWAP), 2) +
                " commission=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_COMMISSION), 2) +
                " time=" + TimeToString(t, TIME_DATE|TIME_SECONDS) +
                " comment=" + HistoryDealGetString(deal, DEAL_COMMENT) +
                "\n";
      report += line;
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT || entry == DEAL_ENTRY_OUT_BY)
        {
         report += "CLOSE_PRICE=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_PRICE), 2) + "\n";
         report += "CLOSE_PROFIT=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_PROFIT), 2) + "\n";
         report += "CLOSE_SWAP=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_SWAP), 2) + "\n";
         report += "CLOSE_COMMISSION=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_COMMISSION), 2) + "\n";
         report += "CLOSE_TIME_SERVER=" + TimeToString(t, TIME_DATE|TIME_SECONDS) + "\n";
         report += "CLOSE_DEAL=" + IntegerToString((long)deal) + "\n";
         report += "CLOSE_ORDER=" + IntegerToString((long)deal_order) + "\n";
         report += "CLOSE_REASON=" + IntegerToString(reason) + "\n";
         report += "CLOSE_COMMENT=" + HistoryDealGetString(deal, DEAL_COMMENT) + "\n";
        }
     }
  }

int WriteAndExit(const string report, const int code)
  {
   Print(report);
   const int h = FileOpen(kResultFile, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h != INVALID_HANDLE)
     {
      FileWriteString(h, report);
      FileClose(h);
     }
   return code;
  }
//+------------------------------------------------------------------+

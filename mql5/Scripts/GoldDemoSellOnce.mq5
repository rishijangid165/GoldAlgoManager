//+------------------------------------------------------------------+
//| GoldDemoSellOnce.mq5                                             |
//| Owner-requested one-shot DEMO market SELL on XAUUSD.             |
//| Aborts on any non-demo account. Runs once and exits.             |
//+------------------------------------------------------------------+
#property copyright "GoldAlgoManager"
#property version   "1.00"
#property script_show_confirm false
#property script_show_inputs  false

#include <Trade/Trade.mqh>

const long   kExpectedLogin   = <demo-login>;
const string kExpectedServer  = "MetaQuotes-Demo";
const string kSymbol          = "XAUUSD";
const double kSL              = 3945.00;
const double kTP              = 3860.00;
const double kRiskPct         = 0.50;
const int    kSlippagePoints  = 30;
const ulong  kOldOrderTicket  = 11377847166;
const string kResultFile      = "GoldDemoSellOnce_result.txt";

int OnStart()
  {
   string report = "";
   report += "time_utc=" + TimeToString(TimeGMT(), TIME_DATE|TIME_SECONDS) + "\n";
   report += "server_time=" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\n";

   const long login = AccountInfoInteger(ACCOUNT_LOGIN);
   const string server = AccountInfoString(ACCOUNT_SERVER);
   const long mode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   report += "login=" + IntegerToString(login) + "\n";
   report += "server=" + server + "\n";
   report += "trade_mode=" + IntegerToString(mode) + " (0=demo,1=contest,2=real)\n";
   report += "company=" + AccountInfoString(ACCOUNT_COMPANY) + "\n";
   report += "balance=" + DoubleToString(balance, 2) + "\n";
   report += "equity=" + DoubleToString(equity, 2) + "\n";

   DumpOldTicket(report);

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
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      report += "ABORT=algo trading not allowed (terminal or MQL)\n";
      return WriteAndExit(report, 1);
     }

   if(!SymbolSelect(kSymbol, true))
     {
      report += "ABORT=cannot select XAUUSD\n";
      return WriteAndExit(report, 1);
     }

   // StartUp can run before the account is synchronized (equity=0). Wait.
   bool ready = false;
   double wait_equity = 0;
   for(int w=0; w<60; ++w)
     {
      const bool connected = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
      const bool synced = SymbolIsSynchronized(kSymbol);
      wait_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      if(connected && synced && wait_equity > 1000.0 && AccountInfoInteger(ACCOUNT_LOGIN)==kExpectedLogin)
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

   const double equity2 = AccountInfoDouble(ACCOUNT_EQUITY);
   const double balance2 = AccountInfoDouble(ACCOUNT_BALANCE);
   report += "balance_synced=" + DoubleToString(balance2, 2) + "\n";
   report += "equity_synced=" + DoubleToString(equity2, 2) + "\n";

   double bid=0, ask=0;
   if(!SymbolInfoDouble(kSymbol, SYMBOL_BID, bid) || !SymbolInfoDouble(kSymbol, SYMBOL_ASK, ask) || bid <= 0 || ask <= 0)
     {
      report += "ABORT=no quote\n";
      return WriteAndExit(report, 1);
     }
   const double point = SymbolInfoDouble(kSymbol, SYMBOL_POINT);
   const int digits = (int)SymbolInfoInteger(kSymbol, SYMBOL_DIGITS);
   const double tick_size = SymbolInfoDouble(kSymbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(kSymbol, SYMBOL_TRADE_TICK_VALUE);
   const double vmin = SymbolInfoDouble(kSymbol, SYMBOL_VOLUME_MIN);
   const double vmax = SymbolInfoDouble(kSymbol, SYMBOL_VOLUME_MAX);
   const double vstep = SymbolInfoDouble(kSymbol, SYMBOL_VOLUME_STEP);
   const double contract = SymbolInfoDouble(kSymbol, SYMBOL_TRADE_CONTRACT_SIZE);
   report += "bid=" + DoubleToString(bid, digits) + "\n";
   report += "ask=" + DoubleToString(ask, digits) + "\n";
   report += "spread=" + DoubleToString((ask-bid)/point, 1) + " points\n";
   report += "contract=" + DoubleToString(contract, 2) + "\n";
   report += "tick_size=" + DoubleToString(tick_size, digits) + "\n";
   report += "tick_value_raw=" + DoubleToString(tick_value, 5) + "\n";
   const double tick_value_expected = tick_size * contract;
   report += "tick_value_expected=" + DoubleToString(tick_value_expected, 5) + "\n";
   if(tick_value_expected > 0 && (tick_value <= 0 || tick_value < tick_value_expected * 0.5 || tick_value > tick_value_expected * 2.0))
     {
      report += "tick_value_adjusted_from_contract=1\n";
      tick_value = tick_value_expected;
     }
   report += "tick_value=" + DoubleToString(tick_value, 5) + "\n";

   int open_positions = 0;
   for(int i=PositionsTotal()-1; i>=0; --i)
     {
      const ulong pt = PositionGetTicket(i);
      if(pt == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == kSymbol)
        {
         open_positions++;
         report += "existing_position ticket=" + IntegerToString((long)pt) +
                   " type=" + IntegerToString(PositionGetInteger(POSITION_TYPE)) +
                   " vol=" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) +
                   " price=" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits) + "\n";
        }
     }
   if(open_positions > 0)
     {
      report += "ABORT=already have an open XAUUSD position; will not add another\n";
      return WriteAndExit(report, 1);
     }

   if(bid >= kSL)
     {
      report += "ABORT=bid " + DoubleToString(bid, digits) + " is already at/above SL " + DoubleToString(kSL, 2) + "\n";
      return WriteAndExit(report, 1);
     }
   if(bid <= kTP)
     {
      report += "ABORT=bid already at/through TP\n";
      return WriteAndExit(report, 1);
     }

   const double sl_dist = kSL - bid;
   const double tp_dist = bid - kTP;
   const double rr = (sl_dist > 0 ? tp_dist / sl_dist : 0);
   report += "sl=" + DoubleToString(kSL, 2) + "\n";
   report += "tp=" + DoubleToString(kTP, 2) + "\n";
   report += "sl_dist=" + DoubleToString(sl_dist, 2) + "\n";
   report += "tp_dist=" + DoubleToString(tp_dist, 2) + "\n";
   report += "rr=" + DoubleToString(rr, 2) + "\n";

   if(tick_size <= 0 || tick_value <= 0)
     {
      report += "ABORT=bad tick size/value\n";
      return WriteAndExit(report, 1);
     }
   equity = AccountInfoDouble(ACCOUNT_EQUITY);
   balance = AccountInfoDouble(ACCOUNT_BALANCE);
   const double risk_money = equity * (kRiskPct / 100.0);
   const double loss_per_lot = (sl_dist / tick_size) * tick_value;
   if(loss_per_lot <= 0)
     {
      report += "ABORT=loss_per_lot <= 0\n";
      return WriteAndExit(report, 1);
     }
   double lots = risk_money / loss_per_lot;
   if(vstep > 0)
      lots = MathFloor(lots / vstep) * vstep;
   lots = NormalizeDouble(lots, 2);
   if(lots > vmax)
      lots = vmax;
   report += "risk_money=" + DoubleToString(risk_money, 2) + "\n";
   report += "loss_per_lot=" + DoubleToString(loss_per_lot, 2) + "\n";
   report += "lots_raw_calc=" + DoubleToString(risk_money / loss_per_lot, 4) + "\n";
   report += "lots=" + DoubleToString(lots, 2) + "\n";
   if(lots < vmin)
     {
      report += "ABORT=calculated lots below minimum " + DoubleToString(vmin, 2) + "\n";
      return WriteAndExit(report, 1);
     }
   const double actual_risk = lots * loss_per_lot;
   report += "actual_risk=" + DoubleToString(actual_risk, 2) + "\n";

   CTrade trade;
   trade.SetExpertMagicNumber(0);
   trade.SetDeviationInPoints(kSlippagePoints);
   trade.SetTypeFillingBySymbol(kSymbol);
   trade.SetAsyncMode(false);

   const bool sent = trade.Sell(lots, kSymbol, bid, kSL, kTP, "owner-requested-demo");
   const uint ret = trade.ResultRetcode();
   const ulong order_id = trade.ResultOrder();
   const ulong deal_id = trade.ResultDeal();
   const double fill = trade.ResultPrice();
   const double fill_vol = trade.ResultVolume();
   report += "sent=" + IntegerToString(sent ? 1 : 0) + "\n";
   report += "retcode=" + IntegerToString((int)ret) + " " + trade.ResultRetcodeDescription() + "\n";
   report += "order=" + IntegerToString((long)order_id) + "\n";
   report += "deal=" + IntegerToString((long)deal_id) + "\n";
   report += "fill_price=" + DoubleToString(fill, digits) + "\n";
   report += "fill_volume=" + DoubleToString(fill_vol, 2) + "\n";
   report += "comment=" + trade.ResultComment() + "\n";

   Sleep(500);
   bool found = false;
   for(int i=PositionsTotal()-1; i>=0; --i)
     {
      const ulong pt = PositionGetTicket(i);
      if(pt == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != kSymbol)
         continue;
      found = true;
      report += "OPEN_TICKET=" + IntegerToString((long)pt) + "\n";
      report += "OPEN_SIDE=" + (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_SELL ? "SELL" : "BUY") + "\n";
      report += "OPEN_VOLUME=" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + "\n";
      report += "OPEN_PRICE=" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits) + "\n";
      report += "OPEN_SL=" + DoubleToString(PositionGetDouble(POSITION_SL), digits) + "\n";
      report += "OPEN_TP=" + DoubleToString(PositionGetDouble(POSITION_TP), digits) + "\n";
      report += "OPEN_MAGIC=" + IntegerToString(PositionGetInteger(POSITION_MAGIC)) + "\n";
      report += "OPEN_COMMENT=" + PositionGetString(POSITION_COMMENT) + "\n";
     }
   if(!found)
      report += "VERIFY=no open position found after send\n";
   else
      report += "VERIFY=position open\n";

   return WriteAndExit(report, sent && found ? 0 : 2);
  }

void DumpOldTicket(string &report)
  {
   report += "---- old ticket " + IntegerToString((long)kOldOrderTicket) + " ----\n";
   const datetime from = D'2026.11.12 00:00:00';
   const datetime to   = TimeCurrent() + 86400;
   if(!HistorySelect(from, to))
     {
      report += "old_history_select=fail\n";
      return;
     }
   report += "history_deals=" + IntegerToString(HistoryDealsTotal()) + "\n";
   report += "history_orders=" + IntegerToString(HistoryOrdersTotal()) + "\n";
   bool any = false;
   for(int i=0; i<HistoryDealsTotal(); ++i)
     {
      const ulong deal = HistoryDealGetTicket(i);
      if(deal == 0)
         continue;
      const ulong deal_order = (ulong)HistoryDealGetInteger(deal, DEAL_ORDER);
      const ulong deal_pos   = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      const string sym = HistoryDealGetString(deal, DEAL_SYMBOL);
      if(deal_order != kOldOrderTicket && deal_pos != kOldOrderTicket && deal != kOldOrderTicket && deal != 11135687590)
         if(sym != kSymbol)
            continue;
      any = true;
      const datetime t = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
      const int entry = (int)HistoryDealGetInteger(deal, DEAL_ENTRY);
      const int reason = (int)HistoryDealGetInteger(deal, DEAL_REASON);
      const int typ = (int)HistoryDealGetInteger(deal, DEAL_TYPE);
      report += "deal=" + IntegerToString((long)deal) +
                " order=" + IntegerToString((long)deal_order) +
                " pos=" + IntegerToString((long)deal_pos) +
                " symbol=" + sym +
                " type=" + IntegerToString(typ) +
                " entry=" + IntegerToString(entry) +
                " reason=" + IntegerToString(reason) +
                " vol=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_VOLUME), 2) +
                " price=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_PRICE), 2) +
                " profit=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_PROFIT), 2) +
                " swap=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_SWAP), 2) +
                " commission=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_COMMISSION), 2) +
                " sl=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_SL), 2) +
                " tp=" + DoubleToString(HistoryDealGetDouble(deal, DEAL_TP), 2) +
                " time=" + TimeToString(t, TIME_DATE|TIME_SECONDS) +
                " comment=" + HistoryDealGetString(deal, DEAL_COMMENT) +
                "\n";
     }
   for(int i=0; i<HistoryOrdersTotal(); ++i)
     {
      const ulong ord = HistoryOrderGetTicket(i);
      if(ord == 0)
         continue;
      if(ord != kOldOrderTicket && (ulong)HistoryOrderGetInteger(ord, ORDER_POSITION_ID) != kOldOrderTicket)
         continue;
      any = true;
      report += "order=" + IntegerToString((long)ord) +
                " state=" + IntegerToString(HistoryOrderGetInteger(ord, ORDER_STATE)) +
                " reason=" + IntegerToString(HistoryOrderGetInteger(ord, ORDER_REASON)) +
                " price_open=" + DoubleToString(HistoryOrderGetDouble(ord, ORDER_PRICE_OPEN), 2) +
                " sl=" + DoubleToString(HistoryOrderGetDouble(ord, ORDER_SL), 2) +
                " tp=" + DoubleToString(HistoryOrderGetDouble(ord, ORDER_TP), 2) +
                " setup=" + TimeToString((datetime)HistoryOrderGetInteger(ord, ORDER_TIME_SETUP), TIME_DATE|TIME_SECONDS) +
                " done=" + TimeToString((datetime)HistoryOrderGetInteger(ord, ORDER_TIME_DONE), TIME_DATE|TIME_SECONDS) +
                " comment=" + HistoryOrderGetString(ord, ORDER_COMMENT) +
                "\n";
     }
   if(!any)
      report += "old_ticket_not_found_in_history\n";
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
   else
      Print("failed to write result file");
   return code;
  }
//+------------------------------------------------------------------+

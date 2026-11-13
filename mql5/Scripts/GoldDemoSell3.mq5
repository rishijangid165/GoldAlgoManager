//+------------------------------------------------------------------+
//| GoldDemoSellOnce.mq5                                             |
//| Owner-requested one-shot DEMO market SELL on XAUUSD.             |
//| Aborts on any non-demo account. Runs once and exits.             |
//| Will not modify or close any existing position (including        |
//| ticket 11388939566). May open an additional SELL on a hedge      |
//| demo account.                                                    |
//+------------------------------------------------------------------+
#property copyright "GoldAlgoManager"
#property version   "1.02"
#property script_show_inputs  false

#include <Trade/Trade.mqh>

const long   kExpectedLogin   = <demo-login>;
const string kExpectedServer  = "MetaQuotes-Demo";
const string kSymbol          = "XAUUSD";
const double kSL              = 3906.00;
const double kTP              = 3866.00;
const double kRiskPct         = 0.50;
const int    kSlippagePoints  = 30;
const string kComment         = "owner-requested-demo-3";
const ulong  kProtectedTicket = 11388939566;
const string kResultFile      = "GoldDemoSellOnce3_result.txt";

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
   for(int w=0; w<60; ++w)
     {
      const bool connected = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
      const bool synced = SymbolIsSynchronized(kSymbol);
      if(connected && synced && AccountInfoDouble(ACCOUNT_EQUITY) > 1000.0 && AccountInfoInteger(ACCOUNT_LOGIN)==kExpectedLogin)
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

   // Log existing positions. Do not close or modify them.
   bool already_have_this_comment = false;
   bool protected_still_open = false;
   for(int i=PositionsTotal()-1; i>=0; --i)
     {
      const ulong pt = PositionGetTicket(i);
      if(pt == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != kSymbol)
         continue;
      const string cmt = PositionGetString(POSITION_COMMENT);
      report += "existing_position ticket=" + IntegerToString((long)pt) +
                " type=" + IntegerToString(PositionGetInteger(POSITION_TYPE)) +
                " vol=" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) +
                " price=" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits) +
                " sl=" + DoubleToString(PositionGetDouble(POSITION_SL), digits) +
                " tp=" + DoubleToString(PositionGetDouble(POSITION_TP), digits) +
                " comment=" + cmt + "\n";
      if(pt == kProtectedTicket)
         protected_still_open = true;
      if(cmt == kComment)
         already_have_this_comment = true;
     }
   report += "protected_ticket=" + IntegerToString((long)kProtectedTicket) +
             " still_open=" + IntegerToString(protected_still_open ? 1 : 0) +
             " (will not modify)\n";
   if(already_have_this_comment)
     {
      report += "ABORT=already have a position with comment " + kComment + "; will not add another\n";
      return WriteAndExit(report, 1);
     }

   // Planned SL 3906 / TP 3866 only if SL distance is $8-$30; otherwise SL=entry+18, TP=entry-22.
   double sl = kSL;
   double tp = kTP;
   double sl_dist_plan = sl - bid;
   report += "planned_sl=" + DoubleToString(kSL, 2) + "\n";
   report += "planned_tp=" + DoubleToString(kTP, 2) + "\n";
   report += "planned_sl_dist=" + DoubleToString(sl_dist_plan, 2) + "\n";
   if(sl_dist_plan < 8.0 || sl_dist_plan > 30.0)
     {
      sl = NormalizeDouble(bid + 18.0, digits);
      tp = NormalizeDouble(bid - 22.0, digits);
      report += "sl_tp_adjusted=1 (planned SL distance outside 8-30)\n";
     }
   else
      report += "sl_tp_adjusted=0\n";

   if(bid >= sl)
     {
      report += "ABORT=bid " + DoubleToString(bid, digits) + " is already at/above SL " + DoubleToString(sl, 2) + "\n";
      return WriteAndExit(report, 1);
     }
   if(bid <= tp)
     {
      report += "ABORT=bid already at/through TP\n";
      return WriteAndExit(report, 1);
     }

   const double sl_dist = sl - bid;
   const double tp_dist = bid - tp;
   const double rr = (sl_dist > 0 ? tp_dist / sl_dist : 0);
   report += "sl=" + DoubleToString(sl, 2) + "\n";
   report += "tp=" + DoubleToString(tp, 2) + "\n";
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

   const bool sent = trade.Sell(lots, kSymbol, bid, sl, tp, kComment);
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
   bool found_new = false;
   bool protected_after = false;
   int xau_open = 0;
   for(int i=PositionsTotal()-1; i>=0; --i)
     {
      const ulong pt = PositionGetTicket(i);
      if(pt == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != kSymbol)
         continue;
      xau_open++;
      const string cmt = PositionGetString(POSITION_COMMENT);
      report += "OPEN_TICKET=" + IntegerToString((long)pt) + "\n";
      report += "OPEN_SIDE=" + (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_SELL ? "SELL" : "BUY") + "\n";
      report += "OPEN_VOLUME=" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + "\n";
      report += "OPEN_PRICE=" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits) + "\n";
      report += "OPEN_SL=" + DoubleToString(PositionGetDouble(POSITION_SL), digits) + "\n";
      report += "OPEN_TP=" + DoubleToString(PositionGetDouble(POSITION_TP), digits) + "\n";
      report += "OPEN_MAGIC=" + IntegerToString(PositionGetInteger(POSITION_MAGIC)) + "\n";
      report += "OPEN_COMMENT=" + cmt + "\n";
      if(pt == kProtectedTicket)
         protected_after = true;
      if(cmt == kComment || pt == order_id)
         found_new = true;
     }
   report += "protected_still_open_after=" + IntegerToString(protected_after ? 1 : 0) + "\n";
   report += "xau_open_after=" + IntegerToString(xau_open) + "\n";
   if(!found_new)
      report += "VERIFY=new " + kComment + " position not found after send\n";
   else
      report += "VERIFY=new position open; existing tickets left untouched\n";

   return WriteAndExit(report, sent && found_new ? 0 : 2);
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

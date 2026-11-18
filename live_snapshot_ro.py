# Read-only live snapshot for the paper tracker and dashboard. No orders, no position changes.
import sys, json
sys.path.insert(0, r"C:\winpy\Lib\site-packages")
import MetaTrader5 as mt5
from datetime import datetime, timezone
OUT = r"C:\winpy\broker"
n_h1 = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
ok = mt5.initialize(path=r"C:\MT5\terminal64.exe")
snap = {"init": bool(ok), "error": str(mt5.last_error()), "pulled_at_utc": datetime.now(timezone.utc).isoformat()}
if ok:
    i = mt5.account_info()
    snap["account"] = {"server": i.server, "trade_mode": i.trade_mode, "currency": i.currency,
                       "balance": i.balance, "equity": i.equity, "margin": i.margin, "profit": i.profit}
    snap["positions"] = [{"ticket": p.ticket, "symbol": p.symbol, "type": p.type, "volume": p.volume,
                          "price_open": p.price_open, "sl": p.sl, "tp": p.tp, "price_current": p.price_current,
                          "profit": p.profit, "magic": p.magic, "comment": p.comment, "time": p.time}
                         for p in (mt5.positions_get() or [])]
    t = mt5.symbol_info_tick("XAUUSD")
    if t is not None:
        snap["tick"] = {"bid": t.bid, "ask": t.ask, "time_server": t.time}
    fr = datetime(2026, 11, 1, tzinfo=timezone.utc)
    deals = mt5.history_deals_get(fr, datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1)) or []
    snap["deals"] = [{"ticket": d.ticket, "order": d.order, "position_id": d.position_id, "time_utc_epoch_server": d.time,
                      "symbol": d.symbol, "type": d.type, "entry": d.entry, "volume": d.volume, "price": d.price,
                      "profit": d.profit, "swap": d.swap, "commission": d.commission, "fee": getattr(d, "fee", 0.0),
                      "magic": d.magic, "reason": d.reason, "comment": d.comment} for d in deals]
    orders = mt5.history_orders_get(fr, datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1)) or []
    snap["orders"] = [{"ticket": o.ticket, "position_id": o.position_id, "time_setup": o.time_setup, "type": o.type,
                       "volume_initial": o.volume_initial, "price_open": o.price_open, "sl": o.sl, "tp": o.tp,
                       "magic": o.magic, "comment": o.comment, "symbol": o.symbol} for o in orders]
    r = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, n_h1)
    snap["h1_rows"] = 0 if r is None else len(r)
    if r is not None and len(r):
        with open(OUT + "\\live_H1.csv", "w") as f:
            f.write("time,open,high,low,close,tick_volume,spread,real_volume\n")
            for x in r:
                f.write("%d,%.2f,%.2f,%.2f,%.2f,%d,%d,%d\n" % (x['time'], x['open'], x['high'], x['low'], x['close'], x['tick_volume'], x['spread'], x['real_volume']))
    mt5.shutdown()
with open(OUT + "\\live_snapshot.json", "w") as f:
    json.dump(snap, f)
print(json.dumps({k: v for k, v in snap.items() if k not in ("positions", "deals", "orders")}))

# Read-only broker XAUUSD history pull. No orders, no order_send, no position changes.
import sys, time
sys.path.insert(0, r"C:\winpy\Lib\site-packages")
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
OUT = r"C:\winpy\broker"
import os; os.makedirs(OUT, exist_ok=True)
ok = mt5.initialize(path=r"C:\MT5\terminal64.exe")
print("init", ok, mt5.last_error())
i = mt5.account_info(); print("server", i.server, "demo_mode", i.trade_mode)
si = mt5.symbol_info("XAUUSD"); print("point", si.point, "digits", si.digits, "spread_now", si.spread, "contract", si.trade_contract_size)
ti = mt5.terminal_info(); print("maxbars", ti.maxbars)
now = datetime.now(timezone.utc) + timedelta(days=1)
tfs = [("M1", mt5.TIMEFRAME_M1), ("M15", mt5.TIMEFRAME_M15), ("H1", mt5.TIMEFRAME_H1), ("H4", mt5.TIMEFRAME_H4), ("D1", mt5.TIMEFRAME_D1)]
for name, tf in tfs:
    best = None
    for start_year in (2000, 2005, 2010, 2015, 2018, 2020, 2022, 2024, 2025, 2026):
        fr = datetime(start_year, 1, 1, tzinfo=timezone.utc)
        r = None
        for attempt in range(4):
            r = mt5.copy_rates_range("XAUUSD", tf, fr, now)
            if r is not None and len(r) > 0: break
            time.sleep(2)
        n = 0 if r is None else len(r)
        print(name, "from", start_year, "rows", n, mt5.last_error())
        if n > 0:
            best = r; break
    # also try copy_rates_from_pos with a large count, in case range is limited
    r2 = mt5.copy_rates_from_pos("XAUUSD", tf, 0, 5000000 if name=="M1" else 500000)
    n2 = 0 if r2 is None else len(r2)
    print(name, "from_pos rows", n2, mt5.last_error())
    if r2 is not None and (best is None or len(r2) > len(best)): best = r2
    if best is None: continue
    with open(OUT + "\\XAUUSD_%s.csv" % name, "w") as f:
        f.write("time,open,high,low,close,tick_volume,spread,real_volume\n")
        for x in best:
            f.write("%d,%.2f,%.2f,%.2f,%.2f,%d,%d,%d\n" % (x['time'], x['open'], x['high'], x['low'], x['close'], x['tick_volume'], x['spread'], x['real_volume']))
    print("WROTE", name, len(best), datetime.fromtimestamp(int(best[0]['time']), timezone.utc), "->", datetime.fromtimestamp(int(best[-1]['time']), timezone.utc))
mt5.shutdown()

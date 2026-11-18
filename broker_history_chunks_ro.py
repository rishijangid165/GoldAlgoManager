# Read-only chunked broker XAUUSD history pull (terminal maxbars=100000 caps one request). No orders.
import sys, time
sys.path.insert(0, r"C:\winpy\Lib\site-packages")
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
OUT = r"C:\winpy\broker"
ok = mt5.initialize(path=r"C:\MT5\terminal64.exe"); print("init", ok, mt5.last_error())
end = datetime(2026, 11, 15, tzinfo=timezone.utc)
plan = [("M1", mt5.TIMEFRAME_M1, timedelta(days=30), datetime(2009,1,1,tzinfo=timezone.utc)),
        ("M15", mt5.TIMEFRAME_M15, timedelta(days=365), datetime(2004,1,1,tzinfo=timezone.utc)),
        ("H1", mt5.TIMEFRAME_H1, timedelta(days=365*3), datetime(2004,1,1,tzinfo=timezone.utc))]
for name, tf, step, floor in plan:
    rows = {}
    hi = end; empties = 0
    while hi > floor and empties < 3:
        lo = hi - step
        r = None
        for a in range(3):
            r = mt5.copy_rates_range("XAUUSD", tf, lo, hi)
            if r is not None and len(r) > 0: break
            time.sleep(1.5)
        n = 0 if r is None else len(r)
        print(name, lo.date(), hi.date(), n, mt5.last_error() if n == 0 else "", flush=True)
        if n == 0: empties += 1
        else:
            empties = 0
            for x in r: rows[int(x['time'])] = x
        hi = lo
    ks = sorted(rows)
    if not ks: continue
    with open(OUT + "\\XAUUSD_%s_chunked.csv" % name, "w") as f:
        f.write("time,open,high,low,close,tick_volume,spread,real_volume\n")
        for k in ks:
            x = rows[k]
            f.write("%d,%.2f,%.2f,%.2f,%.2f,%d,%d,%d\n" % (x['time'], x['open'], x['high'], x['low'], x['close'], x['tick_volume'], x['spread'], x['real_volume']))
    print("WROTE", name, len(ks), datetime.fromtimestamp(ks[0], timezone.utc), "->", datetime.fromtimestamp(ks[-1], timezone.utc), flush=True)
mt5.shutdown()

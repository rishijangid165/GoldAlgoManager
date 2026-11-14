# Read-only deep broker XAUUSD history pull (yearly/monthly chunks). No orders, no settings changes.
import sys, time
sys.path.insert(0, r"C:\winpy\Lib\site-packages")
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
OUT = r"C:\winpy\broker"
ok = mt5.initialize(path=r"C:\MT5\terminal64.exe"); print("init", ok, mt5.last_error(), "maxbars", mt5.terminal_info().maxbars, flush=True)
end = datetime(2026, 11, 15, tzinfo=timezone.utc)
which = sys.argv[1:] or ["H1", "M15", "M5", "M1"]
TF = {"M1": (mt5.TIMEFRAME_M1, 30), "M5": (mt5.TIMEFRAME_M5, 120), "M15": (mt5.TIMEFRAME_M15, 365), "H1": (mt5.TIMEFRAME_H1, 365*3)}
for name in which:
    tf, days = TF[name]
    rows = {}; hi = end; empties = 0
    while hi > datetime(2003,1,1,tzinfo=timezone.utc) and empties < 4:
        lo = hi - timedelta(days=days)
        r = None
        for a in range(4):
            r = mt5.copy_rates_range("XAUUSD", tf, lo, hi)
            if r is not None and len(r) > 1: break
            time.sleep(2)
        n = 0 if r is None else len(r)
        print(name, lo.date(), hi.date(), n, flush=True)
        if n <= 1: empties += 1
        else:
            empties = 0
            for x in r: rows[int(x['time'])] = x
        hi = lo
    ks = sorted(rows)
    if not ks: continue
    with open(OUT + "\\XAUUSD_%s_deep.csv" % name, "w") as f:
        f.write("time,open,high,low,close,tick_volume,spread,real_volume\n")
        for k in ks:
            x = rows[k]
            f.write("%d,%.2f,%.2f,%.2f,%.2f,%d,%d,%d\n" % (x['time'], x['open'], x['high'], x['low'], x['close'], x['tick_volume'], x['spread'], x['real_volume']))
    print("WROTE", name, len(ks), datetime.fromtimestamp(ks[0], timezone.utc), "->", datetime.fromtimestamp(ks[-1], timezone.utc), flush=True)
mt5.shutdown()

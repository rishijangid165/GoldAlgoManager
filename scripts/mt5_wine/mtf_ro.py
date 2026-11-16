# Read-only multi-timeframe dump. No orders.
import sys
sys.path.insert(0, r"C:\winpy\Lib\site-packages")
import MetaTrader5 as mt5
mt5.initialize(path=r"C:\MT5\terminal64.exe")
for tf,n,name in ((mt5.TIMEFRAME_D1,260,"D1"),(mt5.TIMEFRAME_H4,300,"H4"),(mt5.TIMEFRAME_H1,300,"H1"),(mt5.TIMEFRAME_M15,300,"M15")):
    r=mt5.copy_rates_from_pos("XAUUSD", tf, 0, n)
    with open(r"C:\winpy\broker\mtf_%s.csv"%name,"w") as f:
        f.write("time,open,high,low,close\n")
        for x in r: f.write("%d,%.2f,%.2f,%.2f,%.2f\n"%(x['time'],x['open'],x['high'],x['low'],x['close']))
mt5.shutdown()

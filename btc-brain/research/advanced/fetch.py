import json,time,urllib.request,csv,calendar
now=int(json.load(urllib.request.urlopen("https://api.india.delta.exchange/v2/tickers/BTCUSD"))['result']['timestamp'])//1_000_000
start=calendar.timegm((2025,10,1,0,0,0))
ist=lambda k: time.strftime('%Y-%m-%d %H:%M',time.gmtime(k+19800))
print("now",ist(now),"IST")
for res,sec in [("15m",900),("1h",3600),("4h",14400),("1d",86400)]:
    rows={}; s=start
    while s<now:
        e=min(now,s+sec*1000)
        for attempt in range(3):
            try:
                r=json.load(urllib.request.urlopen(f"https://api.india.delta.exchange/v2/history/candles?resolution={res}&symbol=BTCUSD&start={s}&end={e}",timeout=30))['result']; break
            except Exception as ex: time.sleep(2)
        for c in r: rows[c['time']]=c
        s=e; time.sleep(0.2)
    ks=[k for k in sorted(rows) if k+sec<=now]  # complete candles only
    with open(f"delta_{res}.csv","w",newline="") as f:
        w=csv.writer(f); w.writerow(["time","ist","open","high","low","close","volume"])
        for k in ks: c=rows[k]; w.writerow([k,ist(k),c['open'],c['high'],c['low'],c['close'],c['volume']])
    print(res,len(ks),ist(ks[0]),"->",ist(ks[-1]))
# Binance 1h for cross-check of spikes
rows=[]; s=start*1000
while s<now*1000:
    r=json.load(urllib.request.urlopen(f"https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime={s}&limit=1000",timeout=30))
    if not r: break
    rows+=r; s=r[-1][0]+3600_000; time.sleep(0.2)
with open("binance_1h.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["time","open","high","low","close","volume"])
    for x in rows:
        if x[0]//1000+3600<=now: w.writerow([x[0]//1000]+x[1:6])
print("binance 1h",len(rows))

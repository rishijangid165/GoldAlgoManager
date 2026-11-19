import json,time,urllib.request,csv,calendar
now=int(json.load(urllib.request.urlopen("https://api.india.delta.exchange/v2/tickers/BTCUSD"))['result']['timestamp'])//1_000_000
start=calendar.timegm((2026,7,20,0,0,0))  # 20 Jul for warmup (EMA/ADX); test from 20 Aug
print("now",now,time.strftime('%Y-%m-%d %H:%M',time.gmtime(now+19800)),"IST")
for res,sec in [("1h",3600),("4h",14400)]:
    rows={}
    s=start
    while s<now:
        e=min(now,s+sec*1500)
        u=f"https://api.india.delta.exchange/v2/history/candles?resolution={res}&symbol=BTCUSD&start={s}&end={e}"
        r=json.load(urllib.request.urlopen(u))['result']
        for c in r: rows[c['time']]=c
        s=e; time.sleep(0.3)
    ks=sorted(rows)
    with open(f"btc_{res}.csv","w",newline="") as f:
        w=csv.writer(f); w.writerow(["time","ist","open","high","low","close","volume"])
        for k in ks:
            c=rows[k]; w.writerow([k,time.strftime('%Y-%m-%d %H:%M',time.gmtime(k+19800)),c['open'],c['high'],c['low'],c['close'],c['volume']])
    gaps=[(ks[i-1],ks[i]) for i in range(1,len(ks)) if ks[i]-ks[i-1]!=sec]
    print(res,len(ks),time.strftime('%Y-%m-%d %H:%M',time.gmtime(ks[0]+19800)),time.strftime('%Y-%m-%d %H:%M',time.gmtime(ks[-1]+19800)),"gaps",len(gaps),gaps[:5])

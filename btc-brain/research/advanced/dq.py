import csv,statistics as st,time,json
ist=lambda k: time.strftime('%Y-%m-%d %H:%M',time.gmtime(k+19800))
def load(fn):
    with open(fn) as f: return [dict(t=int(r['time']),o=float(r['open']),h=float(r['high']),l=float(r['low']),c=float(r['close']),v=float(r['volume'])) for r in csv.DictReader(f)]
out={}
for res,sec in [("15m",900),("1h",3600),("4h",14400),("1d",86400)]:
    b=load(f"delta_{res}.csv")
    gaps=[(ist(b[i-1]['t']),ist(b[i]['t']),(b[i]['t']-b[i-1]['t'])//sec-1) for i in range(1,len(b)) if b[i]['t']-b[i-1]['t']!=sec]
    bad=[ist(x['t']) for x in b if not (x['l']<=min(x['o'],x['c']) and x['h']>=max(x['o'],x['c']) and x['l']>0)]
    zero=sum(1 for x in b if x['v']==0)
    # spikes: range > 6x median range of previous 100 bars, or |close/prev close -1| > 6 sigma (rolling 500)
    rng=[x['h']-x['l'] for x in b]; sp=[]
    for i in range(100,len(b)):
        med=st.median(rng[i-100:i])
        if med>0 and rng[i]>6*med: sp.append((ist(b[i]['t']),round(rng[i]/med,1),round((b[i]['c']/b[i-1]['c']-1)*100,2)))
    out[res]=dict(n=len(b),first=ist(b[0]['t']),last=ist(b[-1]['t']),gaps=gaps,ohlc_errors=bad,zero_volume=zero,spikes=sp)
    print(res,"n",len(b),"gaps",len(gaps),gaps[:5],"ohlc_err",len(bad),"zero_vol",zero,"spikes(>6x median range)",len(sp))
    for s in sp[:15]: print("   spike",s)
# Delta vs Binance 1h close
d={x['t']:x for x in load("delta_1h.csv")}
bn={}
with open("binance_1h.csv") as f:
    for r in csv.DictReader(f): bn[int(r['time'])]=dict(c=float(r['close']),h=float(r['high']),l=float(r['low']))
diffs=[(t,(d[t]['c']/bn[t]['c']-1)*100) for t in d if t in bn]
ad=[abs(x) for _,x in diffs]
big=[(ist(t),round(x,2)) for t,x in diffs if abs(x)>0.5]
wick=[(ist(t),round((d[t]['h']/bn[t]['h']-1)*100,2),round((d[t]['l']/bn[t]['l']-1)*100,2)) for t in d if t in bn and (abs(d[t]['h']/bn[t]['h']-1)>0.5/100 or abs(d[t]['l']/bn[t]['l']-1)>0.5/100)]
print("Delta vs Binance 1h close diff %: n",len(diffs),"mean",round(st.mean(x for _,x in diffs),3),"median abs",round(st.median(ad),3),"p99 abs",round(sorted(ad)[int(.99*len(ad))],3),"max abs",round(max(ad),3),">0.5%:",len(big),big[:10])
print("high/low differ >0.5% vs Binance:",len(wick),wick[:10])
out['vs_binance']=dict(n=len(diffs),median_abs=st.median(ad),p99=sorted(ad)[int(.99*len(ad))],max=max(ad),big=big,wick=wick)
json.dump(out,open("data_quality.json","w"),indent=1)

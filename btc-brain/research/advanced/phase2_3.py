import json,urllib.request,time
from collections import Counter
import engine as E
now=int(json.load(urllib.request.urlopen("https://api.india.delta.exchange/v2/tickers/BTCUSD"))['result']['timestamp'])//1_000_000
D=E.Data(now)
T0=D.h1[-1]['t']+3600-365*86400; T1=D.h1[-1]['t']+3600
print("Backtest window",E.ist(T0),"->",E.ist(T1),"IST")
idx=[j for j,b in enumerate(D.h1) if T0<=b['t']+3600<=T1]
c=Counter(D.regime[j] for j in idx); n=len(idx)
print("Regime % of 1H candles:",{k:f"{v} ({100*v/n:.1f}%)" for k,v in c.items()})
hv=[j for j in idx if D.regime[j]=='HIGHVOL_NEWS']
print("  HV/News reasons: news±2h",sum(E.near_event(D.h1[j]['t']+3600,7200) for j in hv),"ATR>=p90",sum(D.atr_pct[j]>=0.9 for j in hv),"vol>3x",sum(D.h1[j]['v']>3*D.vavg[j] for j in hv))
res={}
for name,(fn,grid) in E.STRATS.items():
    p=grid[E.DEFAULT[name]]
    tr=E.simulate(D,fn,p,T0,T1)
    m=E.metrics(tr,T0,T1); res[name]=dict(params=p,all=m,byreg={})
    print(f"\n{name} {p}\n  ALL : {E.fmt(m)}")
    for rg in ['TREND_UP','TREND_DOWN','SIDEWAYS','HIGHVOL_NEWS']:
        sub=[t for t in tr if t['regime']==rg]; mm=E.metrics(sub,T0,T1); res[name]['byreg'][rg]=mm
        print(f"  {rg:12s}: {E.fmt(mm)}")
    for sd in ['LONG','SHORT']:
        print(f"  {sd:12s}: {E.fmt(E.metrics([t for t in tr if t['side']==sd],T0,T1))}")
    print("  results:",Counter(t['result'] for t in tr).most_common(6), "open:",sum(t['open'] for t in tr))
    import csv
    with open(f"trades_{name}.csv","w",newline="") as f:
        w=csv.writer(f); w.writerow(['open_IST','close_IST','side','entry','stop','TP1','TP2','qty_BTC','risk','result','gross','cost','net','R_net','regime'])
        for t in tr: w.writerow([E.ist(t['t']),E.ist(t['tclose']),t['side'],round(t['entry'],1),round(t['stop'],1),round(t['tp1'],1),round(t['tp2'],1),round(t['qty'],4),round(t['risk'],2),t['result'],round(t['gross'],2),round(t['cost'],2),round(t['net'],2),round(t['Rn'],2),t['regime']])
json.dump(dict(window=[T0,T1],regime={k:v for k,v in c.items()},res=res),open('phase3.json','w'),indent=1,default=str)

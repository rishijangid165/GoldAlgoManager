import json, urllib.request, time
import backtest as B
now=int(json.load(urllib.request.urlopen("https://api.india.delta.exchange/v2/tickers/BTCUSD"))['result']['timestamp'])//1_000_000
h1=[b for b in B.load('btc_1h.csv') if b['time']+3600<=now]
h4=[b for b in B.load('btc_4h.csv') if b['time']+14400<=now]
B.NOW=now
P=B.prepare(h1,h4)
tr=B.run(h1,h4,P)
B.write_trades(tr,'trades.csv')
def show(name,t):
    for k in ('net','gross'):
        s=B.stats(t,k)
        if s['n']==0: print(f"{name:28s} {k}: n=0"); continue
        print(f"{name:28s} {k:5s} n={s['n']:3d} win%={s['winrate']:5.1f} avgW={s['avgwin']:6.2f} avgL={s['avgloss']:7.2f} exp={s['exp']:6.2f} expR={s['expR']:5.2f} tot={s['total']:7.2f} DD={s['maxdd']:6.2f}({s['maxdd_pct']:.1f}%) streak={s['streak']}")
print("data",B.ist(h1[0]['time']),"->",B.ist(h1[-1]['time']+3600),"1h bars",len(h1),"4h",len(h4),"now",B.ist(now))
show("ALL",tr)
show("IS (20Aug-19Oct)",[t for t in tr if t['t']<B.SPLIT]); show("OOS (20Oct-now)",[t for t in tr if t['t']>=B.SPLIT])
show("trending",[t for t in tr if B.cond(t)=='trending']); show("sideways",[t for t in tr if B.cond(t)=='sideways'])
show("weekday",[t for t in tr if not t['ctx']['weekend']]); show("weekend",[t for t in tr if t['ctx']['weekend']])
show("news+-2h",[t for t in tr if t['ctx']['news']]); show("no news",[t for t in tr if not t['ctx']['news']])
show("long",[t for t in tr if t['side']=='LONG']); show("short",[t for t in tr if t['side']=='SHORT'])
from collections import Counter
print(Counter(t['result'] for t in tr))
for i,t in enumerate(tr,1):
    c=t['ctx']; print(i,B.ist(t['t']),t['side'],round(t['entry']),t['result'],round(t['net'],2),'adx',round(c['adx'] or 0),'wk' if c['weekend'] else '', c['news'],'Ratr',round(c['R_atr'],2),'Rpct',round(c['R_pct'],2),'cp',round(c['close_pos'],2),'body',round(c['body_frac'],2),'vx',round(c['volx'],2),'dEMA',round(c['dist_ema_atr'],1))

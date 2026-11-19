import json,urllib.request,random,time,statistics as st
from collections import defaultdict
import engine as E, risk as RK
now=int(json.load(urllib.request.urlopen("https://api.india.delta.exchange/v2/tickers/BTCUSD"))['result']['timestamp'])//1_000_000
D=E.Data(now); T1=D.h1[-1]['t']+3600; T0=T1-365*86400
def mdd(pl,start=1000):
    eq=start;pk=start;dd=0
    for x in pl: eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    return dd
out={}
random.seed(42)
for name,(fn,grid) in E.STRATS.items():
    p=grid[E.DEFAULT[name]]; o={}
    E.set_cost_mult(1); tr=E.simulate(D,fn,p,T0,T1); pl=[t['net'] for t in tr]
    sims=sorted(mdd(random.sample(pl,len(pl))) for _ in range(1000))
    o['mc']=dict(actual=mdd(pl),median=st.median(sims),p95=sims[949],p99=sims[989],worst=sims[-1])
    wk=defaultdict(float); mo=defaultdict(float)
    for t in tr:
        g=time.gmtime(t['tclose']+19800); wk[time.strftime('%G-W%V',g)]+=t['net']; mo[time.strftime('%Y-%m',g)]+=t['net']
    o['worst_week']=min(wk.items(),key=lambda x:x[1]); o['best_week']=max(wk.items(),key=lambda x:x[1])
    o['worst_month']=min(mo.items(),key=lambda x:x[1]); o['months']=dict(sorted(mo.items()))
    o['pos_months']=sum(v>0 for v in mo.values())
    for lab,mult in [('zero_cost',0),('base_cost',1),('double_cost',2)]:
        E.set_cost_mult(mult)
        if mult==0: E.COST['swap']=0
        o[lab]=E.metrics(E.simulate(D,fn,p,T0,T1),T0,T1)
    E.set_cost_mult(1)
    # KIWAMI-like account: $15 spread, no swap
    E.COST.update(spread=15.0,slip=15.0,swap=0.0); o['kiwami_like']=E.metrics(E.simulate(D,fn,p,T0,T1),T0,T1); E.set_cost_mult(1)
    # Phase 6: risk engine (1% and 0.5%)
    for rp in (1.0,0.5):
        R=RK.RiskEngine(1000,rp,0.5); trr=E.simulate(D,fn,p,T0,T1,risk=R)
        o[f'risk_engine_{rp}']=dict(m=E.metrics(trr,T0,T1),final_equity=R.eq,skips=dict(R.skips),hv_half=sum(1 for t in trr if t['mult']<1))
    out[name]=o
    print(f"\n=== {name} {p} (already REJECTED in Phase 4; stress shown for transparency) ===")
    print(" Monte Carlo maxDD USDT: actual %.1f | median %.1f | p95 %.1f | p99 %.1f | worst %.1f"%tuple(o['mc'][k] for k in ['actual','median','p95','p99','worst']))
    print(" worst week",o['worst_week'],"best week",o['best_week'],"worst month",o['worst_month'],"positive months",o['pos_months'],"/",len(mo))
    for lab in ['zero_cost','base_cost','double_cost','kiwami_like']: print(f" {lab:11s}:",E.fmt(o[lab]))
    for rp in (1.0,0.5):
        r=o[f'risk_engine_{rp}']; print(f" RISK ENGINE {rp}%:",E.fmt(r['m']),"| final equity %.2f"%r['final_equity'],"| skipped:",r['skips'],"| HV half-size trades:",r['hv_half'])
json.dump(out,open('phase5_6.json','w'),indent=1,default=str)

import json,urllib.request
import engine as E
now=int(json.load(urllib.request.urlopen("https://api.india.delta.exchange/v2/tickers/BTCUSD"))['result']['timestamp'])//1_000_000
D=E.Data(now); T1=D.h1[-1]['t']+3600; T0=T1-365*86400; DAY=86400
W={'A':(T0,T0+182*DAY),'B':(T0+91*DAY,T0+273*DAY),'C':(T1-183*DAY,T1)}
REGS=['TREND_UP','TREND_DOWN','SIDEWAYS','HIGHVOL_NEWS']
out={}; combos=0
for name,(fn,grid) in E.STRATS.items():
    out[name]={}
    for wn,(a,b) in W.items():
        split=a+int(0.7*(b-a))
        cands=[]
        for pi,p in enumerate(grid):
            tr=E.simulate(D,fn,p,a,split); combos+=1
            m=E.metrics(tr,a,split)
            if m['n']>=15: cands.append((m['expR'],pi,None,m))
            pos=[rg for rg in REGS if (lambda s: s['n']>=10 and s['expR']>0)(E.metrics([t for t in tr if t['regime']==rg],a,split))]
            if pos and len(pos)<4:
                tr2=E.simulate(D,fn,p,a,split,regimes=set(pos)); combos+=1
                m2=E.metrics(tr2,a,split)
                if m2['n']>=15: cands.append((m2['expR'],pi,pos,m2))
        if not cands: out[name][wn]=dict(note="no candidate with >=15 train trades"); print(name,wn,"no candidate"); continue
        best=max(cands,key=lambda x:x[0]); _,pi,regs,mtr=best
        te=E.simulate(D,fn,grid[pi],split,b,regimes=set(regs) if regs else None); mte=E.metrics(te,split,b)
        ok = mte['n']>0 and mte['expR']>0 and mte['pf']>=1
        out[name][wn]=dict(train=[E.ist(a),E.ist(split)],test=[E.ist(split),E.ist(b)],params=grid[pi],regimes=regs or 'ALL',train_m=mtr,test_m=mte,pass_=ok)
        print(f"{name} window {wn}: train {E.ist(a)[:10]}..{E.ist(split)[:10]} test ..{E.ist(b)[:10]} | chosen {grid[pi]} regimes={regs or 'ALL'}")
        print("   TRAIN:",E.fmt(mtr)); print("   TEST :",E.fmt(mte),"=> PASS" if ok else "=> FAIL")
    out[name]['survives']=all(v.get('pass_',False) for k,v in out[name].items() if k in W)
    print(name,"SURVIVES" if out[name]['survives'] else "REJECTED","\n")
print("parameter/regime combos evaluated on training data:",combos)
out['combos']=combos
json.dump(out,open('phase4.json','w'),indent=1,default=str)

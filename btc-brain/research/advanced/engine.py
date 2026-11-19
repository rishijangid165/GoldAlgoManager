"""Advanced training engine: data, indicators, regimes, 3 strategies, 15m-path trade simulation, metrics.
Signals on completed 1H candles; trend from last completed 4H candle; trade path resolved on 15m candles (stop-first)."""
import csv, math, time, calendar, statistics as st, bisect
from collections import defaultdict
ist=lambda t: time.strftime('%Y-%m-%d %H:%M',time.gmtime(t+19800))
def U(y,m,d,h,mi=0): return calendar.timegm((y,m,d,h,mi,0))
ACCOUNT=1000.0
# ---- costs (XM Standard BTCUSD; see report for sources) ----
COST=dict(spread=50.0, slip=15.0, swap=35.0)   # $ per 1 BTC: spread per round trip, slippage per fill, swap per night held
def set_cost_mult(m): COST.update(spread=50.0*m, slip=15.0*m, swap=35.0)
# ---- US events (UTC). 2026 NFP/CPI: BLS schedule page; FOMC: federalreserve.gov. Late-2025 dates from memory (shutdown-delayed) -> marked unsure.
EVENTS=[
 ("NFP(Sep25, unsure)",U(2025,11,20,13,30)),("FOMC",U(2025,12,10,19)),("NFP(Oct+Nov25, unsure)",U(2025,12,16,13,30)),("CPI(Nov25, unsure)",U(2025,12,18,13,30)),
 ("NFP",U(2026,1,9,13,30)),("CPI",U(2026,1,13,13,30)),("FOMC",U(2026,1,28,19)),("NFP",U(2026,2,11,13,30)),("CPI",U(2026,2,13,13,30)),
 ("NFP",U(2026,3,6,13,30)),("CPI",U(2026,3,11,12,30)),("FOMC",U(2026,3,18,18)),("NFP",U(2026,4,3,12,30)),("CPI",U(2026,4,10,12,30)),
 ("FOMC",U(2026,4,29,18)),("NFP",U(2026,5,8,12,30)),("CPI",U(2026,5,12,12,30)),("NFP",U(2026,6,5,12,30)),("CPI",U(2026,6,10,12,30)),
 ("FOMC",U(2026,6,17,18)),("NFP",U(2026,7,2,12,30)),("CPI",U(2026,7,14,12,30)),("FOMC",U(2026,7,29,18)),("NFP",U(2026,8,7,12,30)),
 ("CPI",U(2026,8,12,12,30)),("NFP",U(2026,9,4,12,30)),("CPI",U(2026,9,11,12,30)),("FOMC",U(2026,9,16,18)),("NFP",U(2026,10,2,12,30)),
 ("CPI",U(2026,10,14,12,30)),("FOMC",U(2026,10,28,18)),("NFP",U(2026,11,6,13,30)),("CPI",U(2026,11,10,13,30))]
ET=sorted(e for _,e in EVENTS)
def near_event(t,win):
    i=bisect.bisect_left(ET,t-win); return i<len(ET) and ET[i]<=t+win

def load(fn):
    with open(fn) as f: return [dict(t=int(r['time']),o=float(r['open']),h=float(r['high']),l=float(r['low']),c=float(r['close']),v=float(r['volume'])) for r in csv.DictReader(f)]
def ema(xs,n):
    k=2/(n+1); out=[None]*len(xs); e=None
    for i,x in enumerate(xs):
        e=x if e is None else x*k+e*(1-k)
        if i>=n-1: out[i]=e
    return out
def atr(b,n=14):
    out=[None]*len(b); a=None
    for i in range(len(b)):
        tr=b[i]['h']-b[i]['l'] if i==0 else max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c']))
        if i<n: a=(a or 0)+tr/n if i<n else a
        else: a=(a*(n-1)+tr)/n
        if i>=n-1: out[i]=a
    return out
def adx(b,n=14):
    out=[None]*len(b); trs=[];pdm=[];ndm=[]
    for i in range(1,len(b)):
        up=b[i]['h']-b[i-1]['h']; dn=b[i-1]['l']-b[i]['l']
        pdm.append(up if up>dn and up>0 else 0); ndm.append(dn if dn>up and dn>0 else 0)
        trs.append(max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c'])))
    tr_s=sum(trs[:n]);p_s=sum(pdm[:n]);n_s=sum(ndm[:n]); dxs=[]; a=None
    for k in range(n,len(trs)+1):
        if k>n: tr_s=tr_s-tr_s/n+trs[k-1]; p_s=p_s-p_s/n+pdm[k-1]; n_s=n_s-n_s/n+ndm[k-1]
        pdi=100*p_s/tr_s; ndi=100*n_s/tr_s; dx=100*abs(pdi-ndi)/(pdi+ndi) if pdi+ndi else 0
        dxs.append(dx)
        if len(dxs)==n: a=sum(dxs)/n
        elif len(dxs)>n: a=(a*(n-1)+dx)/n
        out[k]=a
    return out

class Data:
    def __init__(self,now):
        self.h1=load('delta_1h.csv'); self.h4=load('delta_4h.csv'); self.m15=load('delta_15m.csv')
        h1,h4=self.h1,self.h4
        self.a1=atr(h1); self.e20=ema([x['c'] for x in h1],20); self.e50_1=ema([x['c'] for x in h1],50)
        self.vavg=[None]*len(h1)
        for i in range(20,len(h1)): self.vavg[i]=sum(x['v'] for x in h1[i-20:i])/20
        self.e4=ema([x['c'] for x in h4],50); self.ad4=adx(h4)
        self.m=[]; j=-1
        for b in h1:
            while j+1<len(h4) and h4[j+1]['t']+14400<=b['t']+3600: j+=1
            self.m.append(j)
        self.t15={b['t']:i for i,b in enumerate(self.m15)}
        self.hh={}; self.ll={}
        # ATR percentile over previous 720 bars (30 days)
        self.atr_pct=[None]*len(h1)
        win=[]
        for i in range(len(h1)):
            if self.a1[i] is not None and i>=720+14:
                prev=sorted(self.a1[i-720:i]); self.atr_pct[i]=bisect.bisect_left(prev,self.a1[i])/720
        self.piv={}
        self.regime=[self._regime(j) for j in range(len(h1))]
    def trend(self,j):
        j4=self.m[j]
        if j4<3 or self.e4[j4] is None or self.e4[j4-3] is None: return None
        c=self.h4[j4]['c']; e=self.e4[j4]; s=e-self.e4[j4-3]
        if c>e and s>0: return 'UP'
        if c<e and s<0: return 'DOWN'
        return None
    def _regime(self,j):
        dec=self.h1[j]['t']+3600
        if self.atr_pct[j] is None or self.vavg[j] is None: return None
        if near_event(dec,7200) or self.atr_pct[j]>=0.90 or self.h1[j]['v']>3*self.vavg[j]: return 'HIGHVOL_NEWS'
        tr=self.trend(j); ad=self.ad4[self.m[j]] or 0
        if tr=='UP' and ad>=20: return 'TREND_UP'
        if tr=='DOWN' and ad>=20: return 'TREND_DOWN'
        return 'SIDEWAYS'
    def pivots(self,k):
        if k not in self.piv:
            h1=self.h1; lo=[False]*len(h1); hi=[False]*len(h1)
            for i in range(k,len(h1)-k):
                w=h1[i-k:i+k+1]
                if all(h1[i]['l']<x['l'] for q,x in enumerate(w) if q!=k): lo[i]=True
                if all(h1[i]['h']>x['h'] for q,x in enumerate(w) if q!=k): hi[i]=True
            self.piv[k]=(lo,hi)
        return self.piv[k]

# ---------------- strategies: return (side, stop) or None, evaluated at close of 1H bar j ----------------
def s1_pullback(D,j,p):
    """Trend pullback: 4H trend; 1H candle dips to EMA(p['ema']) and closes back on trend side with trend-colour body.
    Stop = candle extreme -/+ p['buf']*ATR."""
    tr=D.trend(j); b=D.h1[j]; a=D.a1[j]; e=D.e20[j] if p['ema']==20 else D.e50_1[j]
    if not tr or a is None or e is None: return None
    if tr=='UP' and b['l']<=e<b['c'] and b['c']>b['o']: return ('LONG', b['l']-p['buf']*a)
    if tr=='DOWN' and b['h']>=e>b['c'] and b['c']<b['o']: return ('SHORT', b['h']+p['buf']*a)
    return None
def s2_sr(D,j,p):
    """v1 S/R reversal: pivot k, 120h lookback, touch 0.25 ATR, close back across, vol > p['vol']*avg20, stop 0.3 ATR beyond."""
    tr=D.trend(j); b=D.h1[j]; a=D.a1[j]; va=D.vavg[j]; k=p['k']
    if not tr or a is None or va is None or b['v']<=p['vol']*va: return None
    lo,hi=D.pivots(k); h1=D.h1; best=None
    for i in range(max(0,j-120),j-k+1):
        if tr=='UP' and lo[i] and b['c']>b['o']:
            S=h1[i]['l']
            if b['l']<=S+0.25*a and b['c']>S and not any(h1[q]['c']<S for q in range(i+1,j)) and (best is None or S>best): best=S
        if tr=='DOWN' and hi[i] and b['c']<b['o']:
            R=h1[i]['h']
            if b['h']>=R-0.25*a and b['c']<R and not any(h1[q]['c']>R for q in range(i+1,j)) and (best is None or R<best): best=R
    if best is None: return None
    return ('LONG',min(b['l'],best)-0.3*a) if tr=='UP' else ('SHORT',max(b['h'],best)+0.3*a)
def s3_breakout(D,j,p):
    """Breakout: 4H trend; 1H close beyond highest high/lowest low of previous N candles; vol > p['vol']*avg20; stop 1.5 ATR."""
    tr=D.trend(j); b=D.h1[j]; a=D.a1[j]; va=D.vavg[j]; N=p['N']
    if not tr or a is None or va is None or j<N or b['v']<=p['vol']*va: return None
    prev=D.h1[j-N:j]
    if tr=='UP' and b['c']>max(x['h'] for x in prev): return ('LONG',b['c']-1.5*a)
    if tr=='DOWN' and b['c']<min(x['l'] for x in prev): return ('SHORT',b['c']+1.5*a)
    return None
STRATS={'S1_pullback':(s1_pullback,[dict(ema=20,buf=0.5),dict(ema=20,buf=1.0),dict(ema=50,buf=0.5),dict(ema=50,buf=1.0)]),
        'S2_SR_reversal':(s2_sr,[dict(k=3,vol=1.2),dict(k=3,vol=1.5),dict(k=5,vol=1.2),dict(k=5,vol=1.5)]),
        'S3_breakout':(s3_breakout,[dict(N=24,vol=1.5),dict(N=24,vol=2.0),dict(N=48,vol=1.5),dict(N=48,vol=2.0)])}
DEFAULT={'S1_pullback':0,'S2_SR_reversal':0,'S3_breakout':0}

def nights(t0,t1):
    """number of 22:00 UTC rollovers between t0 and t1"""
    first=(t0-79200)//86400+1; last=(t1-79200)//86400
    return max(0,last-first+1)

def simulate(D,sig,p,t_from,t_to,regimes=None,risk=None):
    """risk=None -> fixed 10 USDT risk, fractional qty (research mode). risk=RiskEngine -> XM lots + limits."""
    trades=[]; h1=D.h1; m15=D.m15; jstart=bisect.bisect_left([b['t'] for b in h1],t_from-3600)
    j=jstart; dayPL=defaultdict(float)
    while j<len(h1):
        b=h1[j]; dec=b['t']+3600
        if dec>t_to: break
        reg=D.regime[j]
        if reg is None or near_event(dec,1800) or (regimes and reg not in regimes): j+=1; continue
        dkey=time.strftime('%Y-%m-%d',time.gmtime(dec+19800))
        if risk is None and dayPL[dkey]<=-30: j+=1; continue
        s=sig(D,j,p)
        if not s: j+=1; continue
        side,stop=s; entry=b['c']; R=abs(entry-stop)
        if R<=0: j+=1; continue
        if risk is None: qty=10.0/R; mult=1.0
        else:
            qty,mult=risk.size(entry,R,reg,dec)
            if qty<=0: j+=1; continue
        sg=1 if side=='LONG' else -1
        tp1=entry+sg*2*R; tp2=entry+sg*3*R; cur=stop; t1=False; exits=[]
        i=D.t15.get(dec)
        if i is None: break
        while i<len(m15):
            c=m15[i]; L=side=='LONG'
            # gap through stop -> fill at open
            if (L and c['o']<=cur) or (not L and c['o']>=cur):
                exits.append((c['o'],qty if not t1 else qty/2,c['t'],'SL' if not t1 else 'BE')); break
            hitS=(c['l']<=cur) if L else (c['h']>=cur)
            if hitS: exits.append((cur,qty if not t1 else qty/2,c['t']+900,'SL' if not t1 else 'BE')); break
            if not t1 and ((c['h']>=tp1) if L else (c['l']<=tp1)):
                exits.append((tp1,qty/2,c['t']+900,'TP1')); t1=True; cur=entry
                if (c['l']<=entry) if L else (c['h']>=entry):   # conservative: same 15m candle back to entry -> BE
                    exits.append((entry,qty/2,c['t']+900,'BE')); break
                i+=1; continue
            if t1 and ((c['h']>=tp2) if L else (c['l']<=tp2)):
                exits.append((tp2,qty/2,c['t']+900,'TP2')); break
            i+=1
        openend = i>=len(m15)
        if openend:
            last=m15[-1]; exits.append((last['c'],qty/2 if t1 else qty,last['t']+900,'OPEN'))
        tclose=exits[-1][2]
        gross=sum(sg*(px-entry)*q for px,q,_,_ in exits)
        nfills=1+len(exits)
        cost=qty*COST['spread']+COST['slip']*(qty+sum(q for _,q,_,_ in exits))+COST['swap']*qty*nights(dec,tclose)
        net=gross-cost; riskusd=qty*R
        tr=dict(side=side,t=dec,tclose=tclose,entry=entry,stop=stop,tp1=tp1,tp2=tp2,qty=qty,R=R,risk=riskusd,exits=exits,
                gross=gross,cost=cost,net=net,Rn=net/riskusd,Rg=gross/riskusd,regime=reg,open=openend,mult=mult,
                result='OPEN' if openend else '+'.join(e[3] for e in exits))
        trades.append(tr)
        ck=time.strftime('%Y-%m-%d',time.gmtime(tclose+19800)); dayPL[ck]+=net
        if risk is not None: risk.record(tr)
        # one trade at a time: resume scanning at the first 1H candle whose close is after the trade closed
        j=bisect.bisect_left([x['t'] for x in h1],tclose-3600+1) if False else _next_j(D,tclose)
    return trades
_h1t=None
def _next_j(D,tclose):
    global _h1t
    if _h1t is None: _h1t=[x['t'] for x in D.h1]
    # next decision bar: candle that OPENS at/after tclose (we decide at its close)
    return bisect.bisect_left(_h1t,tclose)

def metrics(tr,t_from,t_to,start_eq=ACCOUNT):
    n=len(tr)
    if n==0: return dict(n=0)
    pl=[t['net'] for t in tr]; w=[x for x in pl if x>0]; l=[x for x in pl if x<=0]
    eq=start_eq; pk=eq; dd=0; ddp=0
    for x in pl:
        eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq); ddp=max(ddp,(pk-eq)/pk*100)
    streak=cur=0
    for x in pl: cur=cur+1 if x<=0 else 0; streak=max(streak,cur)
    # Sharpe: daily P&L (by close day, UTC calendar) / start equity; zero days included; annualised sqrt(365)
    days=defaultdict(float)
    for t in tr: days[t['tclose']//86400]+=t['net']
    d0=t_from//86400; d1=t_to//86400
    r=[days.get(d,0.0)/start_eq for d in range(d0,d1+1)]
    sh=(st.mean(r)/st.pstdev(r)*math.sqrt(365)) if len(r)>1 and st.pstdev(r)>0 else 0
    gw=sum(w); gl=-sum(l)
    return dict(n=n,winrate=100*len(w)/n,avgwin=gw/len(w) if w else 0,avgloss=-gl/len(l) if l else 0,exp=sum(pl)/n,
                expR=sum(t['Rn'] for t in tr)/n,pf=(gw/gl if gl>0 else float('inf')),total=sum(pl),maxdd=dd,maxdd_pct=dd/start_eq*100,
                maxdd_peak_pct=ddp,streak=streak,sharpe=sh,gross_total=sum(t['gross'] for t in tr),cost_total=sum(t['cost'] for t in tr))
def fmt(m):
    if m['n']==0: return "n=0 (data nahi / no trades)"
    return (f"n={m['n']} win={m['winrate']:.1f}% avgW={m['avgwin']:.2f} avgL={m['avgloss']:.2f} exp={m['exp']:.2f}USDT ({m['expR']:+.2f}R) "
            f"PF={m['pf']:.2f} total={m['total']:.2f} (gross {m['gross_total']:.2f}, costs {m['cost_total']:.2f}) maxDD={m['maxdd']:.1f} ({m['maxdd_pct']:.1f}%) streak={m['streak']} Sharpe={m['sharpe']:.2f}")

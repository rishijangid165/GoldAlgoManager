"""BTC training-mode backtest. Delta India BTCUSD perp, 1H + 4H. No lookahead."""
import csv, math, time, json, calendar, sys
from collections import defaultdict

RISK=10.0; ACCOUNT=1000.0; COST=0.0005  # 0.05% per side
EMA_N=50; SLOPE_N=3; PIV=3; LVL_LOOKBACK=120; TOUCH=0.25; VOLX=1.2; VOL_N=20; BUF=0.3; ATR_N=14
TP1R=2.0; TP2R=3.0; DAILY_MAX=-30.0; ADX_TREND=20
TEST_START=calendar.timegm((2026,8,20,0,0,0)); SPLIT=calendar.timegm((2026,10,20,0,0,0))
NOW=None
def U(y,m,d,h,mi): return calendar.timegm((y,m,d,h,mi,0))
EVENTS=[("NFP",U(2026,9,4,12,30)),("CPI",U(2026,9,11,12,30)),("FOMC",U(2026,9,16,18,0)),
        ("NFP",U(2026,10,2,12,30)),("CPI",U(2026,10,14,12,30)),("FOMC",U(2026,10,28,18,0)),
        ("NFP",U(2026,11,6,13,30)),("CPI",U(2026,11,10,13,30))]
ist=lambda t: time.strftime('%Y-%m-%d %H:%M',time.gmtime(t+19800))

def load(fn):
    with open(fn) as f:
        return [dict(time=int(r['time']),o=float(r['open']),h=float(r['high']),l=float(r['low']),c=float(r['close']),v=float(r['volume'])) for r in csv.DictReader(f)]

def ema(xs,n):
    k=2/(n+1); out=[]; e=None
    for i,x in enumerate(xs):
        e = x if e is None else x*k+e*(1-k); out.append(e if i>=n-1 else None)
    return out

def atr(b,n):
    tr=[b[0]['h']-b[0]['l']]+[max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c'])) for i in range(1,len(b))]
    out=[None]*len(b); a=None
    for i in range(len(b)):
        if i==n-1: a=sum(tr[:n])/n
        elif i>=n: a=(a*(n-1)+tr[i])/n
        out[i]=a
    return out

def adx(b,n=14):
    out=[None]*len(b); trs=[];pdm=[];ndm=[]
    for i in range(1,len(b)):
        up=b[i]['h']-b[i-1]['h']; dn=b[i-1]['l']-b[i]['l']
        pdm.append(up if up>dn and up>0 else 0); ndm.append(dn if dn>up and dn>0 else 0)
        trs.append(max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c'])))
    if len(trs)<2*n: return out
    tr_s=sum(trs[:n]);p_s=sum(pdm[:n]);n_s=sum(ndm[:n]); dxs=[]; a=None
    for k in range(n,len(trs)+1):
        if k>n:
            tr_s=tr_s-tr_s/n+trs[k-1]; p_s=p_s-p_s/n+pdm[k-1]; n_s=n_s-n_s/n+ndm[k-1]
        pdi=100*p_s/tr_s; ndi=100*n_s/tr_s; dx=100*abs(pdi-ndi)/(pdi+ndi) if pdi+ndi else 0
        dxs.append(dx)
        if len(dxs)==n: a=sum(dxs)/n
        elif len(dxs)>n: a=(a*(n-1)+dx)/n
        out[k]=a  # index k in bars (trs index k-1 -> bar k)
    return out

def prepare(h1,h4):
    a1=atr(h1,ATR_N)
    vavg=[None]*len(h1)
    for i in range(VOL_N,len(h1)): vavg[i]=sum(x['v'] for x in h1[i-VOL_N:i])/VOL_N  # 20 PREVIOUS candles
    e4=ema([x['c'] for x in h4],EMA_N); ad4=adx(h4)
    # map each 1H decision (close time) to last completed 4H index
    m=[]; j=-1
    for b in h1:
        dec=b['time']+3600
        while j+1<len(h4) and h4[j+1]['time']+14400<=dec: j+=1
        m.append(j)
    # pivots
    plo=[False]*len(h1); phi=[False]*len(h1)
    for i in range(PIV,len(h1)-PIV):
        w=h1[i-PIV:i+PIV+1]
        if h1[i]['l']==min(x['l'] for x in w) and all(h1[i]['l']<x['l'] for k,x in enumerate(w) if k!=PIV): plo[i]=True
        if h1[i]['h']==max(x['h'] for x in w) and all(h1[i]['h']>x['h'] for k,x in enumerate(w) if k!=PIV): phi[i]=True
    return dict(a1=a1,vavg=vavg,e4=e4,ad4=ad4,m=m,plo=plo,phi=phi)

def trend_at(P,h4,j):
    if j<SLOPE_N or P['e4'][j] is None or P['e4'][j-SLOPE_N] is None: return None
    c=h4[j]['c']; e=P['e4'][j]; s=e-P['e4'][j-SLOPE_N]
    if c>e and s>0: return 'UP'
    if c<e and s<0: return 'DOWN'
    return None

def find_level(h1,P,j,side):
    """nearest still-valid confirmed pivot level touched by candle j"""
    a=P['a1'][j]; b=h1[j]; best=None
    for i in range(max(0,j-LVL_LOOKBACK),j-PIV+1):
        if side=='LONG' and P['plo'][i]:
            S=h1[i]['l']
            if any(h1[k]['c']<S for k in range(i+1,j)): continue
            if b['l']<=S+TOUCH*a and b['c']>S and (best is None or S>best): best=S
        if side=='SHORT' and P['phi'][i]:
            R=h1[i]['h']
            if any(h1[k]['c']>R for k in range(i+1,j)): continue
            if b['h']>=R-TOUCH*a and b['c']<R and (best is None or R<best): best=R
    return best

def near_event(t,win):
    return [n for n,e in EVENTS if abs(t-e)<=win]

def run(h1,h4,P,extra=None,label="base"):
    trades=[]; pos=None; dayPL=defaultdict(float)
    for j in range(len(h1)):
        b=h1[j]; dec=b['time']+3600
        # manage open position on this candle (entered at close of earlier candle)
        if pos:
            L=pos['side']=='LONG'; sgn=1 if L else -1
            hitSL = (b['l']<=pos['stop']) if L else (b['h']>=pos['stop'])
            hitT1 = (b['h']>=pos['tp1']) if L else (b['l']<=pos['tp1'])
            hitT2 = (b['h']>=pos['tp2']) if L else (b['l']<=pos['tp2'])
            if not pos['t1done']:
                if hitSL:
                    pos['exits'].append((pos['stop'],pos['qty'],dec,'SL')); close=True
                elif hitT1:
                    pos['exits'].append((pos['tp1'],pos['qty']/2,dec,'TP1')); pos['t1done']=True; pos['stop']=pos['entry']
                    # conservative: same candle back to entry -> BE; TP2 not credited in TP1 candle
                    back=(b['l']<=pos['entry']) if L else (b['h']>=pos['entry'])
                    close=False
                    if back: pos['exits'].append((pos['entry'],pos['qty']/2,dec,'BE')); close=True
                else: close=False
            else:
                if hitSL: pos['exits'].append((pos['stop'],pos['qty']/2,dec,'BE')); close=True
                elif hitT2: pos['exits'].append((pos['tp2'],pos['qty']/2,dec,'TP2')); close=True
                else: close=False
            if close: finish(pos,trades,dayPL); pos=None
        if pos or j<LVL_LOOKBACK or b['time']<TEST_START-3600: continue
        if NOW and dec>NOW: continue
        dkey=time.strftime('%Y-%m-%d',time.gmtime(dec+19800))
        if dayPL[dkey]<=DAILY_MAX: continue
        if near_event(dec,1800): continue   # Rishi rule: no new setup 30m around big news
        j4=P['m'][j]; tr=trend_at(P,h4,j4)
        if not tr: continue
        side='LONG' if tr=='UP' else 'SHORT'
        a=P['a1'][j]; va=P['vavg'][j]
        if a is None or va is None or b['v']<=VOLX*va: continue
        if side=='LONG' and not b['c']>b['o']: continue
        if side=='SHORT' and not b['c']<b['o']: continue
        lvl=find_level(h1,P,j,side)
        if lvl is None: continue
        entry=b['c']
        stop = min(b['l'],lvl)-BUF*a if side=='LONG' else max(b['h'],lvl)+BUF*a
        R=abs(entry-stop)
        qty=math.floor(RISK/R*1000)/1000   # Delta step 0.001 BTC
        if qty<0.001: continue
        sg=1 if side=='LONG' else -1
        ctx=dict(adx=P['ad4'][j4], weekend=time.gmtime(dec).tm_wday>=5, news=near_event(dec,7200),
                 range_pct=None, body_frac=abs(b['c']-b['o'])/(b['h']-b['l']) if b['h']>b['l'] else 0,
                 close_pos=(b['c']-b['l'])/(b['h']-b['l']) if b['h']>b['l'] else 0.5,
                 R_atr=R/a, volx=b['v']/va, dist_ema_atr=(entry-P['e4'][j4])/a*sg, R_pct=R/entry*100)
        if extra and not extra(side,ctx): continue
        pos=dict(side=side,t=dec,entry=entry,stop=stop,stop0=stop,lvl=lvl,tp1=entry+sg*TP1R*R,tp2=entry+sg*TP2R*R,
                 qty=qty,R=R,t1done=False,exits=[],ctx=ctx,dkey=dkey)
    if pos:  # mark-to-market open trade at last close
        last=h1[-1]; pos['exits'].append((last['c'],pos['qty']-sum(e[1] for e in pos['exits']),last['time']+3600,'OPEN'))
        finish(pos,trades,dayPL,open_=True)
    return trades

def finish(p,trades,dayPL,open_=False):
    sg=1 if p['side']=='LONG' else -1
    gross=sum(sg*(px-p['entry'])*q for px,q,_,_ in p['exits'])
    cost=COST*p['entry']*p['qty']+sum(COST*px*q for px,q,_,_ in p['exits'])
    tags=[e[3] for e in p['exits']]
    res='OPEN' if open_ else ('LOSS(SL)' if tags==['SL'] else 'TP1+BE' if 'BE' in tags else 'TP1+TP2' if 'TP2' in tags else '?')
    p.update(gross=gross,net=gross-cost,cost=cost,result=res,risk_usd=p['qty']*p['R'],
             Rg=gross/(p['qty']*p['R']),Rn=(gross-cost)/(p['qty']*p['R']),open=open_)
    dayPL[p['dkey']]+=p['net']   # daily limit uses net realized P&L
    trades.append(p)

def stats(tr,key='net'):
    n=len(tr)
    if n==0: return dict(n=0)
    pl=[t[key] for t in tr]; Rk='Rn' if key=='net' else 'Rg'
    w=[x for x in pl if x>0]; l=[x for x in pl if x<=0]
    eq=ACCOUNT; pk=ACCOUNT; dd=0
    for x in pl:
        eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    streak=cur=0
    for x in pl:
        cur=cur+1 if x<=0 else 0; streak=max(streak,cur)
    return dict(n=n,win=len(w),winrate=100*len(w)/n,avgwin=sum(w)/len(w) if w else 0,avgloss=sum(l)/len(l) if l else 0,
                exp=sum(pl)/n,expR=sum(t[Rk] for t in tr)/n,total=sum(pl),maxdd=dd,maxdd_pct=dd/ACCOUNT*100,streak=streak)

def cond(t): return 'trending' if (t['ctx']['adx'] or 0)>=ADX_TREND else 'sideways'

def write_trades(tr,fn):
    with open(fn,'w',newline='') as f:
        w=csv.writer(f)
        w.writerow(['#','open_time_IST','side','entry','level','stop','TP1','TP2','qty_BTC','XM_lot_equiv','risk_USDT','exits(price@IST:tag)','result',
                    'PnL_gross_USDT','cost_USDT','PnL_net_USDT','R_gross','R_net','condition','ADX4h','weekday_or_weekend','news_within_2h','sample'])
        for i,t in enumerate(tr,1):
            w.writerow([i,ist(t['t']),t['side'],round(t['entry'],1),round(t['lvl'],1),round(t['stop0'],1),round(t['tp1'],1),round(t['tp2'],1),t['qty'],
                        round(t['qty'],2),round(t['risk_usd'],2),' | '.join(f"{px:.1f}@{ist(tt)}:{tg}" for px,q,tt,tg in t['exits']),t['result'],
                        round(t['gross'],2),round(t['cost'],2),round(t['net'],2),round(t['Rg'],2),round(t['Rn'],2),cond(t),
                        round(t['ctx']['adx'],1) if t['ctx']['adx'] else '', 'weekend' if t['ctx']['weekend'] else 'weekday',
                        ','.join(t['ctx']['news']) or 'no','IS' if t['t']<SPLIT else 'OOS'])

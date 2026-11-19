import time, math
from collections import defaultdict
class RiskEngine:
    """XM BTCUSD: 1 lot = 1 BTC, $1 per $1 move per lot, min 0.01 lot, step 0.01.
    Lot = (Equity x Risk%) / (Stop distance x 1) rounded DOWN to 0.01; if < 0.01 -> skip (0.01 lot would exceed the risk budget).
    Risk 1% normally (configurable 0.5-1%), half in HIGHVOL_NEWS. Daily loss limit 3%, weekly 6% (IST Mon-Sun), 3 losses in a row -> pause until next IST day."""
    def __init__(self,equity=1000.0,risk_pct=1.0,hv_mult=0.5):
        self.eq=equity; self.rp=risk_pct; self.hv=hv_mult; self.day=defaultdict(float); self.week=defaultdict(float)
        self.daystart={}; self.weekstart={}; self.streak=0; self.pause_until_day=None; self.skips=defaultdict(int)
    def _keys(self,t):
        g=time.gmtime(t+19800); return time.strftime('%Y-%m-%d',g), time.strftime('%G-W%V',g)
    def size(self,entry,R,regime,t):
        d,w=self._keys(t)
        self.daystart.setdefault(d,self.eq); self.weekstart.setdefault(w,self.eq)
        if self.pause_until_day and d<=self.pause_until_day: self.skips['3-loss pause']+=1; return 0,0
        if self.day[d]<=-0.03*self.daystart[d]: self.skips['daily 3% limit']+=1; return 0,0
        if self.week[w]<=-0.06*self.weekstart[w]: self.skips['weekly 6% limit']+=1; return 0,0
        mult=self.hv if regime=='HIGHVOL_NEWS' else 1.0
        if mult==0: self.skips['HV/news no-trade']+=1; return 0,0
        risk_usd=self.eq*self.rp/100*mult
        lots=math.floor(risk_usd/R*100+1e-9)/100
        if lots<0.01: self.skips['lot<0.01 (stop too wide for budget)']+=1; return 0,0
        return lots,mult
    def record(self,tr):
        d,w=self._keys(tr['tclose'])
        self.daystart.setdefault(d,self.eq); self.weekstart.setdefault(w,self.eq)
        self.eq+=tr['net']; self.day[d]+=tr['net']; self.week[w]+=tr['net']
        self.streak=self.streak+1 if tr['net']<=0 else 0
        if self.streak>=3: self.pause_until_day=d; self.streak=0

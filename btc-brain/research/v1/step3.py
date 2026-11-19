import json, urllib.request
import backtest as B
now=int(json.load(urllib.request.urlopen("https://api.india.delta.exchange/v2/tickers/BTCUSD"))['result']['timestamp'])//1_000_000
h1=[b for b in B.load('btc_1h.csv') if b['time']+3600<=now]; h4=[b for b in B.load('btc_4h.csv') if b['time']+14400<=now]
B.NOW=now; P=B.prepare(h1,h4)
def strong(s,c): return c['close_pos']>=2/3 if s=='LONG' else c['close_pos']<=1/3
CANDS={
 'A_adx20':      lambda s,c: (c['adx'] or 0)>=20,
 'B_not_extended_5atr': lambda s,c: c['dist_ema_atr']<=5,
 'C_close_outer_third': strong,
 'D_body_ge_0.2': lambda s,c: c['body_frac']>=0.2,
 'E_no_weekend': lambda s,c: not c['weekend'],
 'F_no_news_2h': lambda s,c: not c['news'],
}
base=B.run(h1,h4,P)
isb=[t for t in base if t['t']<B.SPLIT]; oob=[t for t in base if t['t']>=B.SPLIT]
def line(t):
    s=B.stats(t,'net'); g=B.stats(t,'gross')
    if s['n']==0: return "n=0"
    return f"n={s['n']} win%={s['winrate']:.1f} avgW={s['avgwin']:.2f} avgL={s['avgloss']:.2f} exp={s['exp']:.2f} ({s['expR']:.2f}R) total={s['total']:.2f} [gross {g['total']:.2f}, {g['expR']:.2f}R] DD={s['maxdd']:.2f} ({s['maxdd_pct']:.1f}%) streak={s['streak']}"
out={}
print("BASE IS :",line(isb)); print("BASE OOS:",line(oob))
for k,f in CANDS.items():
    avoidL=[i for i,t in enumerate(base,1) if t['t']<B.SPLIT and t['net']<=0 and not f(t['side'],t['ctx'])]
    lostW=[i for i,t in enumerate(base,1) if t['t']<B.SPLIT and t['net']>0 and not f(t['side'],t['ctx'])]
    tr=B.run(h1,h4,P,extra=f)
    i_=[t for t in tr if t['t']<B.SPLIT]; o_=[t for t in tr if t['t']>=B.SPLIT]
    print(f"\n{k}: IS losers filtered (base trade #) {avoidL}, IS winners filtered {lostW}")
    print("  IS :",line(i_)); print("  OOS:",line(o_))
    out[k]=dict(avoidL=avoidL,lostW=lostW,IS=B.stats(i_),OOS=B.stats(o_))
json.dump(out,open('step3_candidates.json','w'),indent=1,default=str)

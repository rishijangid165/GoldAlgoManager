
import pandas as pd
B='/home/box/.wine-mt5/drive_c/winpy/broker/'
def rsi(c,n=14):
    d=c.diff(); u=d.clip(lower=0).ewm(alpha=1/n).mean(); v=(-d.clip(upper=0)).ewm(alpha=1/n).mean(); return 100-100/(1+u/v)
for tf in ['D1','H4','H1','M15']:
    df=pd.read_csv(B+f'mtf_{tf}.csv'); df['t']=pd.to_datetime(df.time,unit='s')
    c=df.close; tr=pd.concat([df.high-df.low,(df.high-c.shift()).abs(),(df.low-c.shift()).abs()],axis=1).max(axis=1)
    print(tf,'MA20 %.1f MA50 %.1f MA200 %.1f ATR %.1f RSI %.1f'%(c.rolling(20).mean().iloc[-1],c.rolling(50).mean().iloc[-1],c.rolling(200).mean().iloc[-1],tr.rolling(14).mean().iloc[-1],rsi(c).iloc[-1]))
    n={'D1':2,'H4':3,'H1':6,'M15':8}[tf]
    print(df[['t','open','high','low','close']].tail(n).to_string(index=False))


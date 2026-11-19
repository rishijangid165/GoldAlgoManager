# BTC Training Strategy v1 — "Trend + Level Bounce + Volume"

**Simple Hinglish mein:** Bade chart (4 ghante) par trend dekho. Trend upar hai to sirf BUY, neeche hai to sirf SELL.
Phir 1 ghante ke chart par purana support (BUY ke liye) ya resistance (SELL ke liye) dhoondo. Jab price us level ko
chhoo kar wapas trend ki disha mein band ho, aur us candle mein volume normal se 20% zyada ho, tab trade lo.
Stop level ke thoda paar, Target 1 = risk ka 2 guna (aadha band, stop entry par), Target 2 = risk ka 3 guna.

Data: Delta India `BTCUSD` perpetual, 1H aur 4H candles. Saare indicators sirf **band ho chuki** candles par.

## Exact rules (7 parameters: EMA 50, slope 3, pivot 3, touch 0.25 ATR, volume 1.2x/20, stop buffer 0.3 ATR, ATR 14)

1. **Trend (4H):** last completed 4H candle use karo. EMA50 = 50-period EMA of 4H closes.
   - UP = 4H close > EMA50 **aur** EMA50 abhi > EMA50 3 candles pehle.
   - DOWN = 4H close < EMA50 **aur** EMA50 abhi < EMA50 3 candles pehle.
   - Warna NO TRADE.
2. **Levels (1H pivots):** Pivot low = wo 1H candle jiska low uske 3 pehle aur 3 baad wali candles ke low se kam ho
   (pivot high ulta). Pivot tabhi use hota hai jab uske baad 3 candles band ho chuki hon. Sirf pichhle 120 ghante
   (5 din) ke pivots. Support tab tak valid hai jab tak uske baad koi 1H close uske neeche nahi hua
   (resistance: koi close upar nahi hua).
3. **Entry trigger (1H, decision candle band hone par):**
   - BUY (trend UP): candle ka low <= support + 0.25×ATR14(1H), close > support, aur close > open (hari candle).
     Kai supports match karein to sabse upar wala lo.
   - SELL (trend DOWN): candle ka high >= resistance − 0.25×ATR, close < resistance, close < open (laal candle).
     Sabse neeche wala resistance lo.
4. **Volume:** us candle ka volume > 1.2 × pichhli 20 candles ka average volume.
5. **Entry price:** trigger candle ka close (paper/live mein next candle ki shuruaat par market).
6. **Stop:** BUY: min(candle low, support) − 0.3×ATR. SELL: max(candle high, resistance) + 0.3×ATR. R = |entry − stop|.
7. **Size:** qty BTC = 10 USDT ÷ R, neeche round 0.001 BTC (Delta step). XM lot = qty ko 0.01 tak round (min 0.01;
   agar R > $1,000 hai to 0.01 lot bhi $10 se zyada risk hai → trade SKIP).
8. **Targets:** TP1 = entry ± 2R → aadha band, stop entry par. TP2 = entry ± 3R → baaki band.
   (Costs ke baad TP1 lagbhag 1.8R banta hai; gross 2R.)
9. **Risk rules (Rishi ke):** ek time par sirf 1 trade. Din (IST) ka net loss −30 USDT (3%) ho gaya to us din
   naya trade nahi. Lagatar 3 loss par ruk kar Rishi ko batana (backtest isse simulate nahi kar sakta, sirf report karta hai).
   Badi US news (CPI, NFP, FOMC) ke ±30 minute mein naya trade nahi.
10. **Backtest assumptions:** ek hi 1H candle mein stop aur target dono → stop pehle. TP1 wali candle mein TP2 credit nahi,
    aur agar usi candle mein price entry tak wapas aaya to baaki aadha breakeven par band. Cost = 0.05% har side
    (entry + har exit) notional par.

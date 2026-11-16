# BTCAIBridge – BTC EA (XM MT5 ke liye)

Ye gold wale EA (GoldAIBridge) ka BTC version hai. EA har 5 minute mein GitHub se
`btc/decisions/current.json` padhta hai, aur trade **sirf tab** leta hai jab price AI ke diye entry zone mein ho.
Har trade par hard stop-loss lagta hai, aur risk 0.5% hai. Ye folder gold wale `mql5/` aur `decisions/` se bilkul alag hai.

> **Zaroori:** EA by default sirf **DEMO** account par trade karta hai (`InpAllowLiveAccount=false`).
> Real account par ye khud block ho jayega. Pehle XM **demo** par kam se kam kuch din test karo.
> Uske baad hi, soch samajh kar, `InpAllowLiveAccount=true` karna.

## Files

| File | Kya hai |
|---|---|
| `mql5/Experts/BTCAIBridge.mq5` / `.ex5` | EA (source + compiled) |
| `mql5/Include/BTCAI*.mqh` | EA ki helper files (7 files) |
| `mql5/Scripts/BTCSymbolProbe.mq5` | Sirf padhne wala script. XM ke BTC symbol ki details dikhata hai, koi trade nahi karta |
| `mql5/Presets/BTCAIBridge_demo.set` | EA settings (isme koi token nahi hai) |
| `mql5/docs/decision.schema.json` | Signal file ka format |
| `decisions/current.json` | Live signal file, jise EA padhta hai (abhi NO TRADE) |
| `scripts/write_decision.py` | Signal file banane aur check karne ka script |

## Step by step (aapke Windows PC ka XM MT5)

**1. Files download karo**
GitHub par `btc/` folder kholo aur upar ki files download karo (ya poora repo ZIP mein download karke `btc/` folder nikaal lo).

**2. MT5 ka data folder kholo**
XM MT5 kholo, phir **File > Open Data Folder** par jao. Ek folder khulega, jisme `MQL5` naam ka folder hoga.

**3. Files sahi jagah copy karo**
- `BTCAIBridge.mq5` aur `BTCAIBridge.ex5` ko `MQL5\Experts\` mein daalo
- Saari `BTCAI*.mqh` files ko `MQL5\Include\` mein daalo
- `BTCSymbolProbe.mq5` ko `MQL5\Scripts\` mein daalo
- `BTCAIBridge_demo.set` ko `MQL5\Presets\` mein daalo

**4. Compile karo (ya seedha .ex5 use karo)**
MT5 mein Navigator (Ctrl+N) mein right-click karke **Refresh** karo. `.ex5` already compiled hai, wo seedha chal jayega.
Agar khud compile karna ho, to MetaEditor (F4) mein `BTCAIBridge.mq5` kholo aur **Compile** (F7) dabao. "0 errors" aana chahiye.
`BTCSymbolProbe.mq5` ko bhi isi tarah compile kar lo.

**5. Pehle BTCSymbolProbe chalao, aur output mujhe bhejo**
- Market Watch (Ctrl+M) mein right-click karke **Symbols** kholo, BTC dhoondo (XM par naam `BTCUSD` ya `BTCUSD#` jaisa ho sakta hai), aur **Show** karo.
- Navigator > Scripts > `BTCSymbolProbe` ko BTC chart par drag karo, aur symbol mein XM wala naam daalo.
- **Toolbox > Experts** tab mein output aayega (file `MQL5\Files\BTCSymbolProbe.txt` mein bhi save hota hai). Iska screenshot ya text mujhe bhejo.
  Isse main spread limit aur lot size XM ke hisaab se set kar dunga. Ye script koi trade nahi karta.

**6. WebRequest allow karo**
**Tools > Options > Expert Advisors** mein jao:
- "Allow algorithmic trading" tick karo
- "Allow WebRequest for listed URL" tick karo, aur ye URL add karo: `https://raw.githubusercontent.com`
- Telegram alerts chahiye to `https://api.telegram.org` bhi add karo

**7. EA ko BTCUSD chart par lagao**
- BTCUSD ka **H1** chart kholo (XM par naam ke saath `#` jaisa suffix ho sakta hai, EA khud sahi symbol dhoond leta hai).
- Navigator > Expert Advisors > `BTCAIBridge` ko chart par drag karo.
- **Inputs** tab mein **Load** dabao aur `BTCAIBridge_demo.set` chuno.
- Ye 3 cheezein check karo:
  - `InpTradeSymbol` = XM ka BTC symbol (jaise `BTCUSD` ya `BTCUSD#`)
  - `InpMagicNumber` = `26111601`
  - `InpRiskPercentPerTrade` = `0.5`
- **Common** tab mein "Allow Algo Trading" tick karo, phir **OK** dabao.
- Toolbar mein **Algo Trading** button ON karo.

**8. Check karo ki EA sahi chal raha hai**
Toolbox > Experts mein ye dikhna chahiye: `BTCAI symbol BTCUSD... ` aur `mode=DEMO`.
Chart par ek panel aayega, jisme decision status dikhega (abhi "FLAT (bias NONE)").

## Telegram (optional)
`InpTelegramToken` aur `InpTelegramChatId` sirf EA ke Inputs box mein daalo, preset file mein kabhi mat daalna.
Gold wale bot se **alag naya bot** banao, kyunki ek hi bot do EA par commands mein gadbad karta hai. Har message `[BTC]` se shuru hoga.

## Real account par kab chalaye
1. Pehle XM **demo** par kuch din chalao. Dekho ki trades zone mein hi lag rahe hain, SL lag raha hai, aur lot size sahi hai.
2. Uske baad hi real account par `InpAllowLiveAccount=true` set karo. Ye setting jaan-boojh kar hi badalna.
3. Real par bhi risk 0.5% hi rakho.

## Main rules (EA mein locked)
- Har trade par hard SL
- 0.5% risk, lot size risk ke hisaab se apne aap
- TP1 kam se kam 1.5R. TP1 par aadha band hota hai aur SL breakeven par aa jaata hai. Baaki TP2 tak chalta hai.
- Spread zyada ho (>$30), ya weekend/maintenance gap ho, ya FOMC/CPI/NFP news ho, to naya trade nahi lega
- Signal expire (`valid_until`) ho jaye to naya trade nahi lega

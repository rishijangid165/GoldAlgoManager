# Extreme fear par BUY: kya data kehta hai?

**Seedha jawab:** Bahut dar (Fear & Greed 20 ya usse neeche) mein BUY karna **ek mazboot, proven edge nahi hai.** Kabhi bounce mila (jaise March 2020), kabhi dar ke baad price aur gira (2018, 2022, kuch 2025–26 ke episodes). 30 din ka average return lagbhag normal din jaisa tha. 90 din par **normal din se kam** mila. Jo threshold 2018–2022 par sabse acchi lagi (F&G ≤ 10), wo 2023 ke baad 30 din ke hold par **fail** hui. **XM par 30–90 din rakhna viable nahi** — overnight swap ne profit kha liya.

Fear-weighted weekly DCA ne saadi weekly DCA se **thoda** zyada diya (lagbhag +310% vs +285%), lekin isi duration mein spot **buy-and-hold +582%** raha. Yani “dar par zyada kharido” DCA ko thoda behtar bana sakta hai, lekin “sirf dar par timed BUY” buy-and-hold ko nahi hara paya.

Ye lesson **auto-rule nahi** hai. Naya trading rule tabhi banega jab backtest, walk-forward aur paper teeno pass hon. Profit ki koi guarantee nahi. Is episode ka aage kya hoga, **data nahi hai**.

## Data

| Cheez | Source |
|---|---|
| Fear & Greed, daily | Alternative.me, 2018-02-01 se 2026-11-19 (3,210 din; 4 din missing: 2018-04-14–16, 2024-10-26) |
| BTC daily OHLC | **Binance BTCUSDT 1d**, public `data-api.binance.vision`, 2018-01-01 se 2026-11-18 (3,244 complete days). Spot USDT, no leverage. |
| Entry rule | **No lookahead:** F&G date D par signal, entry **agli daily close (D+1)**. Return close se close. MAE = entry ke baad ke dinon ka sabse neeche low. |
| Delta India check | 1D sirf Oct 2025 se hai (12 mahine). Overlap 414 din, Binance close se median fark **0.039%**, max **0.077%**. Source theek hai. |

Scripts: `fetch_prices.py`, `analyze.py`. Numbers: `numbers.json`.

Independent fear episodes (alag-alag streaks, ek crash ko 30 baar count nahi):

| Threshold | Independent episodes | Overlapping signal days | Non-overlap 30d events | Non-overlap 90d events |
|---|---|---|---|---|
| F&G ≤ 10 | 41 | — | 15 | 11 |
| F&G ≤ 20 | 110 | 421 | 39 | 18 |
| F&G ≤ 25 | 130 | — | 48 | 20 |

90d sample chhota hai (18 independent ≤20 events). Ise “pakka” mat samjho.

## 1. Event study (costs se pehle)

Har row: signal ke **agli close** se 7 / 30 / 90 din. Non-overlap = pehla signal, phir N din ignore (ek crash 30 baar nahi). Baseline = har din ka wahi window. Greed = F&G ≥ 75, same rule.

**F&G ≤ 20, non-overlapping**

| Window | n | Mean | Median | % up | Worst | Median MAE | Baseline mean | vs baseline |
|---|---|---|---|---|---|---|---|---|
| 7d | 99 | +1.15% | +0.77% | 54% | −32.7% | −5.3% | +0.83% | slightly better |
| 30d | 39 | +3.54% | +1.34% | 59% | −28.8% | −8.9% | +3.79% | **slightly worse** |
| 90d | 18 | **−1.81%** | −0.67% | 50% | −53.0% | −20.5% | **+14.01%** | **much worse** |

**Sensitivity**

| Signal | 30d n | 30d mean | 30d median | 30d % up | 90d n | 90d mean | 90d median |
|---|---|---|---|---|---|---|---|
| F&G ≤ 10 | 15 | +7.86% | −0.04% | 47% | 11 | +11.43% | +13.31% |
| F&G ≤ 20 | 39 | +3.54% | +1.34% | 59% | 18 | −1.81% | −0.67% |
| F&G ≤ 25 | 48 | +0.96% | +0.73% | 60% | 20 | −0.74% | −2.21% |
| F&G ≥ 75 | 25 | +8.70% | +1.03% | 64% | 11 | +37.36% | +37.06% |
| All days | 3178 | +3.79% | +1.50% | 54% | 3118 | +14.01% | +3.70% |

F&G ≤ 10 ka 30d **mean** accha dikhta hai, lekin **median ~0** aur 47% jeet — matlab kuch bade bounce (jaise Mar 2020) average ko kheenchte hain. 90d par ≤10 ka mean (+11.4%) bhi baseline (+14.0%) se neeche hai.

Greed wale dinon ke baad bhi average upar gaya. Iska matlab ye nahi ki “greed par BUY karo” — ye sample mein lambi bull runs hain, aur 90d greed wale events sirf 11 hain. Contrast itna hai: **sirf dar unique buy signal nahi dikha.**

## 2. Strategies, costs, aur XM

Spot cost: 0.2% round trip. XM CFD: $40/BTC spread (round trip) + **$35/BTC/night** long swap. Buy-and-hold isi period mein (2018-02-01 → 2026-11-18, spot, 0.2% RT): **+582%**, max DD **77%**.

| Strategy | Cost | Trades | Win rate | Expectancy | PF | Total return | Max DD |
|---|---|---|---|---|---|---|---|
| Buy F&G≤20, hold 30d | spot | 38 | 55% (21/17) | +3.30% | 1.75 | **+117%** | 51% |
| Buy F&G≤20, hold 30d | XM | 38 | 34% | −4.75% | 0.50 | **−91%** | 95% |
| Buy F&G≤20, hold 90d | spot | 18 | 44% (8/10) | −2.28% | 0.76 | **−62%** | 75% |
| Buy F&G≤20, hold 90d | XM | 18 | 28% | −24.5% | 0.13 | **−100%** | ~100% |
| Confirm (F&G>25 or close>SMA20), exit 90d or −15% stop | spot | 26 | 31% (8/18) | −0.91% | 0.90 | **−51%** | 76% |
| Same confirm | XM | 26 | 19% | −17.5% | 0.19 | **−100%** | ~100% |
| Buy-and-hold | spot | 1 | — | — | — | **+582%** | 77% |
| Buy-and-hold | XM (swap!) | 1 | — | — | — | **−635%** | — |

30 din ka spot hold **profit** mein raha, lekin buy-and-hold ka chhota hissa (117% vs 582%), kyunki darmiyan ke bull dinon mein ye strategy often bahar baithi. 90 din aur “confirmation” wale versions spot par bhi ghaate mein rahe.

**XM viability:** nahi. 30 din ke long par swap ~$35 × 30 = **$1,050 per 1 BTC** (~1.5–3%+ price par depend karta hai), jo is edge se bada hai. $1,000 account, 0.01 lot, F&G≤20 hold-30d: 38 trades, average swap **$10.50**/trade, average P/L **−$7.42**, account $1,000 → **$718**, max DD **$430 (43%)**. 90 din to account almost zero. Lambe hold ke liye XM CFD nahi, spot.

**Fear-weighted DCA vs plain DCA** (weekly, same total cash, spot 0.2%):

| Plan | Buys | Total return | Max DD |
|---|---|---|---|
| Plain weekly $1 (scaled) | 459 | **+285%** | (see `numbers.json`) |
| Double when F&G≤25, half when F&G≥75, then same total cash | 459 | **+310%** | slightly similar path |
| Buy-and-hold, same start, same total cash at day 1 | 1 | **+582%** | 77% |

DCA ko dar par zyada aur greed par kam daalna thoda madadgar raha. Timed “sirf dar par trade” se ye alag baat hai, aur phir bhi B&H se peeche.

## 3. Walk-forward (threshold sirf 2018–2022 par chuni)

Rule: 2018–2022 par, {10, 15, 20, 25} mein se kam se kam 8 trades wale 30d spot holds, **sabse zyada excess mean** (non-overlap 30d vs all-day baseline). **Chuni: F&G ≤ 10.** Phir 2023–ab tak **bina badle**.

Train 2018–2022, 30d spot:

| Threshold | Trades | Expectancy | PF | Total return | Excess vs baseline |
|---|---|---|---|---|---|
| 10 (chosen) | 9 | +9.45% | 4.55 | +97% | **+8.83%** |
| 15 | 18 | +8.11% | 3.87 | +229% | +4.37% |
| 20 | 28 | +3.67% | 1.82 | +92% | +1.06% |
| 25 | 33 | +2.17% | 1.32 | +9% | −2.40% |

Test 2023–now (unchanged):

| Threshold | Window | Trades | Expectancy | PF | Total return | Event mean | Baseline | Excess |
|---|---|---|---|---|---|---|---|---|
| **10 chosen** | 30d | **5** | **−1.26%** | **0.43** | **−6.4%** | −1.06% | +3.82% | **−4.88%** |
| 10 | 90d | 4 | +10.0% | 2.54 | +34% | +10.2% | +11.8% | −1.65% |
| 20 | 30d | 10 | +2.27% | 1.53 | +13% | +0.63% | +3.82% | −3.19% |
| 20 | 90d | 5 | +10.4% | 2.53 | +43% | +10.8% | +11.8% | −1.04% |

**Out-of-sample 30d, chosen threshold fail.** Sample chhota hai (5 trades), lekin direction seedhi hai: jo rule purane data par sabse chamki, naye data par baseline se kam rahi. 90d OOS mean positive tha, lekin phir bhi baseline se thoda neeche, aur sirf 4–5 trades.

## 4. Bear vs bull

Saal ki BTC return se label: **bear** 2018 (−72%), 2022 (−65%). **Bull** 2019, 2020, 2021, 2023, 2024. **Mixed** 2025 (−7%), 2026 YTD −29%. 2023 mein F&G≤20 ka koi episode nahi mila (tez bull, dar nahi aaya).

F&G ≤ 20, non-overlap, signal ke saal ke hisaab se (forward calendar days, poori series par):

| Regime | 30d n | 30d mean | 30d baseline | 30d excess | 90d n | 90d mean | 90d baseline | 90d excess |
|---|---|---|---|---|---|---|---|---|
| Bear (2018, 2022) | 17 | +4.1% | −5.3% | **+9.4%** | 8 | **−12.7%** | −13.3% | +0.6% |
| Bull | 13 | +4.6% | +8.8% | **−4.2%** | 6 | +6.8% | +29.1% | **−22.3%** |
| Mixed 2025–26 | 9 | +0.9% | −0.6% | +1.5% | 4 | +7.0% | −0.5% | +7.5% |

Matlab seedha:

- **Bear mein** 30 din par fear-buy, girte market ke baseline se behtar rahi, lekin 90 din par **phir bhi average loss (~13%)** — dar ke baad aur girna possible hai.
- **Bull mein** fear ka wait karne se wo 90 din miss ho jaate hain jab market already tez chalta hai (excess −22%).
- Isliye “real dimag dar mein khareedta hai” ka hissa (bear bounce) data mein dikhta hai, lekin bina context ke automatic BUY nahi.

## 5. Abhi ka mahol (19 Nov 2026)

- Fear & Greed **10** (Extreme Fear), date 2026-11-19.
- Is episode ki shuruaat **13 Nov 2026** (us din 20). **7 din** se F&G ≤ 20. ≤ 10 par **1 din**.
- Last complete BTC close: **18 Nov 2026, $63,068** (Binance). Is episode ke 7/30/90 din ke nateeje **data nahi hai** — abhi khuli hai.

**Milte-julte purane episodes** (pehle din jab F&G ≤ 10 hua, entry agli close; complete 7/30/90d wale, sabse milti-julti pehle). Ye history hai, prediction nahi.

| First F&G≤10 | Episode | Days in | 7d | 30d | 90d |
|---|---|---|---|---|---|
| 2020-03-13 | 2020-03-09..04-07 (Covid low, min 8) | 5 | +19.6% | +32.2% | +83.0% |
| 2021-05-24 | 2021-05-20..05-24 (min 10) | 5 | −4.3% | −9.6% | +29.1% |
| 2020-04-12 | 2020-04-10..04-24 (min 10) | 3 | −0.2% | +36.1% | +36.0% |
| 2022-01-08 | 2022-01-06..01-08 (min 10) | 3 | +2.9% | +5.2% | +2.1% |
| 2022-05-10 | 2022-05-08..07-08 (min 6) | 3 | −1.3% | 0.0% | **−20.5%** |
| 2025-11-15 | 2025-11-13..11-26 (min 10) | 3 | −7.9% | −6.8% | **−25.9%** |
| 2026-03-22 | 2026-03-20..04-13 (min 8) | 3 | −5.8% | +10.3% | −10.7% |
| 2026-02-06 | 2026-01-30..03-04 (min 5) | 8 | +0.8% | −1.2% | +15.7% |
| 2021-07-21 | 2021-07-20..07-21 (min 10) | 2 | +23.9% | +51.2% | +104.4% |
| 2018-11-25 | 2018-11-21..12-17 (min 9) | 5 | +0.6% | −2.2% | −3.1% |

12 complete “first ≤10” events ka 30d: mean accha, median ~0, mix of huge bounces and losses. 90d bhi mixed (March 2020 / July 2021 vs May 2022 / Nov 2025).

Jo streaks **7 din** F&G ≤ 20 tak khich chuki thin (abhi jaisi), unke 12 complete cases: 30d median **+1.5%** (58% up, worst −29%); 90d median **−10.1%** (42% up, worst −47%). 7 din ke dar ke baad bhi 90 din ka typical nateeja negative median tha.

## Verdict

1. Extreme fear **kabhi** accha kharid ka pal raha, khas kar jab crash ke baad tezi se bounce hua. Ye “real dimag” wala hissa hai.
2. Data usko **automatic BUY rule** nahi banata: 30d ≈ baseline, 90d < baseline, walk-forward par chuni hui threshold OOS fail, bear mein 90d par ab bhi loss, XM swap lambe hold ko tod deta hai.
3. Jo cheez thodi support karti hai: **spot** par fear-weighted **DCA** (har hafte thoda, dar par double, greed par aadha) — saadi DCA se thoda behtar, B&H se kam, leverage nahi.
4. Abhi F&G 10 hai, 7 din se dar chal raha hai. Aage kya hoga **data nahi hai**. Purane milte cases dono taraf ke hain. Core rules wahi: paper only, A/A+ setup, Rishi ke “haan” ke bina real order nahi.

Lesson `L09` dimag ke `lessons.json` mein isi nateeje ke saath jodi gayi hai — warning, auto-rule nahi.

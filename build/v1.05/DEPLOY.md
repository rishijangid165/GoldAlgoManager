# GoldAIBridge v1.05 — deploy note

Built 17 Nov 2026 (IST). Compiled in `C:\MT5d` (Wine MetaEditor, not the live `C:\MT5` tree): **0 errors, 0 warnings**. `GoldPropGuardSelfTest` also compiled **0 errors, 0 warnings**. The live demo EA was **not** hot-swapped; replacing a running `.ex5` does not reload it, and a desktop reattach is required.

`InpAllowLiveAccount` remains **false**.

## What v1.05 adds

1. **Real-money partial + breakeven** (playbook v3.3):
   - `InpPartialAtR` (default `1.0`) — close a partial when unrealized R vs the original SL reaches this (0 = off).
   - `InpPartialPct` (default `50`) — percent of volume to close.
   - `InpBEAfterPartial` (default `true`) — move the remaining SL to breakeven after the partial.
   - `InpManageManual` (default `true`) — also manage magic-0 manual XAUUSD positions **that already have a hard SL**. The EA will not invent a stop for a no-SL manual ticket.
   - The existing decision-TP1 path is unchanged (`InpTP1CloseFraction`, `InpBreakevenOffsetPoints`). If price hits +1R first, that path fires; if the decision TP1 is hit first, that path still fires. Trailing after a partial remains EA-magic only, and is still off unless `InpTrailEnabled` is on.

2. **Daily-loss log spam fix:** the 2% `DAILY_LOSS` entry block is journaled and printed **once per state change** (blocked / cleared), not on every tick as the floating loss percentage moves.

3. **Daily-loss baseline survives a restart:** start-of-day equity is persisted in login+magic GlobalVariables **and** in `MQL5/Files/GoldAI_<magic>_<login>_daystart.txt`. A mid-day terminal restart must restore today's baseline, not capture the already-drawn-down equity as a new day. If server time is not ready at `OnInit`, the baseline is not reset.

## How to attach (when you are ready)

1. Copy `build/v1.05/GoldAIBridge.ex5` and `GoldAIBridge.mq5` into the live portable tree `C:\MT5\MQL5\Experts\` (and the Include files only if they changed — they did not for this build).
2. On the XAUUSD M15 chart, remove the running GoldAIBridge and attach this build by **Load** of the live token-bearing preset: `C:\MT5\MQL5\Presets\GoldAIBridge.set` or `C:\MT5\GoldAIBridge.set` (trailing OFF, Friday close ON, Telegram token already in that file). Do not load the repo template in `mql5/Presets/GoldAIBridge.set` for a live attach — that template is token-free and still has older trailing defaults.
3. Confirm the new v1.05 inputs after load (missing keys take the compiled defaults): `InpPartialAtR=1.0`, `InpPartialPct=50`, `InpBEAfterPartial=true`, `InpManageManual=true`.
4. If the terminal was fully restarted, re-add WebRequest URLs if you see error 4014: `https://api.telegram.org` and `https://raw.githubusercontent.com`.
5. Startup Telegram should say `GoldAIBridge online (v1.05, ...)`. Chart comment header: `GoldAI Bridge v1.05`.

Do not enable `InpAllowLiveAccount`. Do not commit the live `.set` (it holds the Telegram token).

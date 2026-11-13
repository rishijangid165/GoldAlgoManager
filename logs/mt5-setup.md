# MT5 setup notes (Linux box + Wine)

Recorded 13 Nov 2026, 00:54 IST (Asia/Calcutta). Box file timestamps are UTC; times below are converted.

## Result

MetaTrader 5 is installed under Wine and GoldAIBridge compiles cleanly:

- **0 errors, 0 warnings**
- CPU target: `X64 Regular`
- Compile time: ~2107 ms
- Compiled binary: `/workspace/out/GoldAIBridge.ex5` (115,810 bytes)
- Sources kept in `/workspace/gold-algo/mql5`
- Zip: `/workspace/out/GoldAIBridge_v1.zip` (mql5 tree at zip root + `current.json`)
- Full compiler log: `/workspace/gold-algo/logs/GoldAIBridge-compile.log`

No broker account was created and nothing was logged in. Demo account setup is still to be done later in the GUI.

## Why not distro Wine

`apt-get` cannot reach Debian repos from this box. `deb.debian.org` is intercepted at `198.18.0.1` and returns HTTP 500 (or TLS EOF on HTTPS). `curl` to the real Fastly edge works, but apt always goes through that proxy. `xvfb-run` was already installed; a native `wine` / `wine64` package was not.

Used a portable Wine instead: Kron4ek **Wine 11.21 Staging amd64-wow64** (SHA256 `a70a9691c42e35f32bab8a8a2deb8f0321aa3081b393c73575727ca76fa503ab`).

## Install paths

| Item | Path |
| --- | --- |
| Wine tree | `/home/box/wine/wine-11.21-staging-amd64-wow64` |
| Wine binary | `/home/box/wine/wine-11.21-staging-amd64-wow64/bin/wine` |
| Wine prefix (`WINEARCH=win64`) | `/home/box/.wine-mt5` |
| MT5 install (portable) | `/home/box/.wine-mt5/drive_c/MT5` |
| `terminal64.exe` | `/home/box/.wine-mt5/drive_c/MT5/terminal64.exe` |
| `MetaEditor64.exe` | `/home/box/.wine-mt5/drive_c/MT5/MetaEditor64.exe` |
| Data dir (portable) | `/home/box/.wine-mt5/drive_c/MT5` (i.e. `C:\MT5`) |
| EA source in MT5 | `C:\MT5\MQL5\Experts\GoldAIBridge.mq5` |
| Project includes in MT5 | `C:\MT5\MQL5\Include\GoldAI*.mqh` |
| Stdlib `Trade.mqh` | `C:\MT5\MQL5\Include\Trade\Trade.mqh` |

Display used: existing desktop `$DISPLAY=:3`. xvfb was not required.

## Installer

The URL in the brief (`…/metaquotes.software.corp/metatrader5/mt5setup.exe`) returned **404**. The current official installer is:

`https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe`

(64-bit PE32+, ~22.7 MB). Saved at `/tmp/mt5-install/mt5setup.exe`.

Silent install (Wine prefix already initialized with `wineboot --init`, `WINEDLLOVERRIDES=mscoree,mshtml=` to skip Mono/Gecko prompts):

```bash
export PATH="/home/box/wine/wine-11.21-staging-amd64-wow64/bin:$PATH"
export WINEPREFIX="/home/box/.wine-mt5"
export WINEARCH=win64
export WINEDLLOVERRIDES="mscoree,mshtml="
wine /tmp/mt5-install/mt5setup.exe /auto /path:"C:\\MT5"
```

The installer process exited with code 1, but both binaries and `C:\MT5` were present. The MQL5 standard library was not unpacked until `terminal64.exe /portable /skipupdate` was started briefly; `Trade.mqh` appeared within a few seconds and the terminal was killed immediately so no account/login UI was used.

## Compile command

Copy sources, then compile headlessly:

```bash
export PATH="/home/box/wine/wine-11.21-staging-amd64-wow64/bin:$PATH"
export WINEPREFIX="/home/box/.wine-mt5"
export WINEDLLOVERRIDES="mscoree,mshtml="

MT5="/home/box/.wine-mt5/drive_c/MT5"
cp /workspace/gold-algo/mql5/Experts/GoldAIBridge.mq5 "$MT5/MQL5/Experts/"
cp /workspace/gold-algo/mql5/Include/*.mqh "$MT5/MQL5/Include/"

cd "$MT5"
wine MetaEditor64.exe /portable \
  /compile:"MQL5\\Experts\\GoldAIBridge.mq5" \
  /log:"MQL5\\Experts\\compile.log"
```

The log is UTF-16. MetaEditor's process exit code was 1 even on a clean build; trust the log's `Result:` line, not the exit code.

## Compile note (2026-11-13, v1.02)

MT5 LiveUpdate around 12:17 UTC replaced `C:\MT5\MetaEditor64.exe` with build 6318 (70,119,528 bytes). That binary fails every compile under this Wine prefix with `(0,0) : error 124: fatal compiler error: unknown error`, including a 3-line script in a fresh portable folder. Do not compile from the live `C:\MT5` tree with that 6318 editor — and do not overwrite `C:\MT5\MQL5\Experts\GoldAIBridge.ex5` while the market is open.

Workaround: the later-installer editor (`C:\MT5\MetaEditor64-fresh.exe`, 70,701,752 bytes) compiles cleanly when **copied as `MetaEditor64.exe` into a separate portable folder** (used `C:\MT5d`). Launching it as `MetaEditor64-fresh.exe` from the live tree did not produce a compile log. Example:

```bash
export PATH="/home/box/wine/wine-11.21-staging-amd64-wow64/bin:$PATH"
export WINEPREFIX="/home/box/.wine-mt5"
export WINEDLLOVERRIDES="mscoree,mshtml="
export DISPLAY=":3"

MT5D="/home/box/.wine-mt5/drive_c/MT5d"
# (sandbox already has official Include/, our GoldAI*.mqh, and GoldAIBridge.mq5)
cd "$MT5D"
wine MetaEditor64.exe /portable   /compile:"MQL5\\Experts\\GoldAIBridge.mq5"   /log:"MQL5\\Experts\\compile.log"
```

v1.02 result: 0 errors, 0 warnings, 2804 ms, `ex5` 158,106 bytes. Copy the `ex5` into the live `C:\MT5\MQL5\Experts\` folder only after the gold market is closed, then reattach with `C:\MT5\GoldAIBridge.set`.

## Source fix

First compile: **0 errors, 1 warning**.

- `GoldAIBridge.mq5` line 306: `warning 43: possible loss of data due to type conversion from 'uint' to 'int'`
- `FileReadArray()` returns `uint`. Changed `const int got` to `const uint got` and the failure check from `got <= 0` to `got == 0`.
- Design unchanged. Recompiled to **0 errors, 0 warnings**.

## Blocking / follow-ups

- Distro Wine still cannot be installed with apt until the `198.18.0.1` egress proxy is fixed.
- Demo (or any) broker account was intentionally not created. To attach the EA on a chart, open `terminal64.exe /portable` from the prefix above and complete a demo login in the GUI.
- `DecisionURL` still needs to be set in EA inputs to `https://raw.githubusercontent.com/rishijangid165/GoldAlgoManager/main/decisions/current.json`, and `https://raw.githubusercontent.com` must be allowed under Tools → Options → Expert Advisors.

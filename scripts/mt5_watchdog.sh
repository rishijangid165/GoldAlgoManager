#!/bin/bash
# Gold MT5 watchdog: restarts the MetaQuotes-Demo terminal (C:\MT5, gold prefix only) if the process is gone.
# Never touches the BTC prefixes/folders (C:\MT5btc etc.). Logs to logs/mt5_watchdog.log.
# 2026-11-20: detect the gold terminal either as the /portable /config:gold_ea_telegram.ini launch OR as
# "C:\MT5\terminal64.exe" (how MetaTrader5.initialize(path=...) launches it), only in WINEPREFIX=/home/box/.wine-mt5.
# Previously a python-launched terminal did not match, so the watchdog relaunched every 3 min and each copy exited.
export PATH="/home/box/wine/wine-11.21-staging-amd64-wow64/bin:$PATH" WINEPREFIX="/home/box/.wine-mt5" WINEDLLOVERRIDES="mscoree,mshtml=" DISPLAY="${DISPLAY:-:3}"
LOG=/workspace/gold-algo/logs/mt5_watchdog.log
gold_running() {
  local p
  for p in $(pgrep -f 'terminal64\.exe'); do
    tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -qx 'WINEPREFIX=/home/box/.wine-mt5' || continue
    if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -Eq '^(C:\\MT5\\terminal64\.exe|terminal64\.exe /portable /config:gold_ea_telegram\.ini)'; then
      return 0
    fi
  done
  return 1
}
while true; do
  if ! gold_running; then
    echo "$(date -u +%FT%TZ) terminal missing -> restart" >> "$LOG"
    (cd /home/box/.wine-mt5/drive_c/MT5 && nohup wine terminal64.exe /portable /config:gold_ea_telegram.ini /skipupdate >/tmp/mt5_restart.log 2>&1 &)
    sleep 120
  fi
  sleep 60
done

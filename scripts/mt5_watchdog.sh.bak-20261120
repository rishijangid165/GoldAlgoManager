#!/bin/bash
# Gold MT5 watchdog: restarts the MetaQuotes-Demo terminal (C:\MT5, gold prefix only) if the process is gone.
# Never touches the BTC prefixes. Logs to logs/mt5_watchdog.log.
export PATH="/home/box/wine/wine-11.21-staging-amd64-wow64/bin:$PATH" WINEPREFIX="/home/box/.wine-mt5" WINEDLLOVERRIDES="mscoree,mshtml=" DISPLAY="${DISPLAY:-:3}"
LOG=/workspace/gold-algo/logs/mt5_watchdog.log
while true; do
  if ! pgrep -f "terminal64.exe /portable /config:gold_ea_telegram.ini" >/dev/null; then
    echo "$(date -u +%FT%TZ) terminal missing -> restart" >> "$LOG"
    (cd /home/box/.wine-mt5/drive_c/MT5 && nohup wine terminal64.exe /portable /config:gold_ea_telegram.ini /skipupdate >/tmp/mt5_restart.log 2>&1 &)
    sleep 120
  fi
  sleep 60
done

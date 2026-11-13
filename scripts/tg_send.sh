#!/bin/bash
# Usage: tg_send.sh "message text"   (token from env TELEGRAM_BOT_TOKEN_NEW)
TELEGRAM_CHAT_ID=730711407
TOKEN="${TELEGRAM_BOT_TOKEN_NEW}"
[ -z "$TOKEN" ] && { echo "fail: TELEGRAM_BOT_TOKEN_NEW not set"; exit 1; }
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=$1" | python3 -c "import sys,json;d=json.load(sys.stdin);print('ok' if d.get('ok') else 'fail '+str(d.get('description')))"

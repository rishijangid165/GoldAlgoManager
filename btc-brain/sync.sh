#!/usr/bin/env bash
# Copy the latest paper-trade file and alert levels into btc-brain/paper/,
# then commit and push if anything changed. Touches only btc-brain/.
# Reads GOLDALGO_GITHUB_TOKEN from the environment and never echoes it.
set -euo pipefail
set +x
export GIT_TERMINAL_PROMPT=0

if [[ -z "${GOLDALGO_GITHUB_TOKEN:-}" ]]; then
  echo "error: GOLDALGO_GITHUB_TOKEN is not set in the environment" >&2
  exit 1
fi

BRAIN_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$BRAIN_DIR" rev-parse --show-toplevel)"

if [[ "$BRAIN_DIR" != "$REPO_ROOT/btc-brain" ]]; then
  echo "error: sync.sh must live at <repo>/btc-brain/sync.sh (found $BRAIN_DIR)" >&2
  exit 1
fi

PAPER_SRC="${PAPER_SRC:-/workspace/btc_paper_trades.json}"
ALERT_SRC="${ALERT_SRC:-/workspace/.btc_alert_state.json}"

mkdir -p "$BRAIN_DIR/paper"

if [[ -f "$PAPER_SRC" ]]; then
  cp "$PAPER_SRC" "$BRAIN_DIR/paper/btc_paper_trades.json"
else
  echo "warn: $PAPER_SRC not found, skipping paper trades copy"
fi

if [[ -f "$ALERT_SRC" ]]; then
  python3 - "$ALERT_SRC" "$BRAIN_DIR/paper/alert_levels.json" << 'PY'
import json, sys
src, dest = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    data = json.load(f)
# Levels only. Do not copy Telegram chat IDs, tokens, or other secrets.
out = {
    "levels": data.get("levels", {}),
    "last_check": data.get("last_check"),
}
with open(dest, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
    f.write("\n")
PY
else
  echo "warn: $ALERT_SRC not found, skipping alert levels copy"
fi

cd "$REPO_ROOT"

# Stage only the synced paper files. Never add anything outside btc-brain/.
to_add=()
[[ -f btc-brain/paper/btc_paper_trades.json ]] && to_add+=("btc-brain/paper/btc_paper_trades.json")
[[ -f btc-brain/paper/alert_levels.json ]] && to_add+=("btc-brain/paper/alert_levels.json")

if [[ ${#to_add[@]} -eq 0 ]]; then
  echo "Nothing to stage."
else
  git add -- "${to_add[@]}"
fi

ist_now() {
  python3 -c "import time; print(time.strftime('%Y-%m-%d %H:%M IST', time.gmtime(time.time()+19800)))"
}

if git diff --cached --quiet; then
  echo "Nothing to commit."
else
  git commit -m "sync(btc-brain): paper trades and alert levels $(ist_now)"
fi

# If HEAD is not ahead of the upstream, do not push.
upstream=""
if upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"; then
  ahead="$(git rev-list --count "${upstream}..HEAD")"
  if [[ "$ahead" -eq 0 ]]; then
    echo "Already up to date with ${upstream}. Nothing to push."
    exit 0
  fi
fi

askpass="$(mktemp)"
chmod 700 "$askpass"
# Token is read from the environment at prompt time; it is not written to this file.
cat > "$askpass" << 'ASK'
#!/bin/sh
case "$1" in
  *[Uu]sername*) printf '%s\n' "x-access-token" ;;
  *) printf '%s\n' "${GOLDALGO_GITHUB_TOKEN}" ;;
esac
ASK
cleanup() { rm -f "$askpass"; }
trap cleanup EXIT

GIT_ASKPASS="$askpass" GIT_TERMINAL_PROMPT=0 git push origin HEAD
echo "Push complete."

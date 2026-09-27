#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

DOWNLOADS="https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/"
action=start
json=""
for arg in "$@"; do
  case "$arg" in
    --json) json=yes ;;
    start | stop) action="$arg" ;;
    *) echo "Usage: share.sh [start|stop] [--json]" >&2; exit 2 ;;
  esac
done

cloudflared_bin() {
  for candidate in "$(command -v cloudflared || true)" "${HOME}/.local/bin/cloudflared" /opt/homebrew/bin/cloudflared /usr/local/bin/cloudflared; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      echo "$candidate"
      return
    fi
  done
}

stop_share() {
  [ -n "$(active_share_url)" ] || return 1
  pid="$(share_field pid)"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 50); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$SHARE_FILE"
}

print_ready() {
  if [ -n "$json" ]; then
    printf '{"event":"share_ready","url":"%s","viewer_local":"%s","reused":%s}\n' "$1" "$VIEWER_URL" "$2"
    return
  fi
  [ "$2" = true ] && echo "Already sharing. This link stays the same until you unshare."
  cat <<EOF
$1

Anyone with this link can control the logged-in browser. Treat it as a secret.
It can take a few seconds before the link loads.
Stop it with: cloakroom unshare
The link changes every time you start a new share.
EOF
}

if [ "$action" = stop ]; then
  stopped=true
  stop_share || stopped=false
  if [ -n "$json" ]; then
    printf '{"event":"share_stopped","stopped":%s}\n' "$stopped"
  elif [ "$stopped" = true ]; then
    echo "Stopped the remote viewer. The old link no longer works."
  else
    echo "No remote viewer is running."
  fi
  exit 0
fi

existing="$(active_share_url)"
if [ -n "$existing" ] && [ "$(share_field viewer_local)" = "$VIEWER_URL" ]; then
  print_ready "$existing" true
  exit 0
fi
stop_share || true

if [ "$VIEWER_PORT" = "$CDP_PORT" ]; then
  echo "Refusing to share port ${VIEWER_PORT}: that is the CDP port. Share the viewer only." >&2
  exit 1
fi

if [ "$(health)" != healthy ]; then
  [ -n "$json" ] && echo '{"event":"starting","detail":"Starting the browser."}'
  bash "${CLOAKROOM_ROOT}/start.sh" >&2
fi

binary="$(cloudflared_bin)"
if [ -z "$binary" ]; then
  cat >&2 <<EOF
cloudflared is not installed.
On a Mac with Homebrew: brew install cloudflared
Otherwise download it from ${DOWNLOADS}
Then run: cloakroom share
EOF
  exit 1
fi

mkdir -p "$STATE_DIR"
nohup "$binary" tunnel --no-autoupdate --url "$VIEWER_URL" >"$SHARE_LOG" 2>&1 </dev/null &
pid=$!

url=""
for _ in $(seq 1 240); do
  url="$(grep -Eo 'https://[A-Za-z0-9-]+\.trycloudflare\.com' "$SHARE_LOG" | head -n 1 || true)"
  [ -n "$url" ] && break
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "cloudflared exited." >&2
    tail -c 2000 "$SHARE_LOG" >&2
    exit 1
  fi
  sleep 0.25
done

if [ -z "$url" ]; then
  kill "$pid" 2>/dev/null || true
  echo "Timed out waiting for the share URL." >&2
  tail -c 2000 "$SHARE_LOG" >&2
  exit 1
fi

printf '{"pid":%s,"url":"%s","viewer_local":"%s"}\n' "$pid" "$url" "$VIEWER_URL" >"${SHARE_FILE}.tmp"
mv "${SHARE_FILE}.tmp" "$SHARE_FILE"
print_ready "$url" false

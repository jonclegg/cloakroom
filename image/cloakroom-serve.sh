#!/bin/bash
# Runs after the upstream /entrypoint.sh has started Xvfb (:99) and openbox.
set -euo pipefail

DATA_DIR=/tmp/cloakserve
PROFILE_DIR=/profile/default
PROFILE_KEY="${CLOAKROOM_FINGERPRINT_SEED:-__default__}"

apply_container_timezone() {
  [ -n "${TZ:-}" ] || return 0
  zone="/usr/share/zoneinfo/${TZ}"
  if [ ! -e "$zone" ]; then
    echo "Timezone ${TZ} is not installed (${zone})." >&2
    exit 1
  fi
  ln -snf "$zone" /etc/localtime
  printf '%s\n' "$TZ" > /etc/timezone
}

apply_container_timezone

mkdir -p "$DATA_DIR" "$PROFILE_DIR"
rm -f "$PROFILE_DIR"/SingletonLock "$PROFILE_DIR"/SingletonSocket "$PROFILE_DIR"/SingletonCookie

# cloakserve deletes <data-dir>/<key> on shutdown but refuses to delete paths that
# resolve outside <data-dir>, so a symlink keeps the profile alive on the volume.
ln -sfn "$PROFILE_DIR" "$DATA_DIR/$PROFILE_KEY"

x11vnc -display :99 -forever -shared -nopw -localhost -rfbport 5900 -quiet -bg -o /tmp/x11vnc.log
websockify --web /usr/share/novnc 6080 localhost:5900 >/tmp/websockify.log 2>&1 &

# The chat API. It connects to the browser over loopback on first use, so it can
# start before Chrome is up. The health check covers it, so a crash shows.
python -u /opt/cloakroom/agent/server.py &

args=(--start-maximized --data-dir="$DATA_DIR")
if [ -n "${CLOAKROOM_FINGERPRINT_SEED:-}" ]; then
  args+=(--fingerprint="$CLOAKROOM_FINGERPRINT_SEED")
fi
if [ -n "${CLOAKROOM_PROXY:-}" ]; then
  args+=(--proxy-server="$CLOAKROOM_PROXY")
fi

exec python /usr/local/bin/cloakserve-headed.py "${args[@]}" "$@"

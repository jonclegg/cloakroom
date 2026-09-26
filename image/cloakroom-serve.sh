#!/bin/bash
# Runs after the upstream /entrypoint.sh has started Xvfb (:99) and openbox.
set -euo pipefail

DATA_DIR=/tmp/cloakserve
PROFILE_DIR=/profile/default
PROFILE_KEY="${CLOAKROOM_FINGERPRINT_SEED:-__default__}"

mkdir -p "$DATA_DIR" "$PROFILE_DIR"
rm -f "$PROFILE_DIR"/SingletonLock "$PROFILE_DIR"/SingletonSocket "$PROFILE_DIR"/SingletonCookie

# cloakserve deletes <data-dir>/<key> on shutdown but refuses to delete paths that
# resolve outside <data-dir>, so a symlink keeps the profile alive on the volume.
ln -sfn "$PROFILE_DIR" "$DATA_DIR/$PROFILE_KEY"

x11vnc -display :99 -forever -shared -nopw -localhost -rfbport 5900 -quiet -bg -o /tmp/x11vnc.log
websockify --web /usr/share/novnc 6080 localhost:5900 >/tmp/websockify.log 2>&1 &

args=(--headless=false --start-maximized --data-dir="$DATA_DIR")
if [ -n "${CLOAKROOM_FINGERPRINT_SEED:-}" ]; then
  args+=(--fingerprint="$CLOAKROOM_FINGERPRINT_SEED")
fi
if [ -n "${CLOAKROOM_PROXY:-}" ]; then
  args+=(--proxy-server="$CLOAKROOM_PROXY")
fi

exec cloakserve "${args[@]}" "$@"

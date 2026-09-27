#!/bin/bash
CLOAKROOM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CDP_PORT="${CLOAKROOM_CDP_PORT:-9222}"
VIEWER_PORT="${CLOAKROOM_VIEWER_PORT:-6080}"
CDP_URL="http://127.0.0.1:${CDP_PORT}"
VIEWER_URL="http://127.0.0.1:${VIEWER_PORT}"
STATE_DIR="${HOME}/.cloakroom"
SHARE_FILE="${STATE_DIR}/share.json"
SHARE_LOG="${STATE_DIR}/share.log"

case ":${PATH}:" in
  *":${HOME}/.orbstack/bin:"*) ;;
  *) export PATH="${HOME}/.orbstack/bin:${PATH}" ;;
esac

health() {
  docker inspect -f '{{.State.Health.Status}}' cloakroom 2>/dev/null || echo not_running
}

share_field() {
  sed -n "s/.*\"$1\": *\"\{0,1\}\([^\",}]*\).*/\1/p" "$SHARE_FILE"
}

active_share_url() {
  [ -f "$SHARE_FILE" ] || return 0
  if kill -0 "$(share_field pid)" 2>/dev/null; then
    share_field url
    return 0
  fi
  rm -f "$SHARE_FILE"
}

#!/bin/bash
CLOAKROOM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Ports: the environment wins, then .env (what docker compose uses), then the defaults.
env_setting() {
  [ -f "${CLOAKROOM_ROOT}/.env" ] || return 0
  sed -n "s/^[[:space:]]*$1=\([0-9][0-9]*\)[[:space:]]*$/\1/p" "${CLOAKROOM_ROOT}/.env" | tail -n 1
}
CDP_PORT="${CLOAKROOM_CDP_PORT:-$(env_setting CLOAKROOM_CDP_PORT)}"
CDP_PORT="${CDP_PORT:-9222}"
VIEWER_PORT="${CLOAKROOM_VIEWER_PORT:-$(env_setting CLOAKROOM_VIEWER_PORT)}"
VIEWER_PORT="${VIEWER_PORT:-6080}"
API_PORT="${CLOAKROOM_API_PORT:-$(env_setting CLOAKROOM_API_PORT)}"
API_PORT="${API_PORT:-8423}"
CDP_URL="http://127.0.0.1:${CDP_PORT}"
VIEWER_URL="http://127.0.0.1:${VIEWER_PORT}"
API_URL="http://127.0.0.1:${API_PORT}"
STATE_DIR="${HOME}/.cloakroom"
DATA_DIR="${CLOAKROOM_DATA_DIR:-${STATE_DIR}/data}"
SHARE_FILE="${STATE_DIR}/share.json"
SHARE_LOG="${STATE_DIR}/share.log"

# OrbStack's docker CLI and the installer's cloudflared live outside the default PATH.
for bin_dir in "${HOME}/.orbstack/bin" "${HOME}/.local/bin"; do
  case ":${PATH}:" in
    *":${bin_dir}:"*) ;;
    *) export PATH="${bin_dir}:${PATH}" ;;
  esac
done

# macOS only: OrbStack's Linux machines can see the Mac's /Applications too.
orbstack_app() {
  [ "$(uname -s)" = Darwin ] && { [ -d /Applications/OrbStack.app ] || [ -d "${HOME}/Applications/OrbStack.app" ]; }
}

# With OrbStack installed, Cloakroom uses its engine for its own commands only; the
# user's default Docker context (Docker Desktop, Colima...) is left alone.
if [ -z "${DOCKER_CONTEXT:-}" ] && [ -z "${DOCKER_HOST:-}" ] && orbstack_app; then
  export DOCKER_CONTEXT=orbstack
fi

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

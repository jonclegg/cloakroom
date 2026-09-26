#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -d "${HOME}/.orbstack/bin" ]; then
  case ":${PATH}:" in
    *":${HOME}/.orbstack/bin:"*) ;;
    *) export PATH="${HOME}/.orbstack/bin:${PATH}" ;;
  esac
fi

if { [ -d /Applications/OrbStack.app ] || [ -d "${HOME}/Applications/OrbStack.app" ]; } \
  && docker context inspect orbstack >/dev/null 2>&1; then
  docker context use orbstack >/dev/null
fi

if ! docker info >/dev/null 2>&1; then
  echo "The container engine is not running, so Cloakroom is already stopped."
  exit 0
fi

docker compose --profile examples down
echo
echo "Cloakroom stopped. Your browser profile is saved; ./cloakroom start brings it back."

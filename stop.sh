#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop is not running, so Cloakroom is already stopped."
  exit 0
fi

docker compose --profile examples down
echo
echo "Cloakroom stopped. Your browser profile is saved; ./start.sh brings it back."

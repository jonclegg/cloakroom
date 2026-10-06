#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

source ./lib.sh

if ! docker info >/dev/null 2>&1; then
  echo "The container engine is not running, so Cloakroom is already stopped."
  exit 0
fi

docker compose --profile examples down
echo
echo "Cloakroom stopped. Your browser profile is saved; ./cloakroom start brings it back."

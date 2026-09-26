#!/bin/bash
# Runs CloakBrowser's own stealth test suite in a throwaway container.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose run --rm --no-deps cloakroom cloaktest "$@"

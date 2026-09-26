#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

bold=$'\033[1m'; green=$'\033[32m'; red=$'\033[31m'; reset=$'\033[0m'

fail() {
  echo
  echo "${red}${bold}Problem:${reset} $1"
  echo
  exit 1
}

echo "${bold}Cloakroom${reset} - starting CloakBrowser"
echo

if ! command -v docker >/dev/null 2>&1; then
  fail "Docker is not installed.
Install Docker Desktop for Mac, open it once, then run ./start.sh again:
  https://www.docker.com/products/docker-desktop/"
fi

if ! docker info >/dev/null 2>&1; then
  fail "Docker Desktop is not running.
Open Docker Desktop (Applications > Docker), wait until it says \"Engine running\",
then run ./start.sh again."
fi

if ! docker compose version >/dev/null 2>&1; then
  fail "Your Docker is missing 'docker compose'. Update Docker Desktop to the latest version."
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env with default settings (edit it later to add a license key or proxy)."
fi

echo "1/3 Downloading the latest CloakBrowser image (first time can take a few minutes)..."
docker compose pull hello --quiet
docker compose build --pull --quiet cloakroom

echo "2/3 Starting the browser..."
docker compose up -d --force-recreate cloakroom

echo "3/3 Waiting for the browser to be ready..."
for _ in $(seq 1 90); do
  status="$(docker inspect -f '{{.State.Health.Status}}' cloakroom 2>/dev/null || echo missing)"
  [ "$status" = "healthy" ] && break
  sleep 2
done

if [ "$status" != "healthy" ]; then
  docker compose logs --tail 40 cloakroom
  fail "The browser did not become ready (status: $status). See the log above, or README > Troubleshooting."
fi

viewer_url="http://$(docker compose port cloakroom 6080)"
cdp_url="http://$(docker compose port cloakroom 9222)"

cat <<EOF

${green}${bold}You're ready!${reset}

  See the browser:    ${viewer_url}
  Try an example:     docker compose run --rm hello
  Stop everything:    ./stop.sh

  For scripts (Playwright, Puppeteer): ${cdp_url}
  Only this computer can connect. Your logins are kept between restarts.

EOF

if [ "$(uname)" = "Darwin" ]; then
  open "$viewer_url"
fi

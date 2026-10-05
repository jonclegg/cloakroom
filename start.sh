#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

bold=$'\033[1m'; green=$'\033[32m'; red=$'\033[31m'; reset=$'\033[0m'
CLOAKROOM_INSTALL_URL="https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh" # // pragma: allowlist secret

fail() {
  echo
  echo "${red}${bold}Problem:${reset} $1"
  echo
  exit 1
}

echo "${bold}Cloakroom${reset} - starting CloakBrowser"
echo

source ./lib.sh

open_orbstack() {
  if [ -d /Applications/OrbStack.app ]; then
    open /Applications/OrbStack.app || echo "Waiting for OrbStack to finish starting..."
    return
  fi
  open "${HOME}/Applications/OrbStack.app" || echo "Waiting for OrbStack to finish starting..."
}

dotenv_defines_tz() {
  [ -f .env ] || return 1
  grep -qE '^[[:space:]]*TZ=' .env
}

detect_host_timezone() {
  tz=""
  if command -v timedatectl >/dev/null 2>&1; then
    tz="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
  fi
  case "$tz" in
    ""|n/a) ;;
    *) printf '%s\n' "$tz"; return 0 ;;
  esac
  if [ -f /etc/timezone ]; then
    tz="$(tr -d '[:space:]' < /etc/timezone)"
    if [ -n "$tz" ]; then
      printf '%s\n' "$tz"
      return 0
    fi
  fi
  if [ -L /etc/localtime ]; then
    link="$(readlink /etc/localtime)"
    case "$link" in
      *zoneinfo/*)
        printf '%s\n' "${link#*zoneinfo/}"
        return 0
        ;;
    esac
  fi
  return 1
}

timezone_name_ok() {
  case "$1" in
    ""|*..*|*[!A-Za-z0-9_+/-]*) return 1 ;;
  esac
}

export_host_timezone() {
  if [ -n "${TZ:-}" ]; then
    return 0
  fi
  if dotenv_defines_tz; then
    return 0
  fi
  tz="$(detect_host_timezone || true)"
  if ! timezone_name_ok "$tz"; then
    return 0
  fi
  export TZ="$tz"
}

if orbstack_app; then
  if ! docker info >/dev/null 2>&1; then
    echo "Starting OrbStack..."
    open_orbstack
    orb_bin=""
    if [ -x /Applications/OrbStack.app/Contents/MacOS/bin/orb ]; then
      orb_bin="/Applications/OrbStack.app/Contents/MacOS/bin/orb"
    elif [ -x "${HOME}/Applications/OrbStack.app/Contents/MacOS/bin/orb" ]; then
      orb_bin="${HOME}/Applications/OrbStack.app/Contents/MacOS/bin/orb"
    fi
    if [ -n "$orb_bin" ]; then
      "$orb_bin" start >/dev/null 2>&1 || echo "Waiting for OrbStack to finish starting..."
    fi
    ready=""
    for _ in $(seq 1 120); do
      if docker info >/dev/null 2>&1; then
        ready=yes
        break
      fi
      sleep 2
    done
    if [ -z "${ready}" ]; then
      fail "OrbStack did not become ready.
Open OrbStack from Applications and finish its setup, then run this again.
  https://orbstack.dev/download"
    fi
  fi
  echo "Using OrbStack."
elif ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  if [ "$(uname)" = "Darwin" ]; then
    fail "OrbStack is not installed, and no container engine is running.
On a Mac, install Cloakroom with one command:
  curl -fsSL ${CLOAKROOM_INSTALL_URL} | sh
Or install OrbStack, open it, then run this again:
  https://orbstack.dev/download"
  fi
  fail "Docker Engine is not available.
Install Docker Engine, then make sure 'docker info' works for this user:
  https://docs.docker.com/engine/install/
If Docker is installed but 'docker info' fails, start it and join the docker group, then log in again:
  sudo systemctl enable --now docker
  sudo usermod -aG docker \"\$USER\""
fi

if ! docker compose version >/dev/null 2>&1; then
  if [ "$(uname)" = "Darwin" ]; then
    fail "This container engine is missing 'docker compose'. Update OrbStack or Docker Desktop (with Colima, set up Homebrew's docker-compose plugin), then run this again."
  fi
  fail "This container engine is missing 'docker compose'.
Install the Docker Compose plugin and run this again.
  https://docs.docker.com/compose/install/linux/"
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env with default settings (edit it later to add a license key or proxy)."
fi

export_host_timezone

echo "1/3 Downloading the latest CloakBrowser image (first time can take a few minutes)..."
docker compose pull hello --quiet
docker compose build --pull --quiet cloakroom

echo "2/3 Starting the browser..."
if ! up_log="$(docker compose up -d --force-recreate cloakroom 2>&1)"; then
  echo "$up_log"
  case "$up_log" in
    *"port is already allocated"*|*"address already in use"*|*"ports are not available"*)
      fail "Another program on this computer is already using port ${CDP_PORT} or ${VIEWER_PORT}.
Pick free ports in ${PWD}/.env, for example:
  CLOAKROOM_CDP_PORT=9333
  CLOAKROOM_VIEWER_PORT=6090
then run: cloakroom start"
      ;;
  esac
  fail "Docker could not start the browser. See the message above."
fi

echo "3/3 Waiting for the browser to be ready..."
for _ in $(seq 1 150); do
  status="$(docker inspect -f '{{.State.Health.Status}}' cloakroom 2>/dev/null || echo missing)"
  [ "$status" = "healthy" ] && break
  sleep 2
done

if [ "$status" != "healthy" ]; then
  docker compose logs --tail 40 cloakroom
  fail "The browser did not become ready (status: $status). See the log above, or skills/cloakroom/SKILL.md > Troubleshooting."
fi

viewer_url="http://$(docker compose port cloakroom 6080)"
cdp_url="http://$(docker compose port cloakroom 9222)"

cat <<EOF

${green}${bold}You're ready!${reset}

  See the browser:    ${viewer_url}
  Agents and scripts: ${cdp_url}   (Playwright, Puppeteer, or open this folder in your agent)
  Watch from a phone: cloakroom share
  Stop everything:    cloakroom stop

  Only this computer can connect. Your logins are kept between restarts.

EOF

if [ "$(uname)" = "Darwin" ]; then
  open "$viewer_url"
elif { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; } && command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$viewer_url" >/dev/null 2>&1 </dev/null &
fi

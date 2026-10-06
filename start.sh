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

add_orbstack_path() {
  case ":${PATH}:" in
    *":${HOME}/.orbstack/bin:"*) ;;
    *) export PATH="${HOME}/.orbstack/bin:${PATH}" ;;
  esac
}

add_orbstack_path

orbstack_app() {
  [ -d /Applications/OrbStack.app ] || [ -d "${HOME}/Applications/OrbStack.app" ]
}

open_orbstack() {
  if [ -d /Applications/OrbStack.app ]; then
    open /Applications/OrbStack.app || echo "Waiting for OrbStack to finish starting..."
    return
  fi
  open "${HOME}/Applications/OrbStack.app" || echo "Waiting for OrbStack to finish starting..."
}

if orbstack_app; then
  if ! docker --context orbstack info >/dev/null 2>&1; then
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
      add_orbstack_path
      if docker --context orbstack info >/dev/null 2>&1; then
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
  docker context use orbstack >/dev/null
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
    fail "This container engine is missing 'docker compose'. Update OrbStack and run this again."
  fi
  fail "This container engine is missing 'docker compose'.
Install the Docker Compose plugin and run this again.
  https://docs.docker.com/compose/install/linux/"
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env with default settings (edit it later to add a license key or proxy)."
fi

# A UTC clock on a US residential IP is a bot tell. The container has no timezone
# of its own, and cloakserve only derives one from GeoIP when a proxy is set, so
# the browser would otherwise report UTC while the traffic leaves from, say,
# America/Chicago. Match the host unless the user set one.
if ! grep -qE '^CLOAKROOM_TIMEZONE=..*' .env 2>/dev/null; then
  host_tz=""
  if [ -L /etc/localtime ]; then
    host_tz="$(readlink /etc/localtime | sed -n 's#.*/zoneinfo/##p')"
  fi
  [ -n "$host_tz" ] || host_tz="$(cat /etc/timezone 2>/dev/null || true)"
  if [ -n "$host_tz" ]; then
    if grep -qE '^CLOAKROOM_TIMEZONE=' .env 2>/dev/null; then
      sed -i.bak "s#^CLOAKROOM_TIMEZONE=.*#CLOAKROOM_TIMEZONE=${host_tz}#" .env && rm -f .env.bak
    else
      printf '\n# Detected from this computer so the browser clock matches the IP.\nCLOAKROOM_TIMEZONE=%s\n' "$host_tz" >> .env
    fi
    echo "Timezone: ${host_tz} (from this computer)"
  fi
fi

# The API writes notes, run logs and photos here. Create it as this user, so on
# Linux the bind mount is ours and the API runs as us rather than root.
mkdir -p "${CLOAKROOM_DATA_DIR:-${HOME}/.cloakroom/data}"

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
  fail "The browser did not become ready (status: $status). See the log above, or skills/cloakroom/SKILL.md > Troubleshooting."
fi

viewer_url="http://$(docker compose port cloakroom 6080)"
cdp_url="http://$(docker compose port cloakroom 9222)"
api_url="http://$(docker compose port cloakroom 8423)"

cat <<EOF

${green}${bold}You're ready!${reset}

  See the browser:    ${viewer_url}
  Agents and scripts: ${cdp_url}   (Playwright, Puppeteer, or open this folder in your agent)
  Chat with it:       ./cloakroom chat "<message>"   (API ${api_url})
  Watch from a phone: ./cloakroom share
  Stop everything:    ./cloakroom stop

  Only this computer can connect. Your logins are kept between restarts.

EOF

if [ "$(uname)" = "Darwin" ]; then
  open "$viewer_url"
elif { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; } && command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$viewer_url" >/dev/null 2>&1 </dev/null &
fi

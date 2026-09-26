#!/bin/sh
# One-step Mac install:
#   curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
set -eu

REPO_URL="https://github.com/jonclegg/cloakroom.git" # // pragma: allowlist secret
TARBALL_URL="https://github.com/jonclegg/cloakroom/archive/refs/heads/main.tar.gz" # // pragma: allowlist secret
INSTALL_DIR="${HOME}/.cloakroom/app"
ORBSTACK_DOWNLOAD="https://orbstack.dev/download"

fail() {
  printf '\nProblem: %s\n\n' "$1" >&2
  exit 1
}

orbstack_installed() {
  [ -d /Applications/OrbStack.app ] || [ -d "${HOME}/Applications/OrbStack.app" ]
}

have_brew() {
  if command -v brew >/dev/null 2>&1; then
    return 0
  fi
  if [ -x /opt/homebrew/bin/brew ]; then
    PATH="/opt/homebrew/bin:${PATH}"
    export PATH
    return 0
  fi
  if [ -x /usr/local/bin/brew ]; then
    PATH="/usr/local/bin:${PATH}"
    export PATH
    return 0
  fi
  return 1
}

ensure_orbstack() {
  if orbstack_installed; then
    echo "OrbStack is already installed."
    return
  fi
  echo "Cloakroom runs its browser in OrbStack, not Docker Desktop."
  if have_brew; then
    echo "Installing OrbStack with Homebrew..."
    brew install orbstack
    if orbstack_installed; then
      return
    fi
  fi
  cat <<EOF
Install OrbStack in one step, then this installer continues:

  ${ORBSTACK_DOWNLOAD}

  1. Download OrbStack
  2. Open the file and drag OrbStack to Applications
  3. Open OrbStack and finish its setup (it may ask for your Mac password)

EOF
  if ! open "${ORBSTACK_DOWNLOAD}"; then
    echo "Open this page in your browser: ${ORBSTACK_DOWNLOAD}"
  fi
  echo "Waiting for OrbStack to appear in Applications..."
  i=0
  while [ "$i" -lt 180 ]; do
    if orbstack_installed; then
      echo "OrbStack found."
      return
    fi
    i=$((i + 1))
    sleep 2
  done
  fail "OrbStack was not found. Download it from ${ORBSTACK_DOWNLOAD}, open the app, then run this installer again."
}

checkout_dir() {
  script_path="$0"
  case "$script_path" in
    /*) ;;
    *) script_path="$(pwd)/${script_path}" ;;
  esac
  if [ ! -f "$script_path" ]; then
    return 1
  fi
  dir="$(cd "$(dirname "$script_path")" && pwd)"
  if [ -f "${dir}/cloakroom" ] && [ -f "${dir}/docker-compose.yml" ]; then
    printf '%s\n' "$dir"
    return 0
  fi
  return 1
}

install_tree() {
  found="$(checkout_dir || true)"
  if [ -n "$found" ]; then
    INSTALL_DIR="$found"
    echo "Using Cloakroom at ${INSTALL_DIR}"
    return
  fi
  mkdir -p "${HOME}/.cloakroom"
  if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "Updating Cloakroom..."
    git -C "${INSTALL_DIR}" pull --ff-only origin main
    return
  fi
  if [ -d "${INSTALL_DIR}" ]; then
    rm -rf "${INSTALL_DIR}"
  fi
  echo "Downloading Cloakroom..."
  if command -v git >/dev/null 2>&1; then
    git clone --depth 1 --branch main "${REPO_URL}" "${INSTALL_DIR}"
    return
  fi
  tmp="$(mktemp -d)"
  curl -fsSL -o "${tmp}/cloakroom.tar.gz" "${TARBALL_URL}"
  tar -xzf "${tmp}/cloakroom.tar.gz" -C "${tmp}"
  mv "${tmp}/cloakroom-main" "${INSTALL_DIR}"
  rm -rf "${tmp}"
}

cloudflared_asset() {
  arch="$(uname -m)"
  case "$arch" in
    arm64) printf '%s\n' "cloudflared-darwin-arm64.tgz" ;;
    x86_64) printf '%s\n' "cloudflared-darwin-amd64.tgz" ;;
    *)
      fail "No cloudflared build for ${arch}. Download one from https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/"
      ;;
  esac
}

install_cloudflared_binary() {
  asset="$(cloudflared_asset)"
  url="https://github.com/cloudflare/cloudflared/releases/latest/download/${asset}"
  dest_dir="${HOME}/.local/bin"
  tmp="$(mktemp -d)"
  echo "Downloading cloudflared from Cloudflare..."
  echo "  ${url}"
  echo "  Docs: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/"
  curl -fsSL -o "${tmp}/cloudflared.tgz" "${url}"
  tar -xzf "${tmp}/cloudflared.tgz" -C "${tmp}"
  mkdir -p "${dest_dir}"
  mv "${tmp}/cloudflared" "${dest_dir}/cloudflared"
  chmod +x "${dest_dir}/cloudflared"
  rm -rf "${tmp}"
  PATH="${dest_dir}:${PATH}"
  export PATH
  echo "Installed cloudflared to ${dest_dir}/cloudflared"
}

ensure_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared is already installed."
    return
  fi
  if have_brew; then
    echo "Installing cloudflared with Homebrew..."
    if brew install cloudflared && command -v cloudflared >/dev/null 2>&1; then
      echo "cloudflared is installed."
      return
    fi
    echo "Homebrew did not provide cloudflared. Downloading the official binary."
  fi
  install_cloudflared_binary
}

link_cli() {
  target="${INSTALL_DIR}/cloakroom"
  chmod +x "${target}" "${INSTALL_DIR}/start.sh" "${INSTALL_DIR}/stop.sh" "${INSTALL_DIR}/install.sh"
  if ln -sf "${target}" /usr/local/bin/cloakroom 2>/dev/null; then
    echo "Installed cloakroom. Open a terminal and run: cloakroom"
    return
  fi
  mkdir -p "${HOME}/.local/bin"
  ln -sf "${target}" "${HOME}/.local/bin/cloakroom"
  line='export PATH="$HOME/.local/bin:$PATH"'
  for rc in "${HOME}/.zprofile" "${HOME}/.zshrc"; do
    if [ -f "$rc" ] && grep -qxF "$line" "$rc"; then
      continue
    fi
    printf '\n%s\n' "$line" >> "$rc"
  done
  export PATH="${HOME}/.local/bin:${PATH}"
  echo "Installed cloakroom to ${HOME}/.local/bin/cloakroom"
}

if [ "$(uname)" != "Darwin" ]; then
  fail "This installer is for a Mac. On Windows, use start.ps1 (see the README)."
fi

ensure_orbstack
ensure_cloudflared
install_tree
link_cli
echo "Starting Cloakroom..."
"${INSTALL_DIR}/cloakroom" start

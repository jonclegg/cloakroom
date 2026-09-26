import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import time

from cloakroom_cli import config
from cloakroom_cli import stack

URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com")
URL_TIMEOUT_SECONDS = 60
STOP_WAIT_SECONDS = 5
DOWNLOADS = "https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/"
MISSING_CLOUDFLARED = (
    "cloudflared is not installed.\n"
    "On a Mac with Homebrew: brew install cloudflared\n"
    f"Otherwise download it from {DOWNLOADS}\n"
    "Then run: cloakroom share"
)

###############################################################################

def cloudflared_bin():
    found = shutil.which("cloudflared")
    if found:
        return found
    candidates = (
        pathlib.Path.home() / ".local" / "bin" / "cloudflared",
        pathlib.Path("/opt/homebrew/bin/cloudflared"),
        pathlib.Path("/usr/local/bin/cloudflared"),
    )
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None

###############################################################################

def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True

###############################################################################

def read_state():
    if not config.SHARE_FILE.is_file():
        return None
    state = json.loads(config.SHARE_FILE.read_text())
    if pid_alive(state["pid"]):
        return state
    config.SHARE_FILE.unlink()
    return None

###############################################################################

def write_state(state):
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = config.SHARE_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state) + "\n")
    temporary.replace(config.SHARE_FILE)

###############################################################################

def active_url():
    state = read_state()
    if state is None:
        return None
    return state["url"]

###############################################################################

def stop_pid(pid):
    if not pid_alive(pid):
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + STOP_WAIT_SECONDS
    while time.time() < deadline and pid_alive(pid):
        time.sleep(0.1)
    if not pid_alive(pid):
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return

###############################################################################

def stop():
    state = read_state()
    if state is None:
        return False
    stop_pid(state["pid"])
    if config.SHARE_FILE.is_file():
        config.SHARE_FILE.unlink()
    return True

###############################################################################

def viewer_origin():
    if config.VIEWER_PORT == config.CDP_PORT:
        print(
            f"Refusing to share port {config.VIEWER_PORT}: that is the CDP port. Share the viewer only.",
            file=sys.stderr,
        )
        return None
    return config.VIEWER_URL

###############################################################################

def wait_for_url(proc):
    deadline = time.time() + URL_TIMEOUT_SECONDS
    while time.time() < deadline:
        text = config.SHARE_LOG.read_text(errors="replace")
        match = URL_RE.search(text)
        if match:
            return match.group(0)
        if proc.poll() is not None:
            print(f"cloudflared exited ({proc.returncode}).\n{text[-2000:]}", file=sys.stderr)
            return None
        time.sleep(0.25)
    text = config.SHARE_LOG.read_text(errors="replace")
    print(f"Timed out waiting for the share URL.\n{text[-2000:]}", file=sys.stderr)
    return None

###############################################################################

def launch(binary, origin):
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.SHARE_LOG, "wb") as log_file:
        proc = subprocess.Popen(
            [binary, "tunnel", "--no-autoupdate", "--url", origin],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    url = wait_for_url(proc)
    if not url:
        stop_pid(proc.pid)
        return None
    state = {"pid": proc.pid, "url": url, "viewer_local": origin}
    write_state(state)
    return state

###############################################################################

def start(emit):
    existing = read_state()
    if existing and existing["viewer_local"] == config.VIEWER_URL:
        existing["reused"] = True
        return existing
    if existing:
        stop()
    if stack.health() != "healthy":
        emit("starting", detail="Starting the browser.")
        stack.run_script("start.sh")
    binary = cloudflared_bin()
    if not binary:
        print(MISSING_CLOUDFLARED, file=sys.stderr)
        return None
    origin = viewer_origin()
    if origin is None:
        return None
    state = launch(binary, origin)
    if state is None:
        return None
    state["reused"] = False
    return state

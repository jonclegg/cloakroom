import json
import os
import pathlib
import subprocess
import urllib.request

from cloakroom_cli import config

###############################################################################

def docker_env():
    env = os.environ.copy()
    home_bin = str(pathlib.Path.home() / ".orbstack" / "bin")
    env["PATH"] = home_bin + os.pathsep + env.get("PATH", "")
    return env

###############################################################################

def run_script(name):
    subprocess.run(["bash", str(config.REPO_ROOT / name)], cwd=config.REPO_ROOT, check=True)

###############################################################################

def health():
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", config.CONTAINER_NAME],
        capture_output=True,
        text=True,
        env=docker_env(),
    )
    if result.returncode != 0:
        return "not_running"
    return result.stdout.strip()

###############################################################################

def docker_running():
    return subprocess.run(["docker", "info"], capture_output=True, env=docker_env()).returncode == 0

###############################################################################

def browser_version():
    with urllib.request.urlopen(f"{config.CDP_URL}/json/version", timeout=10) as resp:
        return json.load(resp)["Browser"]

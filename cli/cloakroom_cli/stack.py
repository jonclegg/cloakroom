import json
import shutil
import subprocess
import urllib.request

from cloakroom_cli import config

###############################################################################

def run_script(name):
    subprocess.run(["bash", str(config.REPO_ROOT / name)], cwd=config.REPO_ROOT, check=True)

###############################################################################

def health():
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", config.CONTAINER_NAME],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "not_running"
    return result.stdout.strip()

###############################################################################

def docker_running():
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0

###############################################################################

def browser_version():
    with urllib.request.urlopen(f"{config.CDP_URL}/json/version", timeout=10) as resp:
        return json.load(resp)["Browser"]

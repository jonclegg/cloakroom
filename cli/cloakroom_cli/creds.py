import json
import os
import subprocess
import sys

from cloakroom_cli import config

###############################################################################

def stored_email():
    if not config.AMAZON_EMAIL_FILE.exists():
        return None
    return json.loads(config.AMAZON_EMAIL_FILE.read_text())["email"]

###############################################################################

def keychain_password(email):
    if sys.platform != "darwin":
        return None
    result = subprocess.run(
        ["security", "find-generic-password", "-s", config.AMAZON_KEYCHAIN_SERVICE, "-a", email, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.rstrip("\n")

###############################################################################

def amazon():
    email = os.environ.get("CLOAKROOM_AMAZON_EMAIL") or stored_email()
    if not email:
        return None, None
    password = os.environ.get("CLOAKROOM_AMAZON_PASSWORD") or keychain_password(email)
    return email, password

###############################################################################

def save_amazon(email):
    config.STATE_DIR.mkdir(mode=0o700, exist_ok=True)
    # A trailing bare -w makes `security` prompt for the password, keeping it out of argv.
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", config.AMAZON_KEYCHAIN_SERVICE, "-a", email, "-w"],
        check=True,
    )
    config.AMAZON_EMAIL_FILE.write_text(json.dumps({"email": email}))

###############################################################################

def forget_amazon():
    email = stored_email()
    if not email:
        return
    subprocess.run(
        ["security", "delete-generic-password", "-s", config.AMAZON_KEYCHAIN_SERVICE, "-a", email],
        capture_output=True,
    )
    config.AMAZON_EMAIL_FILE.unlink()

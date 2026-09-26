import os
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CONTAINER_NAME = "cloakroom"

CDP_PORT = int(os.environ.get("CLOAKROOM_CDP_PORT", "9222"))
VIEWER_PORT = int(os.environ.get("CLOAKROOM_VIEWER_PORT", "6080"))
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
VIEWER_URL = f"http://127.0.0.1:{VIEWER_PORT}"

STATE_DIR = pathlib.Path.home() / ".cloakroom"
SHARE_FILE = STATE_DIR / "share.json"
SHARE_LOG = STATE_DIR / "share.log"
AMAZON_EMAIL_FILE = STATE_DIR / "amazon.json"
AMAZON_KEYCHAIN_SERVICE = "cloakroom-amazon"

AMAZON_HOME_URL = "https://www.amazon.com/"
AMAZON_SIGNIN_URL = (
    "https://www.amazon.com/ap/signin"
    "?openid.return_to=https%3A%2F%2Fwww.amazon.com%2F"
    "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
    "&openid.assoc_handle=usflex"
    "&openid.mode=checkid_setup"
    "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
    "&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
)

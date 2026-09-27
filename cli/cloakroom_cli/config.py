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

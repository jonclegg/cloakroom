import pathlib
import re
import shutil
import sqlite3
import sys
import tempfile
import time

from cloakroom_cli import config

MAC_EPOCH = 978307200
CODE_RE = re.compile(r"(?<![\d,/-])(?<!\d\.)(\d{4,8})(?![\d,/-]|\.\d)")
OTP_WORDS = ("otp", "code", "one-time", "one time", "verification", "verify", "passcode", "security")

QUERY = """
SELECT message.date, message.text, message.attributedBody
FROM message
WHERE message.is_from_me = 0 AND message.date > ?
ORDER BY message.date DESC
LIMIT 200
"""

###############################################################################

def now_mac_ns():
    return int((time.time() - MAC_EPOCH) * 1_000_000_000)

###############################################################################

def message_text(text, attributed_body):
    if text:
        return text
    if attributed_body:
        return attributed_body.decode("latin-1", "ignore")
    return ""

###############################################################################

def extract_code(text, service):
    low = text.lower()
    if service and service.lower() not in low:
        return None
    if not any(word in low for word in OTP_WORDS):
        return None
    match = CODE_RE.search(text)
    if not match:
        return None
    return match.group(1)

###############################################################################

def read_rows(db_path, since_mac_ns):
    with tempfile.TemporaryDirectory() as tmp:
        copy = pathlib.Path(tmp) / "chat.db"
        shutil.copy2(db_path, copy)
        for suffix in ("-wal", "-shm"):
            sidecar = pathlib.Path(str(db_path) + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, pathlib.Path(str(copy) + suffix))
        conn = sqlite3.connect(copy)
        rows = conn.execute(QUERY, (since_mac_ns,)).fetchall()
        conn.close()
    return rows

###############################################################################

def find_code(since_mac_ns, service, db_path=config.MESSAGES_DB):
    for _, text, attributed_body in read_rows(db_path, since_mac_ns):
        code = extract_code(message_text(text, attributed_body), service)
        if code:
            return code
    return None

###############################################################################

def wait_for_code(service, timeout, since_mac_ns=None, db_path=config.MESSAGES_DB, interval=2.0):
    since = since_mac_ns if since_mac_ns is not None else now_mac_ns()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = find_code(since, service, db_path)
        if code:
            return code
        time.sleep(interval)
    return None

###############################################################################

def check_access(db_path=config.MESSAGES_DB):
    if sys.platform != "darwin":
        return "mac_only"
    if not db_path.exists():
        return "missing"
    try:
        read_rows(db_path, now_mac_ns())
    except PermissionError:
        return "no_permission"
    except sqlite3.DatabaseError:
        return "no_permission"
    return "ok"

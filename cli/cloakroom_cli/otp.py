import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

###############################################################################

def parse_code(raw):
    text = raw.strip()
    if text.startswith("{"):
        data = json_object(text)
        if data is None or "code" not in data:
            return None
        text = str(data["code"]).strip()
    if text.isdigit() and 4 <= len(text) <= 8:
        return text
    return None

###############################################################################

def json_object(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None

###############################################################################

class Inbox:
    def __init__(self, preset=None):
        self._code = None
        if preset:
            self._code = parse_code(preset)
            if self._code is None:
                raise ValueError("--otp / CLOAKROOM_OTP must be 4-8 digits")
        self._lock = threading.Lock()
        self.submit_url = None
        self._server = None

    def start(self):
        inbox = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path.split("?", 1)[0] != "/otp":
                    self._reply(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode()
                code = parse_code(raw)
                if not code:
                    self._reply(400)
                    return
                inbox.submit(code)
                self._reply(204)

            def _reply(self, status):
                self.send_response(status)
                self.end_headers()

            def log_message(self, fmt, *args):
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = self._server.server_address[1]
        self.submit_url = f"http://127.0.0.1:{port}/otp"
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        threading.Thread(target=self._read_stdin, daemon=True).start()

    def submit(self, code):
        with self._lock:
            self._code = code

    def take(self):
        with self._lock:
            code = self._code
            self._code = None
            return code

    def _read_stdin(self):
        while True:
            line = sys.stdin.readline()
            if not line:
                return
            code = parse_code(line)
            if code:
                self.submit(code)

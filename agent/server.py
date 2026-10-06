"""Cloakroom's chat API. Runs inside the container, beside the browser.

    POST /v1/chat                    {"message": "...", "session": null, "max_steps": 40, "wait": true}
    GET  /v1/runs/{run}              status, reply, steps, files, cost
    POST /v1/runs/{run}/cancel
    GET  /v1/runs/{run}/files/{path} a file the run saved (photos)
    GET  /v1/runs/{run}/shots/{path} a step screenshot
    GET  /v1/notes                   sites with notes
    GET  /v1/notes/{site}            the notes and run log for one site
    GET  /v1/status
    GET  /v1/health                  no token; for the container health check

Every route but /v1/health needs `Authorization: Bearer <token>`; the token is
<data>/api-token, created on first start. A session is one browser tab and the
conversation in it. One browser has one mouse, so runs go through a single worker
thread, which is also the only thread that touches Playwright.
"""

from __future__ import annotations

import hmac
import json
import os
import queue
import secrets
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cloakroom_agent as agent  # noqa: E402
from notebook import Notebook  # noqa: E402

DATA_DIR = agent.DATA_DIR
HOST_DATA_DIR = os.environ.get("CLOAKROOM_HOST_DATA_DIR", "")
PORT = int(os.environ.get("CLOAKROOM_API_LISTEN_PORT", "8423"))
CDP_URL = os.environ.get("CDP_URL", "http://127.0.0.1:9222")
SESSION_IDLE_SECONDS = int(os.environ.get("CLOAKROOM_SESSION_IDLE_SECONDS", "1800"))
DEFAULT_MAX_STEPS = 40
MAX_STEPS_LIMIT = 200


def new_id(prefix):
    return f"{prefix}_{time.strftime('%Y%m%d-%H%M%S')}_{secrets.token_hex(3)}"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Session:
    def __init__(self):
        self.id = new_id("s")
        self.page = None
        self.conversation = []
        self.last_used = time.time()
        self.busy = False


class Run:
    def __init__(self, session, message, max_steps):
        self.id = new_id("r")
        self.session = session
        self.message = message
        self.max_steps = max_steps
        self.dir = os.path.join(DATA_DIR, "runs", self.id)
        self.status = "queued"
        self.reply = None
        self.turn = None
        self.final_url = None
        self.error = None
        self.started = now()
        self.finished = None
        self.cancel_requested = False
        self.done = threading.Event()

    def view(self, full=False):
        turn = self.turn
        files = []
        if turn:
            for path in turn.files:
                entry = {"path": path, "url": f"/v1/runs/{self.id}/files/{path}"}
                if HOST_DATA_DIR:
                    entry["host_path"] = os.path.join(HOST_DATA_DIR, "runs", self.id, "files", path)
                files.append(entry)
        out = {
            "run": self.id,
            "session": self.session.id,
            "status": self.status,
            "message": self.message,
            "reply": self.reply,
            "files": files,
            "host_dir": os.path.join(HOST_DATA_DIR, "runs", self.id) if HOST_DATA_DIR else None,
            "final_url": self.final_url,
            "steps": len(turn.steps) if turn else 0,
            "sites": turn.sites if turn else [],
            "blocks": turn.blocks_seen if turn else [],
            "memory": turn.memory if turn else [],
            "notes_written": turn.notes_written if turn else [],
            "cost_usd": round(turn.cost_usd, 5) if turn else 0.0,
            "started": self.started,
            "finished": self.finished,
            "error": self.error,
        }
        if full and turn:
            out["trace"] = turn.steps
        elif turn:
            out["trace"] = [
                f"[{step['step']}] {step.get('did', '')}"
                + (f" [bot check: {step['block_type']}]" if step.get("blocked") else "")
                for step in turn.steps
            ]
        return out

    def persist(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = os.path.join(self.dir, "run.json.tmp")
        with open(tmp, "w") as fh:
            json.dump(self.view(full=True), fh, indent=2)
        os.replace(tmp, os.path.join(self.dir, "run.json"))


class Cloakroom:
    """Sessions, the run queue, and the worker that drives the browser."""

    def __init__(self):
        self.notebook = Notebook(DATA_DIR)
        self.sessions = {}
        self.runs = {}
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        self.browser = None
        self.current = None

    # ---- called from HTTP threads

    def submit(self, message, session_id, max_steps):
        with self.lock:
            if session_id:
                session = self.sessions.get(session_id)
                if session is None:
                    raise LookupError(f"no session {session_id} (it may have expired)")
                if session.busy:
                    raise RuntimeError(f"session {session_id} is still working on a message")
            else:
                session = Session()
                self.sessions[session.id] = session
            session.busy = True
            session.last_used = time.time()
            run = Run(session, message, max_steps)
            self.runs[run.id] = run
        self.queue.put(run)
        return run

    def status(self):
        return {
            "browser_connected": bool(self.browser and self.browser.is_connected()),
            "model": agent.DEFAULT_MODEL,
            "openrouter_key": self._has_key(),
            "queue_depth": self.queue.qsize(),
            "running": self.current.id if self.current else None,
            "sessions": [
                {"session": session.id, "turns": len(session.conversation) // 2,
                 "idle_seconds": int(time.time() - session.last_used), "busy": session.busy}
                for session in self.sessions.values()
            ],
        }

    @staticmethod
    def _has_key():
        try:
            agent.api_key()
            return True
        except RuntimeError:
            return False

    # ---- the worker thread

    def work(self):
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        while True:
            run = self.queue.get()
            self.current = run
            try:
                self._run(playwright, run)
            except Exception as exc:  # noqa: BLE001 - the worker must outlive one bad run
                traceback.print_exc()
                run.status = "failed"
                run.error = f"{type(exc).__name__}: {exc}"
                run.reply = run.reply or f"Cloakroom hit an internal error: {exc}"
            finally:
                run.finished = now()
                run.session.busy = False
                run.session.last_used = time.time()
                run.persist()
                self.current = None
                run.done.set()

    def _connect(self, playwright):
        if self.browser is None or not self.browser.is_connected():
            self.browser = playwright.chromium.connect_over_cdp(CDP_URL)
            # Pages from an old connection are dead.
            for session in self.sessions.values():
                session.page = None
        return self.browser.contexts[0]

    def _expire_sessions(self):
        cutoff = time.time() - SESSION_IDLE_SECONDS
        with self.lock:
            stale = [s for s in self.sessions.values() if not s.busy and s.last_used < cutoff]
            for session in stale:
                del self.sessions[session.id]
        for session in stale:
            if session.page is not None and not session.page.is_closed():
                session.page.close()

    def _run(self, playwright, run):
        if run.cancel_requested:
            run.status = "cancelled"
            run.reply = "Cancelled before it started."
            return
        self._expire_sessions()
        context = self._connect(playwright)
        session = run.session
        if session.page is None or session.page.is_closed():
            session.page = context.new_page()
        page = session.page
        page.set_default_timeout(30000)
        page.bring_to_front()

        run.status = "running"
        turn = agent.Turn(run.id, run.message, list(session.conversation), self.notebook,
                          run.dir, run.max_steps, agent.DEFAULT_MODEL)
        turn.cancelled = run.cancel_requested
        run.turn = turn
        run.persist()

        status, reply, page = agent.run_turn(page, turn, lambda _turn: run.persist())
        session.page = page
        run.final_url = page.url
        try:
            agent.reflect(turn, status, reply)
        except RuntimeError as exc:
            print(f"reflect failed for {run.id}: {exc}", file=sys.stderr)

        run.status = status
        run.reply = reply
        session.conversation.append({"role": "caller", "text": run.message})
        session.conversation.append({"role": "cloakroom", "text": reply})

        entry = {
            "time": run.started, "run": run.id, "session": session.id,
            "message": run.message, "status": status, "reply": reply[:300],
            "steps": len(turn.steps), "cost_usd": round(turn.cost_usd, 5),
        }
        for site in turn.sites:
            blocks = sorted({b["type"] for b in turn.blocks_seen if b["site"] == site})
            self.notebook.log_run(site, {**entry, "blocks": blocks})
        with open(os.path.join(DATA_DIR, "runs.jsonl"), "a") as fh:
            fh.write(json.dumps({**entry, "sites": turn.sites}) + "\n")


def load_token():
    path = os.path.join(DATA_DIR, "api-token")
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_urlsafe(32) + "\n")
    with open(path) as fh:
        return fh.read().strip()


def make_handler(cloakroom, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "cloakroom"

        def log_message(self, fmt, *args):
            sys.stderr.write(f"api {self.address_string()} {fmt % args}\n")

        def _send(self, code, payload):
            body = json.dumps(payload, indent=2).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            given = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if hmac.compare_digest(given, token):
                return True
            self._send(401, {"error": "missing or wrong bearer token (see ~/.cloakroom/data/api-token)"})
            return False

        def _parts(self):
            return [unquote(part) for part in self.path.split("?")[0].strip("/").split("/")]

        def do_GET(self):  # noqa: N802
            parts = self._parts()
            if parts == ["v1", "health"]:
                return self._send(200, {"ok": True})
            if not self._authorized():
                return None
            if parts == ["v1", "status"]:
                return self._send(200, cloakroom.status())
            if parts == ["v1", "notes"]:
                return self._send(200, {"sites": cloakroom.notebook.sites(),
                                        "general": cloakroom.notebook.notes_for("general", 1000)})
            if len(parts) == 3 and parts[:2] == ["v1", "notes"]:
                site = parts[2]
                try:
                    return self._send(200, {"site": site,
                                            "notes": cloakroom.notebook.notes_for(site, 1000),
                                            "runs": cloakroom.notebook.runs_for(site, 1000)})
                except ValueError as exc:
                    return self._send(400, {"error": str(exc)})
            if len(parts) >= 3 and parts[:2] == ["v1", "runs"]:
                run = cloakroom.runs.get(parts[2])
                if len(parts) == 3:
                    if run is not None:
                        return self._send(200, run.view(full=True))
                    return self._send_saved_run(parts[2])
                if len(parts) >= 5 and parts[3] in ("files", "shots"):
                    return self._send_file(parts[2], parts[3], parts[4:])
            return self._send(404, {"error": "not found"})

        def _send_saved_run(self, run_id):
            path = os.path.join(DATA_DIR, "runs", os.path.basename(run_id), "run.json")
            if not os.path.exists(path):
                return self._send(404, {"error": f"no run {run_id}"})
            with open(path) as fh:
                return self._send(200, json.load(fh))

        def _send_file(self, run_id, kind, parts):
            base = os.path.realpath(os.path.join(DATA_DIR, "runs", os.path.basename(run_id), kind))
            path = os.path.realpath(os.path.join(base, *parts))
            if not path.startswith(base + os.sep) or not os.path.isfile(path):
                return self._send(404, {"error": "no such file"})
            ext = os.path.splitext(path)[1].lower()
            types = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
            with open(path, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", types.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return None

        def _json_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            return json.loads(self.rfile.read(length))

        def do_POST(self):  # noqa: N802
            if not self._authorized():
                return None
            parts = self._parts()
            if parts == ["v1", "chat"]:
                try:
                    body = self._json_body()
                except json.JSONDecodeError as exc:
                    return self._send(400, {"error": f"body is not JSON: {exc}"})
                message = (body.get("message") or "").strip()
                if not message:
                    return self._send(400, {"error": "message is required"})
                max_steps = min(int(body.get("max_steps") or DEFAULT_MAX_STEPS), MAX_STEPS_LIMIT)
                try:
                    run = cloakroom.submit(message, body.get("session"), max_steps)
                except LookupError as exc:
                    return self._send(404, {"error": str(exc)})
                except RuntimeError as exc:
                    return self._send(409, {"error": str(exc)})
                if body.get("wait", True) is False:
                    return self._send(202, run.view())
                run.done.wait()
                return self._send(200, run.view())
            if len(parts) == 4 and parts[:2] == ["v1", "runs"] and parts[3] == "cancel":
                run = cloakroom.runs.get(parts[2])
                if run is None:
                    return self._send(404, {"error": f"no run {parts[2]}"})
                run.cancel_requested = True
                if run.turn is not None:
                    run.turn.cancelled = True
                return self._send(200, {"run": run.id, "cancelling": run.status in ("queued", "running")})
            return self._send(404, {"error": "not found"})

    return Handler


def drop_privileges():
    """Run as the owner of the data directory, so files land owned by the host user.

    On Linux a bind mount keeps host uids: files the root-run container writes
    would be root's, and the host user could not read the token or the photos.
    """
    owner = os.stat(DATA_DIR)
    if os.getuid() != 0 or owner.st_uid == 0:
        return
    home = "/tmp/cloakroom-api"
    os.makedirs(home, exist_ok=True)
    os.chown(home, owner.st_uid, owner.st_gid)
    os.setgroups([])
    os.setgid(owner.st_gid)
    os.setuid(owner.st_uid)
    os.environ["HOME"] = home


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    drop_privileges()
    os.makedirs(os.path.join(DATA_DIR, "runs"), exist_ok=True)
    token = load_token()
    cloakroom = Cloakroom()
    threading.Thread(target=cloakroom.work, name="browser-worker", daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), make_handler(cloakroom, token))
    print(f"cloakroom api on :{PORT}, model {agent.DEFAULT_MODEL}, data {DATA_DIR}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

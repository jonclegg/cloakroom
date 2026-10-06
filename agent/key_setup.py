"""The OpenRouter key: a local page where the user pastes it, so it never goes
through an agent's chat.

`cloakroom key` asks the API for a one-time link (`/setup?code=...`, 15 minutes).
The user opens it in their own browser, or in Cloakroom's browser through the
viewer when they are away from the machine, and pastes the key. Cloakroom checks
it with OpenRouter and writes <data>/openrouter.key, mode 600. The model reads
that file on every call, so nothing restarts.

The page takes no bearer token (the user has none), so it is guarded instead:
the one-time code, and a Host header that must be localhost, which stops another
website in the user's browser from swapping in a key of its own.
"""

from __future__ import annotations

import html
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request

import cloakroom_agent as agent

CODE_SECONDS = 15 * 60
LOCAL_HOSTS = ("127.0.0.1", "localhost")


class SetupCodes:
    """One-time setup codes, and what happened to the latest one.

    `progress` lets the agent that sent the link tell "not opened yet" from
    "opened but not submitted", "rejected by OpenRouter" and "expired", without
    ever seeing the key: issued -> opened -> rejected (with the reason) | saved.
    """

    def __init__(self):
        self.codes = {}
        self.lock = threading.Lock()
        self.latest = None
        self.progress = None

    def issue(self):
        code = secrets.token_urlsafe(16)
        with self.lock:
            now = time.time()
            self.codes = {key: expiry for key, expiry in self.codes.items() if expiry > now}
            self.codes[code] = now + CODE_SECONDS
            self.latest = code
            self.progress = {"state": "issued", "expires_in_seconds": CODE_SECONDS}
        return code

    def note(self, code, state, error=None):
        """Record what happened to `code`, if it is the latest one."""
        with self.lock:
            if code == self.latest:
                self.progress = {"state": state, "error": error} if error else {"state": state}

    def status(self):
        with self.lock:
            if self.progress is None:
                return None
            progress = dict(self.progress)
            expiry = self.codes.get(self.latest)
            if progress["state"] != "saved":
                if expiry is None or expiry <= time.time():
                    progress["state"] = "expired"
                else:
                    progress["expires_in_seconds"] = int(expiry - time.time())
            return progress

    def valid(self, code):
        with self.lock:
            return bool(code) and self.codes.get(code, 0) > time.time()

    def consume(self, code):
        with self.lock:
            self.codes.pop(code, None)


def local_host(host_header):
    """True when the request was addressed to this machine by a loopback name."""
    host = (host_header or "").rsplit(":", 1)[0].strip("[]").lower()
    return host in LOCAL_HOSTS


def check_key(key):
    """Ask OpenRouter about the key. Returns its info, or raises ValueError."""
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response).get("data") or {}
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ValueError("OpenRouter does not recognise that key.") from exc
        raise ValueError(f"OpenRouter answered {exc.code}; try again in a moment.") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not reach OpenRouter to check the key: {exc.reason}") from exc


def save_key(key):
    tmp = agent.KEY_PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(key + "\n")
    os.replace(tmp, agent.KEY_PATH)


def describe(info):
    """One line about a checked key, without the key."""
    if info.get("limit") is None:
        return "This key has no credit limit set."
    return f"Credit left on this key: ${info.get('limit_remaining') or 0:,.2f} of ${info['limit']:,.2f}."


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cloakroom setup</title>
<style>
  :root {{ --bg: #f6f5f2; --card: #fff; --ink: #1d1d1b; --muted: #6b6a66; --line: #dddbd5;
          --accent: #2f5d50; --good: #2f6b3a; --bad: #9a2f2f; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #171716; --card: #222220; --ink: #ecebe6; --muted: #a3a29c; --line: #3a3936;
            --accent: #8cc2ae; --good: #8fcf98; --bad: #ec8f8f; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink);
         font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  main {{ max-width: 34rem; margin: 10vh auto; padding: 0 16px; }}
  .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 28px; }}
  h1 {{ font-size: 1.3rem; margin: 0 0 6px; }}
  p {{ margin: 0 0 14px; color: var(--muted); }}
  label {{ display: block; font-weight: 600; margin: 18px 0 6px; }}
  input {{ width: 100%; padding: 10px 12px; font: inherit; color: var(--ink); background: var(--bg);
          border: 1px solid var(--line); border-radius: 6px; }}
  button {{ margin-top: 16px; padding: 10px 18px; font: inherit; font-weight: 600; color: var(--card);
           background: var(--accent); border: 0; border-radius: 6px; cursor: pointer; }}
  .good {{ color: var(--good); }} .bad {{ color: var(--bad); }}
  a {{ color: var(--accent); }}
</style></head>
<body><main><div class="card">{body}</div></main></body></html>"""

FORM = """<h1>Cloakroom needs an OpenRouter key</h1>
<p>Cloakroom drives the browser with DeepSeek through OpenRouter. The key stays on this
machine, in <code>~/.cloakroom/data/openrouter.key</code>; your agent never sees it.</p>
<p>Create one at <a href="https://openrouter.ai/keys" target="_blank" rel="noopener">openrouter.ai/keys</a>.</p>
{message}
<form method="post" action="/setup">
  <input type="hidden" name="code" value="{code}">
  <label for="key">OpenRouter key</label>
  <input id="key" name="key" type="password" autocomplete="off" spellcheck="false"
         placeholder="sk-or-v1-..." required autofocus>
  <button type="submit">Check and save</button>
</form>"""

SAVED = """<h1 class="good">Key saved</h1>
<p>OpenRouter accepted it. {detail}</p>
<p>You can close this page and go back to your agent.</p>"""

EXPIRED = """<h1>This link has expired</h1>
<p>Setup links work once and last 15 minutes. Run <code>cloakroom key</code> for a new one.</p>"""


def form_page(code, error=None):
    message = f'<p class="bad">{html.escape(error)}</p>' if error else ""
    return PAGE.format(body=FORM.format(message=message, code=html.escape(code)))


def saved_page(info):
    return PAGE.format(body=SAVED.format(detail=html.escape(describe(info))))


def expired_page():
    return PAGE.format(body=EXPIRED)

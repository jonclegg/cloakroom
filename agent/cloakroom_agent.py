"""Cloakroom's embedded DeepSeek driver.

A caller chats with Cloakroom; each message becomes one turn. DeepSeek (via
OpenRouter) looks at the screen, picks the next browser action, and Cloakroom
executes it humanized, until DeepSeek replies to the caller.

Design notes
------------
* The screenshot is captured with `scale="css"`, so one screenshot pixel is one
  CSS pixel. The model is told the exact image size, so its coordinates are
  usable directly.
* Visible interactive elements are also read from the DOM and handed to the
  model as coordinate hints. That is what makes targeting reliable: on Walmart's
  PerimeterX press-and-hold the model picks the button centre to the pixel.
* Bot checks are detected from the DOM as well as by the model, and the model
  works them: press-and-hold and the like.
* The model keeps notes for itself. Within a turn, `remember` adds to a working
  memory that is always in the prompt (the step history is only a window). Across
  runs, `note` writes to a per-site notebook that is loaded whenever the browser
  is on that site again; see notebook.py.
* `deepseek/deepseek-v4.1-flash` is the default: of the DeepSeek models on
  OpenRouter only the Flash line accepts images, and on a grounding probe it was
  within 5 px of a button centre where `deepseek-v4-flash-vision-exp` was 25-65 px
  off, at a fifth of the price. Low reasoning effort keeps that accuracy; turning
  reasoning off loses it.
"""

from __future__ import annotations

import base64
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("CLOAKROOM_EXAMPLES", os.path.join(os.path.dirname(HERE), "examples")))

import bing_first  # noqa: E402
import humanize  # noqa: E402
import page_images  # noqa: E402

DEFAULT_MODEL = os.environ.get("CLOAKROOM_MODEL") or "deepseek/deepseek-v4.1-flash"
API = "https://openrouter.ai/api/v1/chat/completions"
DATA_DIR = os.environ.get("CLOAKROOM_DATA", "/data")

BLOCK_PATTERNS = {
    "press_and_hold": r"press\s*(&|and)\s*hold|activate and hold",
    "image_captcha": r"select all images|select each image|click all (images|squares)",
    "slider": r"slide to verify|drag the slider",
    "robot_or_human": r"robot or human",
    "access_denied": r"access denied|reference\s*#\s*\d",
    "blocked_url": r"/blocked|/sorry/|/challenge|/cdn-cgi/challenge",
}

# Vendor markers. Only *frame URLs* and real *widget elements* count: a normal
# page routinely mentions recaptcha or geetest inside its JS bundles, so matching
# raw page HTML produces false positives (Cars.com's homepage does exactly that).
# Kept for reference; visible widgets are what count.
VENDOR_FRAMES = {
    "cloudflare_turnstile": r"challenges\.cloudflare\.com",
    "recaptcha": r"google\.com/recaptcha|gstatic\.com/recaptcha",
    "hcaptcha": r"hcaptcha\.com",
    "perimeterx": r"px-cloud\.net|captcha\.px",
    "geetest": r"geetest\.com",
    "datadome": r"datadome\.co",
    "kasada": r"kasada",
}

VENDOR_WIDGETS = {
    "cloudflare_turnstile": "iframe[src*='challenges.cloudflare.com'], .cf-turnstile, #cf-chl-widget",
    "recaptcha": "iframe[src*='recaptcha'], .g-recaptcha, #recaptcha",
    "hcaptcha": "iframe[src*='hcaptcha'], .h-captcha",
    "perimeterx": "#px-captcha",
    "geetest": ".geetest_panel, .geetest_holder, [class*='geetest_']",
    "datadome": "#datadome-captcha, [class*='datadome']",
}

INTERSTITIAL_TEXT = (
    r"just a moment|checking your browser|enable javascript and cookies|"
    r"verifying you are human|verify you are human|attention required|"
    r"performing security verification|one more step|ddos protection by"
)

HINT_SELECTOR = (
    "button, a[href], input:not([type=hidden]), select, textarea, "
    "[role=button], [role=link], [id*=px], [id*=captcha]"
)

ACTION_SCHEMA = """Reply with ONLY a JSON object:
{"observation": "<one sentence: what is on screen>",
 "blocked": true|false,
 "block_type": "none"|"press_and_hold"|"image_captcha"|"slider"|"checkbox"|"login"|"other",
 "action": "click"|"type"|"press"|"hold"|"drag"|"scroll"|"wait"|"back"|"open"|"goto"|"read"|"save_images"|"reply",
 "x": <int px or null>, "y": <int px or null>,
 "x2": <int px or null>, "y2": <int px or null>,
 "text": "<text to type, key name, domain, url, folder name, or your reply; else null>",
 "amount": <int, only for scroll: pixels, positive is down>,
 "hold_ms": <int, only for hold>,
 "status": "done"|"needs_input"|"blocked"|"failed",  (only for reply)
 "remember": "<optional: a fact to add to your working memory for this message>",
 "note": {"site": "<domain or general>", "text": "<optional: a lesson for future runs>"},
 "reason": "<why>"}"""

READ_TEXT_LIMIT = 6000
READ_LINK_LIMIT = 60


# ---------------------------------------------------------------- OpenRouter

def api_key() -> str:
    """Key from the environment, or <data>/openrouter.key."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"].strip()
    path = os.path.join(DATA_DIR, "openrouter.key")
    if os.path.exists(path):
        with open(path) as fh:
            return fh.read().strip()
    raise RuntimeError(
        "No OpenRouter key. Set OPENROUTER_API_KEY in .env, or write it to "
        "~/.cloakroom/data/openrouter.key"
    )


def chat(messages, model, max_tokens=4000, temperature=0.1, json_mode=False):
    """One completion. Returns (content, cost in USD).

    DeepSeek's Flash models reason before answering; the reasoning counts against
    max_tokens, so a small budget returns an empty answer.
    """
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "reasoning": {"effort": "low"},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/jonclegg/cloakroom",
            "X-Title": "Cloakroom",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"OpenRouter {exc.code}: {exc.read().decode()[:500]}") from exc
    content = payload["choices"][0]["message"].get("content")
    if not content:
        raise RuntimeError(f"OpenRouter returned no content "
                           f"(finish_reason {payload['choices'][0].get('finish_reason')})")
    return content, float(payload.get("usage", {}).get("cost") or 0.0)


def _data_url(path):
    with open(path, "rb") as fh:
        blob = base64.b64encode(fh.read()).decode()
    return f"data:image/png;base64,{blob}"


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def site_of(url):
    """The domain a URL belongs to, for the notebook: host without www."""
    host = (urlparse(url or "").hostname or "").lower()
    return host.removeprefix("www.")


# ------------------------------------------------------------------ the page

def dom_hints(page, limit=40):
    """Visible interactive elements with page-relative CSS-pixel centres."""
    hints = []
    for frame in page.frames:
        try:
            els = frame.locator(HINT_SELECTOR)
            count = min(els.count(), limit)
        except Exception:  # noqa: BLE001
            continue
        for i in range(count):
            el = els.nth(i)
            try:
                if not el.is_visible():
                    continue
                box = el.bounding_box()
                if not box or box["width"] < 4 or box["height"] < 4:
                    continue
                hints.append({
                    "tag": el.evaluate("e => e.tagName.toLowerCase()"),
                    "text": (el.inner_text() or "").strip().replace("\n", " ")[:60],
                    "label": (el.get_attribute("aria-label")
                              or el.get_attribute("placeholder")
                              or el.get_attribute("id") or "")[:40],
                    "x": round(box["x"] + box["width"] / 2),
                    "y": round(box["y"] + box["height"] / 2),
                })
            except Exception:  # noqa: BLE001
                continue
    seen, out = set(), []
    for h in hints:
        key = (h["x"], h["y"], h["text"])
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out[:limit]


def safe_screenshot(page, path, timeout=15000):
    """Screenshot at CSS scale, falling back to raw CDP if Playwright hangs.

    Playwright's screenshot waits for fonts and can time out on a page that is
    still loading; the CDP call does not.
    """
    try:
        page.screenshot(path=path, scale="css", timeout=timeout)
        return True
    except Exception:  # noqa: BLE001
        pass
    try:
        session = page.context.new_cdp_session(page)
        result = session.send("Page.captureScreenshot", {"format": "png"})
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(result["data"]))
        return True
    except Exception:  # noqa: BLE001
        return False


def detect_block(page):
    """DOM-side block check, independent of the model.

    Challenge text and vendor widgets usually live in a cross-origin iframe, so
    scanning `body` alone misses them: Cloudflare's "Just a moment..." puts the
    wording in the <title>, not the body. This checks the title and body text,
    the URL, every frame's URL, and the real challenge widget elements.
    """
    url = (page.url or "").lower()
    found = []

    try:
        title = page.title() or ""
    except Exception:  # noqa: BLE001
        title = ""
    try:
        body = page.inner_text("body")
    except Exception:  # noqa: BLE001
        body = ""
    text = (title + "\n" + body).lower()

    # Cross-origin frames: their body text is worth reading too.
    frame_texts = []
    for frame in page.frames:
        try:
            loc = frame.locator("body")
            if loc.count():
                frame_texts.append(loc.inner_text() or "")
        except Exception:  # noqa: BLE001
            continue
    all_text = (text + "\n" + "\n".join(frame_texts)).lower()

    for name, pat in BLOCK_PATTERNS.items():
        if name == "blocked_url":
            if re.search(pat, url):
                found.append(name)
        elif re.search(pat, all_text):
            found.append(name)

    if re.search(INTERSTITIAL_TEXT, all_text):
        found.append("cloudflare_interstitial")
        found.append("blocked")

    # Only a *visible* vendor widget is a challenge. Cars.com ships a hidden
    # recaptcha iframe on its normal homepage; an invisible frame or a passive
    # v3 badge is not something the user has to solve.
    for name, sel in VENDOR_WIDGETS.items():
        for frame in page.frames:
            try:
                loc = frame.locator(sel)
                count = min(loc.count(), 4)
            except Exception:  # noqa: BLE001
                continue
            hit = False
            for i in range(count):
                try:
                    el = loc.nth(i)
                    if not el.is_visible():
                        continue
                    box = el.bounding_box()
                    if not box or box["width"] < 60 or box["height"] < 30:
                        continue
                    found.append(name)
                    hit = True
                    break
                except Exception:  # noqa: BLE001
                    continue
            if hit:
                break

    return sorted(set(found))


def read_page(page):
    """The page's visible text and links, for the model to read on its next step."""
    content = page.evaluate(
        """([textLimit, linkLimit]) => {
          const main = document.querySelector('main') || document.body;
          const text = (main.innerText || '').replace(/\\n{3,}/g, '\\n\\n').slice(0, textLimit);
          const seen = new Set();
          const links = [];
          for (const a of document.querySelectorAll('a[href]')) {
            const label = (a.innerText || a.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
            if (!label || seen.has(a.href) || !a.href.startsWith('http')) continue;
            seen.add(a.href);
            links.push(label.slice(0, 80) + ' -> ' + a.href);
            if (links.length >= linkLimit) break;
          }
          return {text, links};
        }""",
        [READ_TEXT_LIMIT, READ_LINK_LIMIT],
    )
    return content["text"] + "\n\nLinks:\n" + "\n".join(content["links"])


# ------------------------------------------------------------------ deciding

def _conversation_text(conversation):
    if not conversation:
        return "(this is the first message)"
    lines = []
    for entry in conversation[-10:]:
        speaker = "caller" if entry["role"] == "caller" else "you"
        lines.append(f"{speaker}: {entry['text']}")
    return "\n".join(lines)


def repeating(steps, count=3, tolerance=20):
    """True when the last `count` steps were the same action at the same spot and URL."""
    if len(steps) < count:
        return False
    last = steps[-count:]
    first = last[0]
    for step in last:
        if step.get("action") != first.get("action") or step.get("url") != first.get("url"):
            return False
        if step.get("text") != first.get("text"):
            return False
        for axis in ("x", "y"):
            if (step.get(axis) is None) != (first.get(axis) is None):
                return False
            if step.get(axis) is not None and abs(step[axis] - first[axis]) > tolerance:
                return False
    return first.get("action") not in ("wait", "scroll", "hold")


def decide(page, shot, turn, model):
    size = png_size(shot)
    dims = f"{size[0]}x{size[1]} pixels" if size else "unknown"
    try:
        vp = page.evaluate("({w: innerWidth, h: innerHeight, dpr: devicePixelRatio})")
    except Exception:  # noqa: BLE001 - page navigated mid-evaluate (challenges do)
        vp = {"w": 1280, "h": 720, "dpr": 1}
    hints = dom_hints(page)
    site = site_of(page.url)
    recent = [
        {key: step.get(key) for key in ("step", "url", "action", "text", "did")}
        for step in turn.steps[-8:]
    ]
    extra = ""
    if turn.steps and turn.steps[-1].get("action") == "read" and turn.last_read:
        extra = f"\nText of the page from your last `read`:\n{turn.last_read}\n"
    memory = "\n".join(f"- {item}" for item in turn.memory) or "(empty)"
    if repeating(turn.steps):
        extra += (
            "\nWARNING: your last three steps were the same action in the same place "
            "and the page did not move on. It is not working. Do something different: "
            "use `type` with x,y, press Enter, use `read` to find a link, or `goto`.\n"
        )
    prompt = (
        f"You are Cloakroom. You operate a real Chrome browser for a caller who "
        f"chats with you. Work through the caller's latest message one browser "
        f"action per step, then reply to them.\n\n"
        f"Conversation so far:\n{_conversation_text(turn.conversation)}\n\n"
        f"Caller's latest message: {turn.message}\n\n"
        f"Your notebook (lessons you wrote on earlier runs, and the run log):\n"
        f"{turn.notebook.context_for(site)}\n\n"
        f"Your working memory for this message:\n{memory}\n\n"
        f"Step {len(turn.steps) + 1} of at most {turn.max_steps}. "
        f"Your recent steps: {json.dumps(recent) if recent else 'none'}\n"
        f"{extra}\n"
        f"Current URL: {page.url}\n"
        f"The screenshot is exactly {dims}. The CSS viewport is "
        f"{vp['w']}x{vp['h']} at devicePixelRatio {vp['dpr']}. Screenshot pixels map "
        f"1:1 to CSS pixels, so give x,y in screenshot pixels.\n"
        f"Interactive elements found in the DOM, with centre coordinates already in "
        f"screenshot pixels (use these when they match what you see):\n"
        f"{json.dumps(hints, separators=(',', ':'))}\n\n"
        f"Actions:\n"
        f"- click x,y | type text (give x,y to click the field first) | press key | "
        f"scroll amount | hold x,y hold_ms | drag x,y to x2,y2 | wait | back\n"
        f"- open: enter a site you are not already on, by bare domain "
        f"(text \"walmart.com\"). It runs the vetted Bing-first path; do not drive Bing "
        f"by hand.\n"
        f"- goto: a URL on the site you are already on. Refused for other sites.\n"
        f"- read: get the page's text and links on your next step. Use it to read "
        f"details, prices, or listing URLs instead of guessing from the screenshot.\n"
        f"- save_images: download the photos of the item on this page into folder "
        f"`text` (for example \"car-1\"). Give x,y on the main photo when there is "
        f"one. Use it on a product or listing page.\n"
        f"- reply: send `text` to the caller and end this message. status \"done\" "
        f"when finished (include what they asked for), \"needs_input\" to ask them "
        f"something (a code, a choice), \"blocked\" for a bot check you cannot clear, "
        f"\"failed\" otherwise.\n"
        f"Keep notes for yourself. `remember` facts you will need later in this "
        f"message (listing URLs, prices, what you saved), because old steps scroll "
        f"out of view. Write a `note` when you learn something about a site that "
        f"would save time next run: an obstacle, what got past it, where things are.\n"
        f"If a bot check is on screen set blocked=true and name its block_type, then "
        f"work it with the right action:\n"
        f"- press_and_hold: action \"hold\" at the button centre, hold_ms at least 8000.\n"
        f"- slider: action \"drag\" from the handle to where the gap ends (x,y -> x2,y2).\n"
        f"- checkbox (\"I am not a robot\", Turnstile): action \"click\" on the checkbox.\n"
        f"- image_captcha: read the prompt, then \"click\" each matching tile centre in "
        f"turn, one action per step. If tiles are ambiguous, say so in `reason`.\n"
        f"When the check is gone, keep going.\n"
        f"Detected from the DOM right now: {turn.dom_blocks or 'no bot check'}\n"
        f"{ACTION_SCHEMA}"
    )
    raw, cost = chat(
        [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _data_url(shot)}},
        ]}],
        model=model,
        json_mode=True,
    )
    turn.cost_usd += cost
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"observation": raw[:300], "blocked": False, "action": "wait",
                "reason": "unparseable model output"}


# ------------------------------------------------------------------ actions

def do_hold(page, x, y, ms):
    """Press and hold. Returns the real elapsed milliseconds."""
    humanize.human_move(page, x, y)
    humanize.pause(0.15, 0.3)
    page.mouse.move(x, y)
    page.mouse.down()
    start = time.time()
    while (time.time() - start) * 1000 < ms:
        time.sleep(0.05)
    page.mouse.up()
    elapsed = int((time.time() - start) * 1000)
    humanize.pause(1.0, 1.8)
    return elapsed


def do_drag(page, x, y, x2, y2, ms=900):
    """Press at (x,y), drag to (x2,y2) with human-like easing, release.

    Slider challenges (Geetest, Alibaba, PerimeterX) score the path, not just the
    endpoints: a straight teleport is rejected. This eases in and out, overshoots
    slightly, then settles.
    """
    humanize.human_move(page, x, y)
    humanize.pause(0.12, 0.25)
    page.mouse.move(x, y)
    page.mouse.down()
    humanize.pause(0.05, 0.15)

    steps = random.randint(28, 45)
    overshoot = random.uniform(3, 9)
    for i in range(1, steps + 1):
        t = i / steps
        # ease-in-out
        eased = 3 * t * t - 2 * t * t * t
        px = x + (x2 - x) * eased
        py = y + (y2 - y) * eased
        if i == steps:
            px += overshoot
        px += random.uniform(-1.2, 1.2)
        py += random.uniform(-1.2, 1.2)
        page.mouse.move(px, py)
        time.sleep(random.uniform(0.008, 0.022))
    # settle back onto the target
    for settle in (0.6, 0.3, 0.1, 0.0):
        page.mouse.move(x2 + overshoot * settle, y2)
        time.sleep(random.uniform(0.03, 0.07))
    humanize.pause(0.1, 0.2)
    page.mouse.up()
    humanize.pause(1.0, 1.8)
    return f"drag ({x},{y})->({x2},{y2})"


def execute(page, d, turn):
    """Run one action. Returns (log line, the page to drive next)."""
    action = (d.get("action") or "wait").lower()
    x, y, text = d.get("x"), d.get("y"), d.get("text")
    x2, y2 = d.get("x2"), d.get("y2")

    if action == "drag":
        if None in (x, y, x2, y2):
            return "drag without both start and end coordinates", page
        return do_drag(page, x, y, x2, y2), page

    if action == "hold":
        if x is None or y is None:
            return "hold without coordinates", page
        ms = int(d.get("hold_ms") or 8000)
        held = do_hold(page, x, y, ms)
        return f"hold ({x},{y}) {held}ms", page

    if action == "click" and x is not None and y is not None:
        before = set(page.context.pages)
        humanize.human_move(page, x, y)
        humanize.pause(0.08, 0.22)
        page.mouse.click(x, y)
        humanize.pause(0.6, 1.2)
        opened = [item for item in page.context.pages if item not in before]
        if opened:
            opened[-1].wait_for_load_state("domcontentloaded")
            return f"click ({x},{y}) opened a new tab", opened[-1]
        return f"click ({x},{y})", page

    if action == "type" and text:
        if x is not None and y is not None:
            humanize.human_move(page, x, y)
            page.mouse.click(x, y)
            humanize.pause(0.2, 0.4)
        humanize.human_type(page, text)
        humanize.pause(0.3, 0.7)
        return f"type {text!r}", page

    if action == "press" and text:
        page.keyboard.press(text)
        humanize.pause(0.6, 1.2)
        return f"press {text}", page

    if action == "scroll":
        amount = int(d.get("amount") or 600)
        page.mouse.wheel(0, amount)
        humanize.pause(0.6, 1.2)
        return f"scroll {amount}", page

    if action == "back":
        page.go_back(wait_until="domcontentloaded")
        humanize.pause(0.8, 1.6)
        return "back", page

    if action == "open" and text:
        landed = bing_first.open_via_bing(page, text.strip())
        return f"open {text} -> {landed.url[:80]}", landed

    if action == "goto" and text:
        if site_of(text) != site_of(page.url):
            return (f"goto refused: {site_of(text)} is not the site you are on; "
                    f"enter it with open first"), page
        page.goto(text, wait_until="domcontentloaded")
        humanize.pause(0.8, 1.6)
        return f"goto {text}", page

    if action == "read":
        turn.last_read = read_page(page)
        return f"read {len(turn.last_read)} characters", page

    if action == "save_images":
        folder = page_images.safe_folder(text or f"page-{len(turn.steps)}")
        saved = page_images.save_images(page, os.path.join(turn.files_dir, folder), x, y)
        turn.files.extend(os.path.join(folder, name) for name in saved)
        return f"saved {len(saved)} images to {folder}/", page

    humanize.pause(1.0, 1.8)
    return "wait", page


# -------------------------------------------------------------------- loop

class Turn:
    """One caller message being worked: its steps, notes, files and cost."""

    def __init__(self, run_id, message, conversation, notebook, run_dir, max_steps, model):
        self.run_id = run_id
        self.message = message
        self.conversation = conversation
        self.notebook = notebook
        self.run_dir = run_dir
        self.shots_dir = os.path.join(run_dir, "shots")
        self.files_dir = os.path.join(run_dir, "files")
        self.max_steps = max_steps
        self.model = model
        self.steps = []
        self.memory = []
        self.files = []
        self.notes_written = []
        self.sites = []
        self.blocks_seen = []
        self.dom_blocks = []
        self.last_read = ""
        self.cost_usd = 0.0
        self.cancelled = False
        os.makedirs(self.shots_dir, exist_ok=True)
        os.makedirs(self.files_dir, exist_ok=True)

    def write_note(self, note, page_url):
        if not isinstance(note, dict) or not (note.get("text") or "").strip():
            return
        site = (note.get("site") or site_of(page_url) or "general").strip().lower()
        if site != "general":
            site = site_of(site if "://" in site else "https://" + site)
        self.notebook.add_note(site, note["text"].strip(), self.run_id)
        self.notes_written.append({"site": site, "text": note["text"].strip()})


def run_turn(page, turn, on_step):
    """Work one caller message until the model replies, the step limit, or cancel.

    Returns (status, reply, page). `on_step` is called after every step so the
    caller can publish progress.
    """
    failures = 0
    for step in range(turn.max_steps):
        if turn.cancelled:
            return "cancelled", "Cancelled by the caller.", page
        shot = os.path.join(turn.shots_dir, f"step-{step:02d}.png")
        if not safe_screenshot(page, shot):
            # A challenge that is mid-navigation destroys the page context. A
            # PerimeterX overlay in particular can navigate as it arms, and a
            # single retry is not enough: aborting here meant the hold never ran
            # and a beatable challenge was recorded as a failure. Keep trying.
            for wait in (2.5, 4.0, 6.0, 8.0):
                humanize.pause(wait, wait + 1.5)
                if safe_screenshot(page, shot):
                    break
            else:
                return "failed", "I could not take a screenshot of the page.", page

        try:
            turn.dom_blocks = detect_block(page)
        except Exception:  # noqa: BLE001
            turn.dom_blocks = []

        try:
            decision = decide(page, shot, turn, turn.model)
        except RuntimeError as exc:
            failures += 1
            turn.steps.append({"step": step, "url": page.url, "did": f"decide failed: {str(exc)[:200]}"})
            on_step(turn)
            if failures >= 3:
                return "failed", f"The model call kept failing: {str(exc)[:200]}", page
            humanize.pause(1.5, 2.5)
            continue
        failures = 0

        url = page.url
        site = site_of(url)
        if site and site not in turn.sites:
            turn.sites.append(site)
        blocked = bool(decision.get("blocked")) or bool(turn.dom_blocks)
        block_type = decision.get("block_type") or "none"
        if block_type == "none" and turn.dom_blocks:
            block_type = turn.dom_blocks[0]
        if blocked and block_type != "none":
            turn.blocks_seen.append({"site": site, "type": block_type, "step": step})

        if decision.get("remember"):
            turn.memory.append(str(decision["remember"]).strip())
        turn.write_note(decision.get("note"), url)

        record = {
            "step": step,
            "url": url,
            "observation": decision.get("observation"),
            "action": decision.get("action"),
            "x": decision.get("x"),
            "y": decision.get("y"),
            "text": decision.get("text"),
            "blocked": blocked,
            "block_type": block_type,
            "dom_blocks": turn.dom_blocks,
            "reason": decision.get("reason"),
            "screenshot": os.path.relpath(shot, turn.run_dir),
        }

        if (decision.get("action") or "").lower() == "reply":
            status = decision.get("status") or "done"
            if status not in ("done", "needs_input", "blocked", "failed"):
                status = "done"
            record["did"] = f"reply ({status})"
            turn.steps.append(record)
            on_step(turn)
            return status, decision.get("text") or "", page

        try:
            record["did"], page = execute(page, decision, turn)
        except Exception as exc:  # noqa: BLE001 - one bad action should not end the turn
            record["did"] = f"action failed: {str(exc)[:200]}"
        turn.steps.append(record)
        on_step(turn)
    return "step_limit", f"I ran out of steps ({turn.max_steps}) before finishing.", page


def reflect(turn, status, reply):
    """After a turn that hit trouble, ask the model what to remember next time.

    The model writes notes as it goes, but under pressure it often does not. One
    text-only call at the end turns the step log into a lesson per site. Runs that
    went smoothly are skipped: there is nothing to learn and it saves a call.
    """
    trouble = status != "done" or turn.blocks_seen or any(
        "failed" in (step.get("did") or "") or "refused" in (step.get("did") or "")
        for step in turn.steps
    )
    if not trouble or not turn.sites:
        return
    log = [
        {key: step.get(key) for key in ("step", "url", "observation", "did", "block_type")}
        for step in turn.steps
    ]
    existing = "\n\n".join(f"{site}:\n{turn.notebook.notes_for(site)}" for site in turn.sites)
    prompt = (
        f"You are Cloakroom reviewing your own browser run, to keep notes for next "
        f"time.\nCaller's message: {turn.message}\nOutcome: {status}: {reply}\n"
        f"Steps:\n{json.dumps(log)}\n\nNotes you already have:\n{existing or '(none)'}\n\n"
        f"Write only lessons that are new and would save time on a future run: a bot "
        f"check and what cleared it (or that nothing did), a page that misbehaved, "
        f"where a feature lives on the site. One short sentence each. Return "
        f'{{"notes": [{{"site": "<domain>", "text": "..."}}]}}, or {{"notes": []}} '
        f"if there is nothing new."
    )
    raw, cost = chat([{"role": "user", "content": prompt}], model=turn.model, json_mode=True)
    turn.cost_usd += cost
    for note in json.loads(raw).get("notes") or []:
        turn.write_note(note, "")

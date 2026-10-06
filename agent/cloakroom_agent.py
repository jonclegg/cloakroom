"""Cloakroom's embedded DeepSeek driver.

The agent hands Cloakroom one top-level goal; DeepSeek (via OpenRouter) looks at
the screen, picks the next browser action, and Cloakroom executes it humanized.

    cloakroom do "find a 12-cup coffee maker on walmart.com and open it"

Design notes
------------
* The screenshot is captured with `scale="css"`, so one screenshot pixel is one
  CSS pixel. The model is told the exact image size, so its coordinates are
  usable directly.
* Visible interactive elements are also read from the DOM and handed to the
  model as coordinate hints. That is what makes targeting reliable: on Walmart's
  PerimeterX press-and-hold the model picks the button centre to the pixel.
* Bot checks are reported in the step output and in `--json` (`blocked`,
  `block_type`), and the model works them: press-and-hold and the like.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "examples"))

import humanize  # noqa: E402

DEFAULT_MODEL = os.environ.get("CLOAKROOM_MODEL", "deepseek/deepseek-v4-flash-vision-exp")
API = "https://openrouter.ai/api/v1/chat/completions"
CDP_URL = os.environ.get("CDP_URL", "http://127.0.0.1:9222")

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
 "action": "click"|"type"|"press"|"hold"|"drag"|"scroll"|"wait"|"open"|"goto"|"done",
 "x": <int px or null>, "y": <int px or null>,
 "x2": <int px or null>, "y2": <int px or null>,
 "text": "<text to type, key name, domain to open, or url; else null>",
 "hold_ms": <int, only for hold>,
 "reason": "<why>"}"""


# ---------------------------------------------------------------- OpenRouter

def api_key() -> str:
    """Key from the environment, the repo .env, or ~/.cloakroom/.openrouter.key."""
    for name in ("OPENROUTER_API_KEY", "CLOAKROOM_OPENROUTER_KEY"):
        if os.environ.get(name):
            return os.environ[name].strip()
    env_file = os.path.join(ROOT, ".env")
    if os.path.exists(env_file):
        with open(env_file) as fh:
            for line in fh:
                if line.strip().startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    fallback = os.path.expanduser("~/.cloakroom/.openrouter.key")
    if os.path.exists(fallback):
        with open(fallback) as fh:
            return fh.read().strip()
    raise SystemExit(
        "No OpenRouter key. Set OPENROUTER_API_KEY, add it to .env, or write it to "
        "~/.cloakroom/.openrouter.key"
    )


def chat(messages, model, max_tokens=1200, temperature=0.1, json_mode=False):
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
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
        raise SystemExit(f"OpenRouter {exc.code}: {exc.read().decode()[:500]}") from exc
    return payload["choices"][0]["message"]["content"]


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
    import re

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
    frame_urls = []
    for frame in page.frames:
        try:
            frame_urls.append(frame.url or "")
        except Exception:  # noqa: BLE001
            pass
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


def decide(page, shot, goal, history, model):
    size = png_size(shot)
    dims = f"{size[0]}x{size[1]} pixels" if size else "unknown"
    try:
        vp = page.evaluate("({w: innerWidth, h: innerHeight, dpr: devicePixelRatio})")
    except Exception:  # noqa: BLE001 - page navigated mid-evaluate (challenges do)
        vp = {"w": 1280, "h": 720, "dpr": 1}
    hints = dom_hints(page)
    prompt = (
        f"You are operating a real Chrome browser. Goal: {goal}\n"
        f"The screenshot is exactly {dims}. The CSS viewport is "
        f"{vp['w']}x{vp['h']} at devicePixelRatio {vp['dpr']}. Screenshot pixels map "
        f"1:1 to CSS pixels, so give x,y in screenshot pixels.\n"
        f"Recent actions: {json.dumps(history[-6:]) if history else 'none'}\n"
        f"Interactive elements found in the DOM, with centre coordinates already in "
        f"screenshot pixels (use these when they match what you see):\n"
        f"{json.dumps(hints, separators=(',', ':'))}\n"
        f"To enter a site you are not already on, use action \"open\" with the bare "
        f"domain (for example {{\"action\":\"open\",\"text\":\"walmart.com\"}}). It runs "
        f"the vetted Bing-first path for you; do not drive Bing by hand and never open "
        f"a deep URL. "
        f"If a bot check is on screen set blocked=true and name its block_type, then "
        f"work it with the right action:\n"
        f"- press_and_hold: action \"hold\" at the button centre, hold_ms at least 8000.\n"
        f"- slider: action \"drag\" from the handle to where the gap ends (x,y -> x2,y2).\n"
        f"- checkbox (\"I am not a robot\", Turnstile): action \"click\" on the checkbox.\n"
        f"- image_captcha: read the prompt, then \"click\" each matching tile centre in "
        f"turn, one action per step. If tiles are ambiguous, say so in `reason`.\n"
        f"When the check is gone, keep going with the goal.\n"
        f"{ACTION_SCHEMA}"
    )
    raw = chat(
        [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _data_url(shot)}},
        ]}],
        model=model,
        json_mode=True,
    )
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


def execute(page, d, page_factory):
    action = (d.get("action") or "wait").lower()
    x, y, text = d.get("x"), d.get("y"), d.get("text")
    x2, y2 = d.get("x2"), d.get("y2")

    if action == "done":
        return "done", None

    if action == "drag":
        if None in (x, y, x2, y2):
            return "drag without both start and end coordinates", None
        return do_drag(page, x, y, x2, y2), None

    if action == "hold":
        if x is None or y is None:
            return "hold without coordinates", None
        ms = int(d.get("hold_ms") or 8000)
        held = do_hold(page, x, y, ms)
        return f"hold ({x},{y}) {held}ms", None

    if action == "click" and x is not None and y is not None:
        humanize.human_move(page, x, y)
        humanize.pause(0.08, 0.22)
        page.mouse.click(x, y)
        humanize.pause(0.6, 1.2)
        return f"click ({x},{y})", None

    if action == "type" and text:
        if x is not None and y is not None:
            humanize.human_move(page, x, y)
            page.mouse.click(x, y)
            humanize.pause(0.2, 0.4)
        humanize.human_type(page, text)
        humanize.pause(0.3, 0.7)
        return f"type {text!r}", None

    if action == "press" and text:
        page.keyboard.press(text)
        humanize.pause(0.6, 1.2)
        return f"press {text}", None

    if action == "scroll":
        page.mouse.wheel(0, int(d.get("amount") or 600))
        humanize.pause(0.6, 1.2)
        return "scroll", None

    if action == "open" and text:
        import bing_first

        before = set(page.context.pages)
        try:
            landed = bing_first.open_via_bing(page, text.strip())
        except Exception as exc:  # noqa: BLE001
            return f"open {text} failed: {str(exc)[:120]}", None
        for opened in page.context.pages:
            if opened not in before:
                page_factory[0] = opened
                break
        return f"open {text} -> {landed.url[:60]}", landed

    if action == "goto" and text:
        page.goto(text, wait_until="domcontentloaded")
        humanize.pause(0.8, 1.6)
        return f"goto {text}", None

    humanize.pause(1.0, 1.8)
    return "wait", None


# -------------------------------------------------------------------- loop

def run(page, goal, model, max_steps, shots_dir):
    history = []
    for step in range(max_steps):
        shot = os.path.join(shots_dir, f"step-{step:02d}.png")
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
                return history, "screenshot failed", page

        try:
            decision = decide(page, shot, goal, history, model)
        except Exception as exc:  # noqa: BLE001
            history.append({"step": step, "did": f"decide failed: {str(exc)[:120]}"})
            humanize.pause(1.5, 2.5)
            continue

        try:
            dom_blocks = detect_block(page)
        except Exception:  # noqa: BLE001
            dom_blocks = []

        try:
            url = page.url
        except Exception:  # noqa: BLE001
            url = "?"
        try:
            title = (page.title() or "")[:120]
        except Exception:  # noqa: BLE001
            title = ""

        record = {
            "step": step,
            "url": url,
            "title": title,
            "observation": decision.get("observation"),
            "action": decision.get("action"),
            "x": decision.get("x"),
            "y": decision.get("y"),
            "text": decision.get("text"),
            "hold_ms": decision.get("hold_ms"),
            "blocked": bool(decision.get("blocked")) or bool(dom_blocks),
            "block_type": decision.get("block_type") or (dom_blocks[0] if dom_blocks else "none"),
            "dom_blocks": dom_blocks,
            "reason": decision.get("reason"),
            "screenshot": shot,
        }

        if decision.get("action") == "done":
            history.append(record)
            return history, None, page

        page_factory = [page]
        try:
            log, landed = execute(page, decision, page_factory)
        except Exception as exc:  # noqa: BLE001
            log, landed = f"action failed: {str(exc)[:120]}", None
        record["did"] = log
        history.append(record)
        if landed is not None:
            page = page_factory[0]
    return history, "step limit reached", page


def pick_tab(ctx, want=None):
    """Choose the tab to drive.

    Explicit `want` (index or URL substring) wins. Otherwise prefer a tab that is
    currently showing a bot check, then the newest real http(s) tab that is not
    Bing, then whatever exists.
    """
    pages = list(ctx.pages)
    if not pages:
        return ctx.new_page()
    if want:
        if want.isdigit() and int(want) < len(pages):
            return pages[int(want)]
        for p in pages:
            if want.lower() in (p.url or "").lower():
                return p
        raise SystemExit(f"no tab matches {want!r}")
    for p in pages:
        if detect_block(p):
            return p
    for p in reversed(pages):
        url = p.url or ""
        if url.startswith("http") and "bing.com" not in url:
            return p
    return pages[-1]


def main():
    ap = argparse.ArgumentParser(prog="cloakroom do", description=__doc__)
    ap.add_argument("goal", help="what to do, in plain language")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-steps", type=int, default=15)
    ap.add_argument("--tab", default=None,
                    help="tab index or URL substring to drive (default: the best guess)")
    ap.add_argument("--shots", default=os.path.expanduser("~/.cloakroom/shots"),
                    help="where to write step screenshots")
    args = ap.parse_args()

    os.makedirs(args.shots, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        page = pick_tab(ctx, args.tab)
        page.set_default_timeout(30000)
        try:
            page.bring_to_front()
        except Exception:  # noqa: BLE001
            pass

        history, error, page = run(page, args.goal, args.model, args.max_steps,
                                   args.shots)

        if args.json:
            print(json.dumps({"goal": args.goal, "steps": history,
                              "final_url": page.url, "error": error}, indent=2))
        else:
            for r in history:
                flag = ""
                if r["blocked"] and r["block_type"] != "none":
                    flag = f" [BLOCKED:{r['block_type']}]"
                print(f"[{r['step']}] {r['url'][:80]}{flag}")
                print(f"     {r['observation']}")
                print(f"     -> {r.get('did', r['action'])}")
            if error:
                print(f"stopped: {error}")
            print(f"final: {page.url}")
        if error and error != "step limit reached":
            raise SystemExit(1)


if __name__ == "__main__":
    main()

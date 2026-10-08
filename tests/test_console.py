"""End-to-end tests for the Cloakroom console, through the Cloudflare share link.

They drive a separate headless Chromium (the host's Playwright) against a running
Cloakroom, the way a user on another machine would: every page load goes through
the share tunnel. Runs use the real model, so they cost a few cents and take
several minutes.

    pip install pytest playwright && playwright install chromium
    pytest tests/test_console.py

Cloakroom must be running with an OpenRouter key and a console password, and
CLOAKROOM_CONSOLE_PASSWORD must hold that password. The tests sign in with it
(one wrong try too, never enough to lock sign-in) and sign out only the devices
they signed in. They start a share (`cloakroom share --json`), and the last one
stops and restarts it, which signs out the devices that used the old link.

Every trycloudflare.com name is served from the same Cloudflare addresses, so the
test browser resolves them through public DNS: a resolver that was asked about a
new name too early (macOS caches the "no such name" for a while) would otherwise
fail tests that have nothing to do with Cloakroom.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_SECONDS = 240
RUN_TIMEOUT = RUN_SECONDS * 1000
PASSWORD = os.environ.get("CLOAKROOM_CONSOLE_PASSWORD", "")


def cloakroom(*args):
    result = subprocess.run([os.path.join(ROOT, "cloakroom"), *args], capture_output=True, text=True, check=True)
    return result.stdout


def share_link():
    lines = [line for line in cloakroom("share", "--json").splitlines() if line.startswith("{")]
    return json.loads(lines[-1])["url"]


def sign_in(page, url):
    """Open a console link and sign in; the page ends on the console, live."""
    page.goto(url)
    page.get_by_label("Console password").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_test_id("events-state")).to_have_text("Live updates on", timeout=30000)


def cloudflare_address():
    answer = subprocess.run(["dig", "+short", "@1.1.1.1", "trycloudflare.com"],
                            capture_output=True, text=True, check=True).stdout.split()
    return next(line for line in answer if re.match(r"^\d+\.\d+\.\d+\.\d+$", line))


def wait_reachable(browser, url):
    """A new tunnel can answer with an error for its first seconds."""
    context = browser.new_context()
    try:
        deadline = time.time() + 120
        while True:
            try:
                response = context.request.get(url.split("/console")[0] + "/v1/health", timeout=10000)
                if response.status == 200:
                    return
            except Exception:
                if time.time() > deadline:
                    raise
            time.sleep(2)
    finally:
        context.close()


@pytest.fixture(scope="module", autouse=True)
def console_password():
    if not PASSWORD:
        pytest.fail("Set CLOAKROOM_CONSOLE_PASSWORD to this install's console password.")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            args=[f"--host-resolver-rules=MAP *.trycloudflare.com {cloudflare_address()}"])
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def link(browser):
    url = share_link()
    wait_reachable(browser, url)
    # After a restart the browser can take minutes to come up; the tests time runs, not that.
    context = browser.new_context()
    sign_in(context.new_page(), url)
    deadline = time.time() + 300
    while not context.request.get(url.split("/console")[0] + "/v1/status").json()["browser_connected"]:
        assert time.time() < deadline, "the browser never connected"
        time.sleep(3)
    context.close()
    return url


@pytest.fixture
def page(browser, link):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    sign_in(page, link)
    base = link.split("/console")[0]
    before = {s["session"] for s in context.request.get(base + "/v1/sessions").json()["sessions"]}
    yield page
    # Close what this test opened, so the next one starts from the same list.
    for session in context.request.get(base + "/v1/sessions").json()["sessions"]:
        if session["session"] not in before and session["state"] not in ("working", "paused", "waiting"):
            context.request.post(f"{base}/v1/sessions/{session['session']}/close")
    context.close()


def start_session(page, message):
    """Start a session from the console; returns its id once the page has selected it."""
    before = [s["session"] for s in page.request.get(page.url.split("/console")[0] + "/v1/sessions").json()["sessions"]]
    page.get_by_test_id("new-message").fill(message)
    page.get_by_test_id("new-start").click()
    expect(page.get_by_test_id("new-message")).to_have_value("")
    page.wait_for_function("before => location.hash.startsWith('#s_') && !before.includes(location.hash.slice(1))",
                           arg=before)
    return page.evaluate("location.hash.slice(1)")


def status(page):
    return page.get_by_test_id("session-status")


def cloakroom_messages(page):
    return page.get_by_test_id("message-cloakroom")


def list_item(page, session):
    return page.locator(f'[data-testid="session-item"][data-session="{session}"]')


def step_count(page):
    steps = page.get_by_test_id("steps").last
    if not steps.count():
        return 0
    return int(re.match(r"\d+", steps.locator("summary").inner_text()).group(0))


# ---------------------------------------------------------------- the link


def test_the_console_asks_for_the_password_and_keeps_the_device_30_days(browser, link):
    base = link.split("/console")[0]
    context = browser.new_context()
    page = context.new_page()

    page.goto(link)
    expect(page.get_by_role("heading", name="Sign in to the console")).to_be_visible()
    assert page.request.get(base + "/v1/sessions").status == 401
    assert page.request.get(base + "/viewer/core/rfb.js").status == 401

    page.get_by_label("Console password").fill(PASSWORD + "-not")
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("alert")).to_contain_text("Wrong password")

    page.get_by_label("Console password").fill(PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_test_id("events-state")).to_have_text("Live updates on", timeout=30000)
    assert page.request.get(base + "/v1/sessions").status == 200
    cookie = next(c for c in context.cookies() if c["name"] == "cloakroom_console")
    assert cookie["httpOnly"] and cookie["secure"] and cookie["sameSite"] == "Lax"
    assert abs(cookie["expires"] - time.time() - 30 * 24 * 3600) < 600

    # Another site's page cannot use the cookie.
    assert page.request.post(base + "/v1/devices/sign-out-everywhere",
                             headers={"Origin": "https://example.com"}).status == 401
    context.close()


def test_signing_out_another_device_sends_it_back_to_sign_in(browser, link):
    base = link.split("/console")[0]
    mine = browser.new_context()
    other = browser.new_context()
    page = mine.new_page()
    other_page = other.new_page()
    sign_in(page, link)
    sign_in(other_page, link)
    other_id = next(d["device"] for d in other.request.get(base + "/v1/devices").json()["devices"] if d["current"])

    page.get_by_test_id("devices-open").click()
    expect(page.get_by_test_id("devices")).to_be_visible()
    expect(page.get_by_test_id("device").filter(has_text="This device")).to_have_count(1)
    page.locator(f'[data-device="{other_id}"]').click()
    expect(page.locator(f'[data-device="{other_id}"]')).to_have_count(0)

    expect(other_page.get_by_role("heading", name="Sign in to the console")).to_be_visible(timeout=60000)
    assert other.request.get(base + "/v1/sessions").status == 401
    assert page.request.get(base + "/v1/sessions").status == 200
    mine_id = next(d["device"] for d in mine.request.get(base + "/v1/devices").json()["devices"] if d["current"])
    mine.request.post(f"{base}/v1/devices/{mine_id}/sign-out")
    mine.close()
    other.close()


# ---------------------------------------------------------------- sessions


def test_new_session_runs_to_a_reply_with_steps_and_a_live_view(page):
    session = start_session(page, "Open example.com and tell me the page's main heading.")
    expect(list_item(page, session)).to_be_visible()
    expect(status(page)).to_have_text(re.compile("Waiting its turn|Working"), timeout=30000)

    expect(page.get_by_test_id("live-view")).to_be_visible(timeout=RUN_TIMEOUT)
    expect(page.get_by_test_id("live-view")).to_have_attribute("data-connected", "true", timeout=30000)
    expect(page.get_by_test_id("live-view")).to_have_attribute("data-view-only", "true")

    expect(status(page)).to_have_text("Finished", timeout=RUN_TIMEOUT)
    expect(page.get_by_test_id("session-title")).to_have_text("example.com")
    # What the model says varies; the console's job is to show it.
    expect(cloakroom_messages(page).last.locator(".bubble")).to_contain_text(re.compile("example|domain", re.I))
    assert step_count(page) >= 1
    steps = page.get_by_test_id("steps").last
    if not steps.evaluate("details => details.open"):
        steps.locator("summary").click()
    expect(steps.locator("li").first).to_be_visible()
    steps.locator("summary").click()
    expect(steps.locator("li").first).to_be_hidden()

    item = list_item(page, session)
    expect(item).to_have_attribute("data-state", "done")
    thumbnail = item.locator("img")
    expect(thumbnail).to_have_count(1)
    page.wait_for_function("img => img.complete && img.naturalWidth > 0", arg=thumbnail.element_handle())
    expect(page.get_by_test_id("browser-state")).to_have_text("Browser ready")

    # When idle, the live view hands the user the mouse.
    expect(page.get_by_test_id("live-view")).to_have_attribute("data-view-only", "false")


def test_a_follow_up_queues_behind_the_run_and_stays_in_the_same_tab(page):
    session = start_session(page, "Open example.com and tell me the page's main heading.")
    expect(status(page)).to_have_text(re.compile("Waiting its turn|Working"), timeout=30000)
    page.get_by_test_id("reply").fill("What does the one link on that page say?")
    page.get_by_test_id("send").click()

    expect(page.get_by_test_id("message-you")).to_have_count(2)
    expect(cloakroom_messages(page)).to_have_count(2)
    expect(cloakroom_messages(page).last).to_have_attribute("data-status", re.compile("queued|running"))

    expect(cloakroom_messages(page).first).to_have_attribute("data-status", "done", timeout=RUN_TIMEOUT)
    expect(cloakroom_messages(page).last).to_have_attribute("data-status", "done", timeout=RUN_TIMEOUT)
    expect(cloakroom_messages(page).last.locator(".bubble")).not_to_have_text("(no reply)")
    assert page.evaluate("location.hash.slice(1)") == session
    expect(list_item(page, session)).to_contain_text("What does the one link")


def test_take_over_holds_the_run_and_hand_back_resumes_it_then_stop(page):
    start_session(page, "Go to wikipedia.org, search for Austin, Texas, open the article, "
                        "and tell me the population in the infobox and the name of the mayor.")
    expect(status(page)).to_have_text("Working", timeout=RUN_TIMEOUT)
    page.wait_for_function("() => document.querySelectorAll('[data-testid=steps] li').length >= 1",
                           timeout=RUN_TIMEOUT)

    page.get_by_test_id("pause").click()
    expect(status(page)).to_have_text("Paused · you have the mouse")
    expect(page.get_by_test_id("paused-note")).to_be_visible()
    expect(page.get_by_test_id("live-view")).to_have_attribute("data-view-only", "false")

    # The step in flight may finish; after that nothing moves while the user drives.
    time.sleep(20)
    held = step_count(page)
    time.sleep(15)
    assert step_count(page) == held, "the run took steps while paused"

    page.get_by_test_id("resume").click()
    expect(status(page)).to_have_text("Working")
    expect(page.get_by_test_id("live-view")).to_have_attribute("data-view-only", "true")
    page.wait_for_function(f"() => {{ const s = document.querySelectorAll('[data-testid=steps]');"
                           f" const summary = s[s.length - 1]?.querySelector('summary')?.textContent || '';"
                           f" return parseInt(summary) > {held}; }}", timeout=RUN_TIMEOUT)

    page.get_by_test_id("cancel").click()
    expect(status(page)).to_have_text("Stopped", timeout=RUN_TIMEOUT)
    expect(cloakroom_messages(page).last).to_have_attribute("data-status", "cancelled")


# ---------------------------------------------------------------- needs you


def test_a_sign_in_hands_off_with_a_session_link_that_opens_anywhere(browser, page, link):
    session = start_session(page, "Go to github.com and open my notifications")
    expect(status(page)).to_have_text("Needs you", timeout=RUN_TIMEOUT)
    expect(list_item(page, session)).to_have_attribute("data-state", "needs")
    expect(page.locator(".group").first).to_have_text("Needs you")

    card = page.get_by_test_id("needs-card")
    expect(card).to_be_visible()
    expect(card).to_contain_text(re.compile("sign in", re.I))
    expect(page.get_by_test_id("live-view")).to_have_attribute("data-view-only", "false")

    session_link = page.get_by_test_id("share-link").inner_text()
    assert session_link == link + "#" + session

    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.get_by_test_id("copy-link").click()
    expect(page.get_by_test_id("copy-link")).to_have_text("Copied")
    assert page.evaluate("navigator.clipboard.readText()") == session_link

    # The link the agent sends lands a phone straight on this session.
    phone = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    phone_page = phone.new_page()
    sign_in(phone_page, session_link)
    expect(phone_page.get_by_test_id("needs-card")).to_be_visible(timeout=30000)
    assert phone_page.evaluate("location.hash.slice(1)") == session
    assert phone_page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "the phone page scrolls sideways"

    # Done, carry on: Cloakroom picks up in the same tab. Nobody signed in, so it asks again.
    phone_page.get_by_test_id("carry-on").click()
    expect(phone_page.get_by_test_id("message-you").last.locator(".bubble")).to_have_text("I’m done, carry on")
    expect(phone_page.get_by_test_id("session-status")).to_have_text(
        re.compile("Waiting its turn|Working"), timeout=30000)
    expect(phone_page.get_by_test_id("session-status")).to_have_text("Needs you", timeout=RUN_TIMEOUT)
    expect(phone_page.get_by_test_id("message-cloakroom")).to_have_count(2)
    phone.close()
    expect(status(page)).to_have_text("Needs you")

    page.get_by_test_id("close-needs").click()
    expect(list_item(page, session)).to_have_count(0)


# ---------------------------------------------------------------- tabs


def test_show_it_live_brings_a_background_session_to_the_front_and_close_forgets_it(page):
    first = start_session(page, "Open example.com and tell me the page's main heading.")
    expect(status(page)).to_have_text("Finished", timeout=RUN_TIMEOUT)
    second = start_session(page, "Open example.org and tell me the page's main heading.")
    expect(status(page)).to_have_text("Finished", timeout=RUN_TIMEOUT)

    list_item(page, first).click()
    expect(page.get_by_test_id("still-view")).to_be_visible()
    page.get_by_test_id("show-live").click()
    expect(page.get_by_test_id("live-view")).to_be_visible(timeout=30000)

    list_item(page, second).click()
    expect(page.get_by_test_id("still-view")).to_be_visible()

    page.get_by_test_id("close").click()
    expect(list_item(page, second)).to_have_count(0)
    list_item(page, first).click()
    page.get_by_test_id("close").click()
    expect(list_item(page, first)).to_have_count(0)


# ---------------------------------------------------------------- unshare


def test_unshare_expires_the_link_and_a_new_share_asks_again(browser, link):
    context = browser.new_context()
    page = context.new_page()
    sign_in(page, link)

    cloakroom("unshare")
    gone = browser.new_context()
    response = gone.new_page().goto(link)
    assert response.status >= 400, "the old link still answers after unshare"
    gone.close()

    fresh = share_link()
    assert fresh != link
    wait_reachable(browser, fresh)
    # A new share is a new address: the cookie from the old one does not go there.
    page.goto(fresh)
    expect(page.get_by_role("heading", name="Sign in to the console")).to_be_visible(timeout=60000)
    sign_in(page, fresh)
    context.close()

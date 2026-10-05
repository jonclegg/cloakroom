"""Enter a site from Bing: search the domain, click the organic result."""

import os
import sys
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

import humanize

CDP_URL = os.environ.get("CDP_URL", "http://127.0.0.1:9222")
BING = "https://www.bing.com/"
SEARCH_BOXES = (
    'textarea[name="q"]',
    'input[name="q"]',
    "#sb_form_q",
)
SEARCH_BUTTONS = (
    "#search_icon",
    "#sb_form_go",
    'button[aria-label="Search"]',
)
CONSENT_BUTTONS = (
    "#bnp_btn_accept",
    'button:has-text("Accept")',
)

###############################################################################

def _host(url):
    name = (urlparse(url).hostname or "").lower()
    if name.startswith("www."):
        return name[4:]
    return name

###############################################################################

def _same_site(domain, href):
    host = _host(href)
    domain = domain.lower().removeprefix("www.")
    return host == domain or host.endswith("." + domain)

###############################################################################

def _visible(page, selector):
    locator = page.locator(selector).first
    if locator.count() == 0:
        return None
    if not locator.is_visible():
        return None
    return locator

###############################################################################

def _first_visible(page, selectors):
    for selector in selectors:
        locator = _visible(page, selector)
        if locator is not None:
            return locator
    return None

###############################################################################

def _dismiss_consent(page):
    button = _first_visible(page, CONSENT_BUTTONS)
    if button is None:
        return
    humanize.human_click(page, button)
    humanize.pause(0.4, 0.9)

###############################################################################

def _cites_domain(link, domain):
    block = link.locator("xpath=ancestor::li[contains(@class,'b_algo')][1]")
    cite = block.locator("cite").first
    if cite.count() == 0:
        return False
    needle = domain.lower().removeprefix("www.")
    return needle in cite.inner_text().lower()

###############################################################################

def _organic_link(page, domain):
    links = page.locator("#b_results li.b_algo:not(.b_ad) h2 a")
    for index in range(links.count()):
        link = links.nth(index)
        href = link.get_attribute("href") or ""
        if _same_site(domain, href) or _cites_domain(link, domain):
            return link
    raise RuntimeError(f"No organic Bing result for {domain}")

###############################################################################

def _click_and_follow(page, link, domain=None):
    """Click a result and return the page it landed on.

    Bing usually opens the target in a new tab through a `bing.com/ck/a`
    redirect, and that tab can take several seconds to leave `about:blank`.
    Waiting a fixed 0.8-1.6s and checking `context.pages` once misses it, so
    the caller ends up still on Bing. Poll for the new tab, then wait for it
    to reach a real URL.
    """
    context = page.context
    before = set(context.pages)
    start_url = page.url

    landed = None
    for attempt in range(3):
        humanize.human_click(page, link)
        deadline = time.time() + 12
        while time.time() < deadline:
            humanize.pause(0.25, 0.45)
            opened = [item for item in context.pages if item not in before]
            if opened:
                landed = opened[-1]
                break
            if page.url != start_url:
                landed = page
                break
        if landed is not None:
            break
        # Bing sometimes swallows the first click; click again.
        humanize.pause(0.6, 1.1)
    if landed is None:
        landed = page

    # Wait for the tab to leave about:blank / the Bing redirect.
    deadline = time.time() + 20
    while time.time() < deadline:
        url = landed.url or ""
        if url and url != "about:blank" and "chrome://" not in url:
            if domain is None or _same_site(domain, url) or "bing.com" not in _host(url):
                break
        humanize.pause(0.3, 0.5)

    try:
        landed.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:  # noqa: BLE001 - a slow site is not a failure
        pass
    humanize.pause(0.8, 1.6)
    return landed

###############################################################################

def _enter(page, domain):
    """One attempt: search the domain on Bing and click the organic result."""
    box = _first_visible(page, SEARCH_BOXES)
    if box is None:
        raise RuntimeError("Bing search box not found")
    humanize.human_click(page, box)
    humanize.pause(0.2, 0.5)
    humanize.human_type(page, domain)
    humanize.pause(0.4, 0.9)
    button = _first_visible(page, SEARCH_BUTTONS)
    if button is None:
        raise RuntimeError("Bing search button not found")
    humanize.human_click(page, button)
    page.wait_for_load_state("domcontentloaded")
    humanize.pause(0.8, 1.6)
    link = _organic_link(page, domain)
    return _click_and_follow(page, link, domain=domain)

###############################################################################

def open_via_bing(page, domain, query=None, attempts=2):
    """Enter `domain` through Bing, retrying if the first click does not land."""
    if query is None:
        query = domain
    landed = page
    for attempt in range(attempts):
        landed.goto(BING, wait_until="domcontentloaded")
        humanize.pause(0.8, 1.6)
        _dismiss_consent(landed)
        try:
            landed = _enter(landed, query)
        except RuntimeError:
            if attempt == attempts - 1:
                raise
            continue
        if _same_site(domain, landed.url):
            return landed
        humanize.pause(0.6, 1.2)
    return landed

###############################################################################

def main():
    domain = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    query = sys.argv[2] if len(sys.argv) > 2 else None
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        page = browser.contexts[0].new_page()
        landed = open_via_bing(page, domain, query)
        print(f"Page title: {landed.title()}")
        print(f"URL: {landed.url}")
        print("The tab stays open - look for it in the viewer.")

###############################################################################

if __name__ == "__main__":
    main()

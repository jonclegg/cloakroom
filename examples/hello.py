import os

from playwright.sync_api import sync_playwright

CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    page = browser.contexts[0].new_page()
    page.goto("https://example.com")
    print(f"Page title: {page.title()}")
    print("The tab stays open - look for it in the viewer.")

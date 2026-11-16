"""Capture the throwaway UI alternatives; this is a visual preview, not an acceptance suite."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for width in (1440, 390):
        page = browser.new_page(viewport={"width": width, "height": 1000}, locale="it-IT")
        page.on("pageerror", lambda error: print(f"Browser: {error}", flush=True))
        for variant in ("A", "B", "C"):
            for query, name in (("", "home"), ("&fermentation=ipa", "detail")):
                response = page.goto(f"{os.environ['PROTOTYPE_URL']}/?variant={variant}{query}")
                if response is None or not response.ok:
                    raise RuntimeError(
                        f"Preview unavailable: {response.status if response else 'no response'}"
                    )
                page.locator(".p-prototype-switcher").wait_for()
                page.wait_for_timeout(800)
                page.screenshot(
                    path=Path("/artifacts") / f"{variant}-{name}-{width}.png", full_page=True
                )
                print(f"Captured {variant} {name} at {width}px", flush=True)
        page.close()
    browser.close()

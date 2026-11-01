from collections.abc import Iterator

import httpx
import pytest
from playwright.sync_api import Browser, Page, sync_playwright


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser: Browser, api: httpx.Client) -> Iterator[Page]:
    context = browser.new_context(locale="it-IT", timezone_id="Europe/Rome")
    instance = context.new_page()
    yield instance
    context.close()

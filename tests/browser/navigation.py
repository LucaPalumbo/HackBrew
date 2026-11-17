"""Open public destinations after the dashboard was split into focused pages."""

import httpx
from playwright.sync_api import Page


def open_active_fermentation(page: Page, api: httpx.Client) -> None:
    response = api.get("/api/fermentations/active")
    response.raise_for_status()
    cycle = response.json()["fermentation"]
    page.goto(f"{str(api.base_url).rstrip('/')}/?fermentation={cycle['id']}")

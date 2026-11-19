"""Open public destinations after the dashboard was split into focused pages."""

import httpx
from playwright.sync_api import Page


def open_active_fermentation(page: Page, api: httpx.Client) -> None:
    response = api.get("/api/fermentations/active")
    response.raise_for_status()
    cycle = response.json()["fermentation"]
    page.goto(f"{str(api.base_url).rstrip('/')}/?fermentation={cycle['id']}")


def show_management(page: Page) -> None:
    page.get_by_role("tab", name="Gestione", exact=True).click()


def finish_fermentation(page: Page) -> None:
    confirmation = page.get_by_role("dialog", name="Concludi la fermentazione")
    if not confirmation.is_visible():
        show_management(page)
        page.get_by_role("button", name="Termina fermentazione", exact=True).click()
    confirmation.get_by_role("button", name="Conferma termine", exact=True).click()

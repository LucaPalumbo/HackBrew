"""Open public destinations after the dashboard was split into focused pages."""

import httpx
from playwright.sync_api import Locator, Page, expect


def open_active_fermentation(page: Page, api: httpx.Client) -> None:
    response = api.get("/api/fermentations/active")
    response.raise_for_status()
    cycle = response.json()["fermentation"]
    page.goto(f"{str(api.base_url).rstrip('/')}/?fermentation={cycle['id']}")


def show_management(page: Page) -> None:
    close_raw_readings(page)
    page.get_by_role("tab", name="Gestione", exact=True).click()


def open_raw_readings(page: Page) -> Locator:
    dialog = page.get_by_role("dialog", name="Dati grezzi", exact=True)
    if not dialog.is_visible():
        page.get_by_role("button", name="Dati grezzi", exact=True).click()
    expect(dialog).to_be_visible()
    expect(dialog.get_by_text("Caricamento dati grezzi…", exact=True)).to_have_count(0)
    return dialog


def close_raw_readings(page: Page) -> None:
    dialog = page.get_by_role("dialog", name="Dati grezzi", exact=True)
    if dialog.is_visible():
        dialog.get_by_role("button", name="Chiudi dati grezzi", exact=True).click()
        expect(dialog).to_have_count(0)


def finish_fermentation(page: Page) -> None:
    confirmation = page.get_by_role("dialog", name="Concludi la fermentazione")
    if not confirmation.is_visible():
        show_management(page)
        page.get_by_role("button", name="Termina fermentazione", exact=True).click()
    confirmation.get_by_role("button", name="Conferma termine", exact=True).click()

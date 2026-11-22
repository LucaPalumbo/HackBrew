"""Global configuration on desktop and mobile through public interfaces."""

from contextlib import suppress

import httpx
import pytest
from playwright.sync_api import APIResponse, Page, Route, expect
from playwright.sync_api import Error as PlaywrightError


@pytest.mark.parametrize("width", [1440, 390])
def test_settings_safety_summary_and_fractional_seconds_survive_reload(
    page: Page, api: httpx.Client, width: int
) -> None:
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=settings")
    summary = page.get_by_role("complementary", name="Regole di sicurezza", exact=True)
    expect(summary).to_contain_text("Ultima lettura ricevuta")
    expect(summary).to_contain_text("Ultimo comando valido")
    expect(page.get_by_label("Timeout desiderato", exact=True)).to_contain_text("3 ore")
    field = page.get_by_label("Timeout di comunicazione (secondi)", exact=True)
    field.fill("0.125")
    page.get_by_role("button", name="Salva timeout", exact=True).click()
    expect(page.get_by_role("status", name="Esito salvataggio")).to_contain_text("salvato")
    assert api.get("/api/settings").json()["communication_timeout_seconds"] == 0.125
    page.reload()
    expect(field).to_have_value("0.125")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_failed_initial_load_can_retry_without_inventing_defaults(
    page: Page, api: httpx.Client
) -> None:
    api.patch("/api/settings", json={"communication_timeout_seconds": 7200}).raise_for_status()
    page.route("**/api/settings", lambda route: route.fulfill(status=503, json={}))
    page.goto(f"{api.base_url}?page=settings")
    expect(page.get_by_role("alert")).to_contain_text("leggere le impostazioni")
    expect(page.get_by_label("Timeout desiderato", exact=True)).to_have_count(0)
    page.unroute("**/api/settings")
    page.get_by_role("button", name="Riprova impostazioni", exact=True).click()
    expect(page.get_by_label("Timeout desiderato", exact=True)).to_contain_text("2 ore")


@pytest.mark.parametrize("leave", [False, True])
def test_pending_save_is_submitted_once_and_cannot_affect_another_page(
    page: Page, api: httpx.Client, leave: bool
) -> None:
    page.goto(f"{api.base_url}?page=settings")
    field = page.get_by_label("Timeout di comunicazione (secondi)", exact=True)
    expect(field).to_have_value("10800")
    field.fill("3600")
    pending: list[tuple[Route, APIResponse]] = []

    def hold(route: Route) -> None:
        if route.request.method == "PATCH":
            pending.append((route, route.fetch()))
        else:
            route.continue_()

    page.route("**/api/settings", hold)
    page.get_by_role("button", name="Salva timeout", exact=True).click()
    expect(page.get_by_role("button", name="Salvataggio…", exact=True)).to_be_disabled()
    field.locator("..").locator("..").dispatch_event("submit")
    assert len(pending) == 1
    expect(page.get_by_role("status", name="Esito salvataggio")).to_have_count(0)
    assert api.get("/api/settings").json()["communication_timeout_seconds"] == 3600
    if leave:
        page.get_by_role("link", name="Home", exact=True).click()
    route, response = pending[0]
    with suppress(PlaywrightError):
        route.fulfill(response=response)
    if leave:
        expect(page.get_by_role("status", name="Esito salvataggio")).to_have_count(0)
        page.goto(f"{api.base_url}?page=settings")
    else:
        expect(page.get_by_role("status", name="Esito salvataggio")).to_contain_text("salvato")
    expect(field).to_have_value("3600")
    expect(page.get_by_label("Timeout desiderato", exact=True)).to_contain_text("1 ora")


def test_live_refresh_preserves_an_unsaved_fractional_draft(page: Page, api: httpx.Client) -> None:
    page.goto(f"{api.base_url}?page=settings")
    field = page.get_by_label("Timeout di comunicazione (secondi)", exact=True)
    expect(field).to_have_value("10800")
    field.fill("23.45")
    api.patch("/api/settings", json={"communication_timeout_seconds": 86400}).raise_for_status()
    expect(page.get_by_label("Timeout desiderato", exact=True)).to_contain_text("24 ore")
    expect(field).to_have_value("23.45")
    page.get_by_role("button", name="Salva timeout", exact=True).click()
    expect(page.get_by_role("status", name="Esito salvataggio")).to_contain_text("salvato")
    assert api.get("/api/settings").json()["communication_timeout_seconds"] == 23.45

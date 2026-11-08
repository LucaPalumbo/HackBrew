import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.thermal import thermal_simulator


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_change_global_timeout_and_observe_device_confirmation(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    with thermal_simulator() as simulator:
        api.post(
            "/api/thermal-devices",
            json={"name": "Frigo", "capability": "both", "base_url": str(simulator.base_url)},
        ).raise_for_status()
        page.set_viewport_size({"width": width, "height": height})
        page.goto(str(api.base_url))
        page.get_by_role("link", name="Impostazioni", exact=True).click()
        expect(page.get_by_role("heading", name="Impostazioni", exact=True)).to_be_visible()
        expect(page.get_by_label("Timeout di comunicazione (secondi)", exact=True)).to_have_value(
            "10800"
        )
        simulator.patch("/__simulation", json={"control_http_status": 503}).raise_for_status()
        page.get_by_label("Timeout di comunicazione (secondi)", exact=True).fill("2.5")
        page.get_by_role("button", name="Salva timeout", exact=True).click()
        expect(page.get_by_role("status", name="Esito salvataggio", exact=True)).to_contain_text(
            "salvato"
        )
        device = page.get_by_role("region", name="Sincronizzazione Frigo", exact=True)
        expect(device).to_contain_text("Errore di sincronizzazione", timeout=10000)
        expect(page.get_by_label("Timeout desiderato", exact=True)).to_contain_text("2,5 s")
        simulator.patch("/__simulation", json={"control_http_status": 200}).raise_for_status()
        expect(device).to_contain_text("Sincronizzato", timeout=10000)
        expect(device).to_contain_text("Revisione confermata: 1")
        expect(device).to_contain_text("2,5 s")
        assert simulator.get("/api/v1/state").json()["accepted_command"] is None
        page.reload()
        expect(page.get_by_label("Timeout di comunicazione (secondi)", exact=True)).to_have_value(
            "2.5"
        )
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            page.screenshot(
                path=Path(directory) / f"impostazioni-timeout-{width}.png", full_page=True
            )


def test_failed_save_is_not_acknowledged_and_the_draft_can_be_retried(
    page: Page, api: httpx.Client
) -> None:
    page.goto(str(api.base_url) + "?page=settings")
    field = page.get_by_label("Timeout di comunicazione (secondi)", exact=True)
    expect(field).to_have_value("10800")
    field.fill("0")
    page.get_by_role("button", name="Salva timeout", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("durata positiva")
    field.fill("2.5")
    page.route(
        "**/api/settings",
        lambda route: (
            route.fulfill(status=503, body="{}")
            if route.request.method == "PATCH"
            else route.continue_()
        ),
    )
    page.get_by_role("button", name="Salva timeout", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("salvataggio non è stato confermato")
    expect(page.get_by_role("status", name="Esito salvataggio", exact=True)).to_have_count(0)
    assert api.get("/api/settings").json()["communication_timeout_seconds"] == 10800
    page.unroute("**/api/settings")
    expect(field).to_have_value("2.5")
    page.get_by_role("button", name="Salva timeout", exact=True).click()
    expect(page.get_by_role("status", name="Esito salvataggio", exact=True)).to_contain_text(
        "salvato"
    )
    assert api.get("/api/settings").json()["communication_timeout_seconds"] == 2.5


def test_settings_update_live_communication_without_inventing_a_new_receipt(
    page: Page, api: httpx.Client
) -> None:
    from tests.payloads import gateway_lettura

    api.post("/telemetry", json=gateway_lettura()).raise_for_status()
    before = api.get("/api/readings/latest").json()
    page.goto(str(api.base_url))
    expect(page.get_by_label("Stato dei dati")).to_have_text("Lettura disponibile")
    api.patch("/api/settings", json={"communication_timeout_seconds": 0.01}).raise_for_status()
    expect(page.get_by_label("Stato dei dati")).to_have_text("Timeout di comunicazione superato")
    api.patch("/api/settings", json={"communication_timeout_seconds": 10800}).raise_for_status()
    expect(page.get_by_label("Stato dei dati")).to_have_text("Lettura disponibile")
    after = api.get("/api/readings/latest").json()
    assert after["reading"] == before["reading"]
    assert after["last_received_at"] == before["last_received_at"]

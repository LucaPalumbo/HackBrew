"""Register and observe thermal equipment from desktop and phone browsers."""

import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.thermal import thermal_simulator


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_register_verify_and_recover_thermal_device(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    with thermal_simulator() as simulator:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(str(api.base_url) + "?page=devices")
        page.get_by_label("Nome del dispositivo termico", exact=True).fill("Frigo combinato")
        page.get_by_label("Funzioni del dispositivo", exact=True).select_option("both")
        page.get_by_label("Indirizzo HTTP", exact=True).fill("http://thermal-both:8000/")
        page.get_by_role("button", name="Registra dispositivo termico", exact=True).click()
        card = page.get_by_role("region", name="Dispositivo termico Frigo combinato", exact=True)
        expect(card).to_contain_text("Non verificato")
        expect(card).to_contain_text("Stato sconosciuto")
        expect(card).to_contain_text("Riscaldamento e raffreddamento")
        card.get_by_role("button", name="Verifica collegamento", exact=True).click()
        expect(card).to_contain_text("Spento confermato")
        expect(card).to_contain_text("10.800 s")
        expect(card).to_contain_text("Revisione applicata: 0")
        assert simulator.get("/api/v1/state").json()["last_command_at"] is None
        simulator.patch("/__simulation", json={"state_http_status": 503}).raise_for_status()
        card.get_by_role("button", name="Verifica collegamento", exact=True).click()
        expect(card).to_contain_text("Stato sconosciuto")
        expect(card).to_contain_text("Verifica HTTP fallita")
        expect(card).not_to_contain_text("Spento confermato")
        expect(card).to_contain_text("Ultima conferma precedente")
        page.reload()
        expect(card).to_contain_text("Stato sconosciuto")
        simulator.patch("/__simulation", json={"state_http_status": 200}).raise_for_status()
        card.get_by_role("button", name="Verifica collegamento", exact=True).click()
        expect(card).to_contain_text("Spento confermato")
        expect(page.get_by_role("button", name="Accendi", exact=True)).to_have_count(0)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            page.screenshot(
                path=Path(directory) / f"dispositivi-termici-{width}.png", full_page=True
            )


def test_invalid_address_unreachable_device_and_duplicate_registration(
    page: Page, api: httpx.Client
) -> None:
    page.goto(str(api.base_url) + "?page=devices")
    registration = page.get_by_role("region", name="Registrazione dispositivo termico", exact=True)
    expect(page.get_by_text("Nessun dispositivo termico registrato.", exact=True)).to_be_visible()
    page.get_by_label("Nome del dispositivo termico", exact=True).fill("Frigo spento")
    page.get_by_label("Funzioni del dispositivo", exact=True).select_option("cooling")
    page.get_by_label("Indirizzo HTTP", exact=True).fill("ftp://frigo.local")
    registration.get_by_role("button", name="Registra dispositivo termico", exact=True).click()
    expect(registration.get_by_role("alert")).to_contain_text("indirizzo HTTP(S)")
    assert api.get("/api/thermal-devices").json()["devices"] == []
    page.get_by_label("Indirizzo HTTP", exact=True).fill("http://thermal-cooling:1")
    registration.get_by_role("button", name="Registra dispositivo termico", exact=True).click()
    card = page.get_by_role("region", name="Dispositivo termico Frigo spento", exact=True)
    expect(card).to_contain_text("Raffreddamento")
    card.get_by_role("button", name="Verifica collegamento", exact=True).click()
    expect(card).to_contain_text("Stato sconosciuto")
    expect(card.get_by_role("alert")).to_contain_text("Verifica HTTP fallita")
    expect(card).not_to_contain_text("Spento confermato")
    page.get_by_label("Nome del dispositivo termico", exact=True).fill("Duplicato")
    page.get_by_label("Indirizzo HTTP", exact=True).fill("http://THERMAL-cooling:1/")
    registration.get_by_role("button", name="Registra dispositivo termico", exact=True).click()
    expect(registration.get_by_role("alert")).to_contain_text("già registrato")
    assert len(api.get("/api/thermal-devices").json()["devices"]) == 1


def test_failed_registry_load_does_not_invent_an_empty_list_and_can_retry(
    page: Page, api: httpx.Client
) -> None:
    page.route("**/api/thermal-devices", lambda route: route.fulfill(status=503, body="{}"))
    page.goto(str(api.base_url) + "?page=devices")
    registry = page.get_by_role("region", name="Dispositivi termici", exact=True)
    expect(registry.get_by_role("alert")).to_contain_text("recuperare i dispositivi termici")
    expect(page.get_by_text("Nessun dispositivo termico registrato.", exact=True)).to_have_count(0)
    page.unroute("**/api/thermal-devices")
    registry.get_by_role("button", name="Aggiorna dispositivi termici", exact=True).click()
    expect(page.get_by_text("Nessun dispositivo termico registrato.", exact=True)).to_be_visible()
    expect(registry.get_by_role("alert")).to_have_count(0)

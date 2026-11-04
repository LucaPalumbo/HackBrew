import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.payloads import gateway_lettura


@pytest.fixture
def api(empty_api: httpx.Client) -> httpx.Client:
    return empty_api


def test_first_start_requires_registering_a_pillola(page: Page, api: httpx.Client) -> None:
    page.goto(str(api.base_url))
    expect(page.get_by_role("button", name="Aggiorna lettura", exact=True)).to_be_enabled()
    expect(page.get_by_role("button", name="Avvia fermentazione", exact=True)).to_be_disabled()
    expect(page.get_by_text("Registra prima una pillola nella pagina Dispositivi.")).to_be_visible()


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_register_pillole_and_see_each_live_diagnostic_reading(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url))
    page.get_by_role("link", name="Dispositivi", exact=True).click()
    expect(page.get_by_role("heading", name="Dispositivi", exact=True)).to_be_visible()
    page.get_by_label("Nome della pillola", exact=True).fill("Pillola IPA")
    page.get_by_label("MAC Bluetooth", exact=True).fill("aa-bb-cc-dd-ee-ff")
    page.get_by_role("button", name="Registra pillola", exact=True).click()
    first = page.get_by_role("region", name="Pillola Pillola IPA", exact=True)
    expect(first).to_contain_text("AA:BB:CC:DD:EE:FF")
    expect(first).to_contain_text("Nessuna lettura ricevuta")
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(
                pill_mac="AA:BB:CC:DD:EE:FF", valid=True, gravity_velocity=-2.5, accel_x=-0.25
            ),
        ).status_code
        == 200
    )
    expect(first).to_contain_text("1.050")
    expect(first).to_contain_text("-2,5")
    expect(first).to_contain_text("-0,25")
    page.get_by_label("Nome della pillola", exact=True).fill("Pillola Stout")
    page.get_by_label("MAC Bluetooth", exact=True).fill("11:22:33:44:55:66")
    page.get_by_role("button", name="Registra pillola", exact=True).click()
    second = page.get_by_role("region", name="Pillola Pillola Stout", exact=True)
    expect(second).to_contain_text("Nessuna lettura ricevuta")
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(
                pill_mac="11:22:33:44:55:66", specific_gravity=1040, temperature=21.5
            ),
        ).status_code
        == 200
    )
    expect(second).to_contain_text("1.040")
    expect(second).to_contain_text("21,5")
    expect(first).to_contain_text("1.050")
    page.reload()
    expect(first).to_contain_text("1.050")
    expect(second).to_contain_text("1.040")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=path / f"pillole-{width}.png", full_page=True)


def test_choose_registered_pillola_for_diagnostics_and_fermentazione(
    page: Page,
    api: httpx.Client,
) -> None:
    first = api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).json()["pill"]
    second = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(pill_mac=second["mac"], specific_gravity=1040)
        ).status_code
        == 200
    )
    page.goto(str(api.base_url))
    page.get_by_label("Pillola diagnostica").select_option(second["id"])
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible()
    page.get_by_label("Nome della fermentazione").fill("Stout scelta")
    page.get_by_label("Pillola della fermentazione").select_option(second["id"])
    page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
    expect(page.get_by_role("heading", name="Stout scelta", exact=True)).to_be_visible()
    fermentation = api.get("/api/fermentations/active").json()["fermentation"]
    assert fermentation["pill_id"] == second["id"]
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(pill_mac=first["mac"], timestamp=datetime.now(UTC).timestamp()),
        ).status_code
        == 200
    )
    expect(
        page.get_by_role("heading", name="In attesa della prima lettura della fermentazione")
    ).to_be_visible()
    assert api.get(f"/api/fermentations/{fermentation['id']}/readings").json()["readings"] == []
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(
                pill_mac=second["mac"],
                timestamp=datetime.now(UTC).timestamp(),
                specific_gravity=1030,
            ),
        ).status_code
        == 200
    )
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.030", exact=True)
    ).to_be_visible()


def test_duplicate_registration_error_keeps_existing_pillola(page: Page, api: httpx.Client) -> None:
    api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).raise_for_status()
    page.goto(str(api.base_url) + "?page=devices")
    page.get_by_label("Nome della pillola", exact=True).fill("Duplicata")
    page.get_by_label("MAC Bluetooth", exact=True).fill("aabbccddeeff")
    page.get_by_role("button", name="Registra pillola", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("già registrato")
    assert len(api.get("/api/pills").json()["pills"]) == 1

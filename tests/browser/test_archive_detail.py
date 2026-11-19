"""Archive and detail workflows observed through HTTP and the browser."""

import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.heating import start_heating, temperature, wait_regulation
from tests.payloads import fermentation_payload, gateway_lettura
from tests.thermal import thermal_simulator


@pytest.mark.parametrize("width", [1440, 390])
def test_archive_pages_and_search_only_concluded_cycles(
    page: Page, api: httpx.Client, width: int
) -> None:
    for number in range(21):
        cycle = api.post(
            "/api/fermentations", json=fermentation_payload(api, f"Archivio {number:02}")
        ).json()["fermentation"]
        if number == 0:
            api.post(
                "/telemetry",
                json=gateway_lettura(
                    timestamp=datetime.now(UTC).timestamp(), specific_gravity=1060
                ),
            ).raise_for_status()
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
    api.post(
        "/api/fermentations", json=fermentation_payload(api, "Archivio attiva")
    ).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=archive")
    cards = page.get_by_role("region", name="Fermentazioni", exact=True)
    expect(cards.get_by_role("button", name="Apri", exact=False)).to_have_count(20)
    expect(cards.get_by_role("button", name="Apri Archivio attiva", exact=False)).to_have_count(0)
    expect(cards.get_by_text("Batteria", exact=False)).to_have_count(0)
    expect(cards.get_by_role("button", name="Apri Archivio 20", exact=False)).to_contain_text(
        "Termine"
    )
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=path / f"archive-{width}.png", full_page=True)
    page.get_by_role("button", name="Altre fermentazioni", exact=True).click()
    oldest = cards.get_by_role("button", name="Apri Archivio 00", exact=False)
    expect(oldest).to_be_visible()
    expect(oldest).to_contain_text("1.060")
    expect(cards.get_by_role("button", name="Apri", exact=False)).to_have_count(1)
    page.get_by_role("button", name="Fermentazioni più recenti", exact=True).click()
    expect(cards.get_by_role("button", name="Apri", exact=False)).to_have_count(20)
    page.get_by_label("Cerca per nome", exact=True).fill("Archivio 00")
    page.get_by_role("button", name="Cerca fermentazioni", exact=True).click()
    expect(cards.get_by_role("button", name="Apri", exact=False)).to_have_count(1)
    oldest.click()
    expect(page.get_by_role("heading", name="Storico: Archivio 00", exact=True)).to_be_visible()
    expect(page.get_by_label("Cerca per nome", exact=True)).to_have_count(0)
    page.reload()
    expect(page.get_by_role("heading", name="Storico: Archivio 00", exact=True)).to_be_visible()
    page.go_back()
    expect(page.get_by_label("Cerca per nome", exact=True)).to_have_value("Archivio 00")
    expect(cards.get_by_role("button", name="Apri", exact=False)).to_have_count(1)
    page.go_forward()
    expect(page.get_by_role("heading", name="Storico: Archivio 00", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
def test_detail_tabs_preserve_period_and_manage_real_thermal_settings(
    page: Page, api: httpx.Client, width: int
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(f"{api.base_url}?fermentation={cycle['id']}")
        trend = page.get_by_role("tab", name="Andamento", exact=True)
        management = page.get_by_role("tab", name="Gestione", exact=True)
        expect(trend).to_have_attribute("aria-selected", "true")
        expect(page.get_by_role("img", name="Grafico a linee: 1 lettura")).to_be_visible()
        chart = page.get_by_role("img", name="Grafico a linee: 1 lettura").bounding_box()
        summary = page.get_by_role(
            "complementary", name="Riepilogo della fermentazione"
        ).bounding_box()
        assert chart and summary
        if width == 1440:
            assert summary["x"] > chart["x"] + chart["width"]
            assert chart["width"] > summary["width"] * 2
        else:
            assert summary["y"] > chart["y"] + chart["height"]
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=path / f"detail-trend-{width}.png", full_page=True)
        expect(
            page.get_by_role("button", name="Termina fermentazione", exact=True)
        ).not_to_be_visible()
        expect(page.get_by_label("Cerca per nome", exact=True)).to_have_count(0)
        trend.focus()
        trend.press("ArrowRight")
        expect(management).to_be_focused()
        expect(management).to_have_attribute("aria-selected", "true")
        expect(page.get_by_role("tabpanel", name="Gestione", exact=True)).to_be_visible()
        assignments = page.get_by_role("region", name="Associazioni della fermentazione")
        expect(assignments).to_contain_text("AA:BB:CC:DD:EE:FF")
        expect(assignments).to_contain_text("Fascia")
        expect(assignments.get_by_role("combobox")).to_have_count(0)
        editor = page.get_by_role("region", name="Impostazioni termiche", exact=True)
        editor.get_by_label("Nuova temperatura minima (°C)").fill("16")
        editor.get_by_role("button", name="Salva impostazioni termiche").click()
        expect(editor.get_by_label("Valori termici salvati")).to_contain_text("Revisione 1")
        expect(
            editor.get_by_role("table", name="Cronologia impostazioni termiche").get_by_role("row")
        ).to_have_count(3)
        page.reload()
        expect(management).to_have_attribute("aria-selected", "true")
        expect(editor.get_by_label("Nuova temperatura minima (°C)")).to_have_value("16")
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            page.screenshot(path=Path(directory) / f"detail-management-{width}.png", full_page=True)
        management.press("Home")
        expect(trend).to_be_focused()
        expect(trend).to_have_attribute("aria-selected", "true")
        page.get_by_role("button", name="Ingrandisci", exact=True).click()
        period = page.get_by_label("Intervallo visualizzato", exact=True).inner_text()
        management.click()
        trend.click()
        expect(page.get_by_label("Intervallo visualizzato", exact=True)).to_have_text(period)
        page.go_back()
        expect(management).to_have_attribute("aria-selected", "true")
        page.go_forward()
        expect(trend).to_have_attribute("aria-selected", "true")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
def test_manual_end_requires_confirmation_and_keeps_unreachable_device_reserved(
    page: Page, api: httpx.Client, width: int
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(f"{api.base_url}?fermentation={cycle['id']}")
        page.get_by_role("tab", name="Gestione", exact=True).click()
        simulator.patch(
            "/__simulation", json={"state_http_status": 503, "control_http_status": 503}
        ).raise_for_status()
        wait_regulation(
            api,
            cycle,
            "suspended",
            condition=lambda state: state["regulation"]["actual_mode"] is None,
        )
        end = page.get_by_role("button", name="Termina fermentazione", exact=True)
        end.click()
        confirmation = page.get_by_role("dialog", name="Concludi la fermentazione")
        expect(confirmation).to_be_visible()
        assert (
            api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]["status"]
            == "active"
        )
        confirmation.get_by_role("button", name="Annulla", exact=True).click()
        expect(confirmation).not_to_be_visible()
        expect(end).to_be_focused()
        end.click()
        confirmation.get_by_role("button", name="Conferma termine", exact=True).click()
        expect(
            page.get_by_role("heading", name="Storico: IPA riscaldata", exact=True)
        ).to_be_visible()
        regulation = page.get_by_role("region", name="Regolazione IPA riscaldata", exact=True)
        expect(regulation).to_contain_text("Spegnimento in attesa di conferma")
        expect(regulation).to_contain_text("Effettivo: Sconosciuto")
        expect(regulation).to_contain_text("Dispositivo ancora riservato")
        ended = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
        assert ended["status"] == "concluded"
        assert ended["regulation"]["desired_mode"] == "off"
        assert api.get("/api/thermal-devices").json()["devices"][0]["available"] is False
        simulator.patch("/__simulation", json={"control_http_status": 200}).raise_for_status()
        expect(regulation).to_contain_text("Spegnimento confermato", timeout=15000)
        expect(regulation).to_contain_text("Assegnazione rilasciata")
        assert api.get("/api/thermal-devices").json()["devices"][0]["available"] is True
        assert (
            api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]["ended_at"]
            == ended["ended_at"]
        )
        page.reload()
        expect(page.get_by_role("tab", name="Gestione", exact=True)).to_have_attribute(
            "aria-selected", "true"
        )
        expect(end).to_have_count(0)
        expect(page.get_by_role("button", name="Salva impostazioni termiche")).to_have_count(0)


def test_missing_fermentation_has_a_distinct_message_and_a_useful_exit(
    page: Page, api: httpx.Client
) -> None:
    page.goto(f"{api.base_url}?fermentation=00000000-0000-0000-0000-000000000000")
    expect(
        page.get_by_role("heading", name="Fermentazione non trovata", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("tablist")).to_have_count(0)
    page.get_by_role("link", name="← Home", exact=True).click()
    expect(page.get_by_role("heading", name="Inizia dalla prima fermentazione.")).to_be_visible()


@pytest.mark.parametrize("width", [1440, 390])
def test_archive_failure_retry_empty_state_and_monitor_only_management(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Solo monitoraggio attivo")
    ).json()["fermentation"]
    page.set_viewport_size({"width": width, "height": 1000})
    page.route("**/api/fermentations?*", lambda route: route.fulfill(status=503))
    page.goto(f"{api.base_url}?page=archive")
    empty = page.get_by_text("Nessuna fermentazione conclusa.", exact=False)
    expect(page.get_by_role("alert")).to_contain_text("Non è stato possibile recuperare")
    expect(empty).to_have_count(0)
    page.unroute("**/api/fermentations?*")
    page.get_by_role("button", name="Riprova elenco", exact=True).click()
    expect(empty).to_be_visible()
    page.get_by_label("Cerca per nome", exact=True).fill("inesistente")
    page.get_by_role("button", name="Cerca fermentazioni", exact=True).click()
    expect(
        page.get_by_text("Nessuna fermentazione corrisponde alla ricerca.", exact=True)
    ).to_be_visible()
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    page.get_by_role("tab", name="Gestione", exact=True).click()
    expect(
        page.get_by_text(
            "Solo monitoraggio: nessuna soglia o dispositivo termico richiesto.", exact=True
        )
    ).to_be_visible()
    expect(page.get_by_role("region", name="Impostazioni termiche", exact=True)).to_have_count(0)
    expect(page.get_by_role("combobox")).to_have_count(0)
    page.get_by_role("button", name="Termina fermentazione", exact=True).click()
    confirmation = page.get_by_role("dialog", name="Concludi la fermentazione")
    confirmation.press("Escape")
    expect(confirmation).not_to_be_visible()
    assert api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]["status"] == "active"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

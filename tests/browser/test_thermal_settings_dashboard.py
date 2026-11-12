"""Edit a cycle's thermal settings and read its history through the visible UI."""

import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import APIResponse, Page, Route, expect

from tests.heating import start_heating, temperature, wait_regulation
from tests.thermal import thermal_simulator


@pytest.mark.parametrize("width", [1440, 390])
def test_edit_settings_history_reload_and_read_only_end(
    page: Page, api: httpx.Client, width: int
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(f"{api.base_url}?fermentation={cycle['id']}")
        editor = page.get_by_role("region", name="Impostazioni termiche", exact=True)
        expect(editor.get_by_label("Nuova temperatura minima (°C)")).to_have_value("18")
        editor.get_by_label("Nuova temperatura minima (°C)").fill("16")
        editor.get_by_label("Nuova temperatura massima (°C)").fill("21")
        editor.get_by_label("Nuova isteresi (°C)").fill("1")
        editor.get_by_role("button", name="Salva impostazioni termiche").click()
        expect(editor.get_by_role("status", name="Esito impostazioni")).to_contain_text("salvate")
        expect(editor.get_by_label("Valori termici salvati")).to_contain_text("Revisione 1")
        history = editor.get_by_role("table", name="Cronologia impostazioni termiche")
        expect(history.get_by_role("row")).to_have_count(3)
        expect(history.get_by_role("row").nth(1)).to_contain_text("Iniziale")
        regulation = page.get_by_role("region", name="Regolazione IPA riscaldata", exact=True)
        expect(regulation).to_contain_text("In attesa nella fascia termica", timeout=15000)
        expect(regulation).to_contain_text("Fascia: 16–21 °C")
        page.reload()
        expect(editor.get_by_label("Nuova temperatura minima (°C)")).to_have_value("16")
        expect(history.get_by_role("row")).to_have_count(3)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            page.screenshot(
                path=Path(directory) / f"impostazioni-termiche-{width}.png", full_page=True
            )
        page.get_by_role("button", name="Termina fermentazione", exact=True).click()
        expect(editor.get_by_role("button", name="Salva impostazioni termiche")).to_have_count(0)
        expect(history.get_by_role("row")).to_have_count(3)


@pytest.mark.parametrize("width", [1440, 390])
def test_conflict_validation_save_failure_and_unconfirmed_device_are_visible(
    page: Page, api: httpx.Client, width: int
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(f"{api.base_url}?fermentation={cycle['id']}")
        editor = page.get_by_role("region", name="Impostazioni termiche", exact=True)
        low = editor.get_by_label("Nuova temperatura minima (°C)")
        expect(low).to_have_value("18")
        low.fill("19")
        path = f"/api/fermentations/{cycle['id']}/thermal-settings"
        api.patch(
            path,
            json={
                "expected_revision": 0,
                "temperature_min": 16,
                "temperature_max": 21,
                "hysteresis": 1,
            },
        ).raise_for_status()
        expect(editor.get_by_label("Valori termici salvati")).to_contain_text(
            "Revisione 1", timeout=15000
        )
        expect(low).to_have_value("19")
        with page.expect_response(
            lambda response: (
                response.request.method == "PATCH" and response.url.endswith("/thermal-settings")
            )
        ) as conflict_response:
            editor.get_by_role("button", name="Salva impostazioni termiche").click()
        assert conflict_response.value.status == 409
        expect(editor.get_by_text("La bozza è conservata", exact=False)).to_be_visible()
        editor.get_by_role("button", name="Carica impostazioni salvate").click()
        expect(low).to_have_value("16")
        low.fill("24")
        editor.get_by_role("button", name="Salva impostazioni termiche").click()
        expect(editor.get_by_role("alert")).to_contain_text("Minimo inferiore al massimo")
        assert api.get(path + "/history").json()["fermentation"]["thermal_settings_revision"] == 1
        low.fill("15")
        page.route(
            "**/thermal-settings",
            lambda route: route.fulfill(status=503, json={"detail": "Salvataggio non confermato."}),
        )
        editor.get_by_role("button", name="Salva impostazioni termiche").click()
        expect(editor.get_by_role("alert")).to_contain_text("Salvataggio non confermato")
        expect(editor.get_by_label("Valori termici salvati")).to_contain_text("Revisione 1")
        assert len(api.get(path + "/history").json()["history"]) == 2
        page.unroute("**/thermal-settings")
        editor.get_by_role("button", name="Salva impostazioni termiche").click()
        expect(editor.get_by_label("Valori termici salvati")).to_contain_text("Revisione 2")
        expect(editor.get_by_role("button", name="Salva impostazioni termiche")).to_be_enabled()
        regulation = page.get_by_role("region", name="Regolazione IPA riscaldata", exact=True)
        expect(regulation).to_contain_text("Fascia: 15–21 °C", timeout=15000)
        page.route("**/thermal-settings/history", lambda route: route.fulfill(status=503))
        editor.get_by_role("button", name="Carica impostazioni salvate").click()
        expect(editor.get_by_role("alert")).to_contain_text("recuperare la cronologia")
        page.unroute("**/thermal-settings/history")
        editor.get_by_role("button", name="Riprova cronologia").click()
        expect(editor.get_by_role("alert")).to_have_count(0)
        simulator.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        low.fill("20")
        editor.get_by_role("button", name="Salva impostazioni termiche").click()
        expect(editor.get_by_label("Valori termici salvati")).to_contain_text("Revisione 3")
        regulation = page.get_by_role("region", name="Regolazione IPA riscaldata", exact=True)
        expect(regulation).to_contain_text("Effettivo: Sconosciuto", timeout=15000)
        expect(regulation).to_contain_text("Regolazione sospesa")
        simulator.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        expect(regulation).to_contain_text("Riscaldamento attivo", timeout=15000)


@pytest.mark.parametrize("intervening_action", ["newer_revision", "end"])
def test_delayed_save_response_cannot_replace_newer_settings_or_reopen_end(
    page: Page, api: httpx.Client, intervening_action: str
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        page.goto(f"{api.base_url}?fermentation={cycle['id']}")
        editor = page.get_by_role("region", name="Impostazioni termiche", exact=True)
        low = editor.get_by_label("Nuova temperatura minima (°C)")
        expect(low).to_have_value("18")
        held: list[tuple[Route, APIResponse]] = []

        def delay_response(route: Route) -> None:
            held.append((route, route.fetch()))

        page.route("**/thermal-settings", delay_response)
        low.fill("16")
        with page.expect_request(
            lambda request: request.method == "PATCH" and request.url.endswith("/thermal-settings")
        ):
            editor.get_by_role("button", name="Salva impostazioni termiche").click()
        # The request has persisted; its response remains held at the browser boundary.
        expect(editor.get_by_label("Valori termici salvati")).to_contain_text(
            "Revisione 1", timeout=15000
        )
        assert len(held) == 1
        path = f"/api/fermentations/{cycle['id']}"
        if intervening_action == "newer_revision":
            api.patch(
                path + "/thermal-settings",
                json={
                    "expected_revision": 1,
                    "temperature_min": 20,
                    "temperature_max": 25,
                    "hysteresis": 1,
                },
            ).raise_for_status()
            expect(editor.get_by_label("Valori termici salvati")).to_contain_text(
                "Revisione 2", timeout=15000
            )
        else:
            api.post(path + "/end").raise_for_status()
            expect(
                page.get_by_role("heading", name="Storico: IPA riscaldata", exact=True)
            ).to_be_visible(timeout=15000)
        route, response = held[0]
        route.fulfill(response=response)
        expect(
            editor.get_by_text(
                "Esiste una revisione più recente o la fermentazione è conclusa.", exact=False
            )
        ).to_be_visible()
        if intervening_action == "newer_revision":
            expect(editor.get_by_label("Valori termici salvati")).to_contain_text("Revisione 2")
            expect(editor.get_by_label("Valori termici salvati")).to_contain_text("20–25 °C")
        else:
            expect(editor.get_by_role("button", name="Salva impostazioni termiche")).to_have_count(
                0
            )

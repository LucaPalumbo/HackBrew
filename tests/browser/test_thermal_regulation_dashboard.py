import os
from contextlib import ExitStack
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.heating import temperature
from tests.thermal import thermal_simulator
from tests.thermal_regulation import register_thermal


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
@pytest.mark.parametrize("mode", ["cooling", "heating_cooling", "combined"])
def test_select_compatible_devices_and_observe_full_shutdown(
    page: Page, api: httpx.Client, mode: str, width: int, height: int
) -> None:
    with ExitStack() as stack:
        simulators = {
            capability: stack.enter_context(thermal_simulator(capability))
            for capability in ("heating", "cooling", "both")
        }
        devices = {
            capability: register_thermal(api, simulator, capability)
            for capability, simulator in simulators.items()
        }
        pill = api.get("/api/pills").json()["pills"][0]
        name = f"IPA {mode}"
        page.set_viewport_size({"width": width, "height": height})
        page.goto(str(api.base_url))
        page.get_by_label("Nome della fermentazione", exact=True).fill(name)
        page.get_by_label("Pillola della fermentazione", exact=True).select_option(pill["id"])
        page.get_by_label("Modalità della fermentazione", exact=True).select_option(mode)
        if mode == "heating_cooling":
            field = page.get_by_label("Dispositivo di riscaldamento", exact=True)
            expect(field.get_by_role("option")).to_have_text(
                ["Scegli un dispositivo", devices["heating"]["name"]]
            )
            field.select_option(devices["heating"]["id"])
        else:
            expect(page.get_by_label("Dispositivo di riscaldamento", exact=True)).to_have_count(0)
        if mode != "combined":
            field = page.get_by_label("Dispositivo di raffreddamento", exact=True)
            expect(field.get_by_role("option")).to_have_text(
                ["Scegli un dispositivo", devices["cooling"]["name"]]
            )
            field.select_option(devices["cooling"]["id"])
            active = simulators["cooling"]
            device = devices["cooling"]
            expect(page.get_by_label("Dispositivo combinato", exact=True)).to_have_count(0)
        else:
            expect(page.get_by_label("Dispositivo di raffreddamento", exact=True)).to_have_count(0)
            field = page.get_by_label("Dispositivo combinato", exact=True)
            expect(field.get_by_role("option")).to_have_text(
                ["Scegli un dispositivo", devices["both"]["name"]]
            )
            field.select_option(devices["both"]["id"])
            active = simulators["both"]
            device = devices["both"]
        page.get_by_label("Temperatura minima (°C)", exact=True).fill("22")
        page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("Minimo")
        assert api.get("/api/fermentations/active").json()["fermentations"] == []
        page.get_by_label("Temperatura minima (°C)", exact=True).fill("18")
        page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
        expect(page.get_by_role("status", name="Esito operazione", exact=True)).to_contain_text(
            "avviata"
        )
        temperature(api, 23)
        page.get_by_role("button", name=f"Apri {name}").click()
        regulation = page.get_by_role("region", name=f"Regolazione {name}", exact=True)
        expect(regulation).to_contain_text("Raffreddamento attivo", timeout=15000)
        node = regulation.get_by_role("region", name=f"Stato {device['name']}", exact=True)
        expect(node).to_contain_text("Effettivo: Raffreddamento")
        if mode == "heating_cooling":
            expect(
                regulation.get_by_role(
                    "region", name=f"Stato {devices['heating']['name']}", exact=True
                )
            ).to_contain_text("Effettivo: Spento")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            page.screenshot(
                path=Path(directory) / f"termoregolazione-{mode}-{width}.png", full_page=True
            )
        active.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        page.get_by_role("button", name="Termina fermentazione", exact=True).click()
        expect(regulation).to_contain_text("Spegnimento in attesa di conferma")
        expect(node).to_contain_text("Effettivo: Sconosciuto")
        expect(node).to_contain_text("Dispositivo ancora riservato")
        active.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        expect(regulation).to_contain_text("Spegnimento confermato", timeout=15000)
        expect(node).to_contain_text("Assegnazione rilasciata")
        page.reload()
        expect(regulation).to_contain_text("Spegnimento confermato")

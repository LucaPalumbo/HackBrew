import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.heating import temperature
from tests.thermal import thermal_simulator


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_create_heat_and_end_with_truthful_pending_shutdown(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    with thermal_simulator("heating") as simulator:
        device = api.post(
            "/api/thermal-devices",
            json={
                "name": "Fascia IPA",
                "capability": "heating",
                "base_url": str(simulator.base_url),
            },
        ).json()["device"]
        pill = api.get("/api/pills").json()["pills"][0]
        page.set_viewport_size({"width": width, "height": height})
        page.goto(str(api.base_url))
        page.get_by_label("Nome della fermentazione", exact=True).fill("IPA riscaldata")
        page.get_by_label("Pillola della fermentazione", exact=True).select_option(pill["id"])
        page.get_by_label("Modalità della fermentazione", exact=True).select_option("heating")
        page.get_by_label("Dispositivo di riscaldamento", exact=True).select_option(device["id"])
        page.get_by_label("Temperatura minima (°C)", exact=True).fill("18")
        page.get_by_label("Temperatura massima (°C)", exact=True).fill("22")
        page.get_by_label("Isteresi (°C)", exact=True).fill("0.5")
        page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
        expect(page.get_by_role("status", name="Esito operazione", exact=True)).to_contain_text(
            "avviata"
        )
        temperature(api, 17)
        page.get_by_role("button", name="Apri IPA riscaldata").click()
        regulation = page.get_by_role("region", name="Regolazione IPA riscaldata", exact=True)
        expect(regulation).to_contain_text("Riscaldamento attivo", timeout=15000)
        expect(regulation).to_contain_text("Fascia: 18–22 °C")
        expect(regulation).to_contain_text("Isteresi: 0,5 °C")
        expect(regulation).to_contain_text("Richiesto: Riscaldamento")
        expect(regulation).to_contain_text("Effettivo: Riscaldamento")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            page.screenshot(path=Path(directory) / f"riscaldamento-{width}.png", full_page=True)
        simulator.patch(
            "/__simulation", json={"state_http_status": 503, "control_http_status": 503}
        ).raise_for_status()
        expect(regulation).to_contain_text("Regolazione sospesa", timeout=15000)
        expect(regulation).to_contain_text("Effettivo: Sconosciuto")
        page.get_by_role("button", name="Termina fermentazione", exact=True).click()
        expect(
            page.get_by_role("heading", name="Storico: IPA riscaldata", exact=True)
        ).to_be_visible()
        expect(regulation).to_contain_text("Spegnimento in attesa di conferma")
        expect(regulation).to_contain_text("Dispositivo ancora riservato")
        simulator.patch(
            "/__simulation", json={"state_http_status": 200, "control_http_status": 200}
        ).raise_for_status()
        expect(regulation).to_contain_text("Spegnimento confermato", timeout=15000)
        expect(regulation).to_contain_text("Assegnazione rilasciata")
        page.reload()
        expect(regulation).to_contain_text("Spegnimento confermato")

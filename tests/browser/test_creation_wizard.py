"""Create real fermentations through the guided browser workflow."""

import os
import time
from contextlib import suppress
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import APIResponse, Page, Route, expect
from playwright.sync_api import Error as PlaywrightError

from tests.payloads import gateway_lettura
from tests.thermal import thermal_simulator
from tests.thermal_regulation import register_thermal, thermal_cycle


def screenshot(page: Page, stage: str, width: int) -> None:
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=Path(directory) / f"wizard-{stage}-{width}.png", full_page=True)


@pytest.mark.parametrize("width", [1440, 390])
def test_monitoring_wizard_preserves_choices_and_starts_only_from_review(
    page: Page, api: httpx.Client, width: int
) -> None:
    pill = api.get("/api/pills").json()["pills"][0]
    api.post("/telemetry", json=gateway_lettura()).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=new")
    expect(page.get_by_role("heading", name="Nome e pillola", exact=True)).to_be_visible()
    expect(page.get_by_label("Modalità della fermentazione", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Avvia fermentazione", exact=True)).to_have_count(0)
    page.get_by_label("Nome della fermentazione", exact=True).fill("IPA guidata")
    page.get_by_label("Pillola della fermentazione", exact=True).select_option(pill["id"])
    screenshot(page, "identita", width)
    page.get_by_role("button", name="Avanti", exact=True).click()
    expect(page.get_by_role("heading", name="Regolazione", exact=True)).to_be_visible()
    expect(page.get_by_label("Modalità della fermentazione", exact=True)).to_have_value(
        "monitor_only"
    )
    expect(page.get_by_label("Temperatura minima (°C)", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Indietro", exact=True).click()
    expect(page.get_by_label("Nome della fermentazione", exact=True)).to_have_value("IPA guidata")
    expect(page.get_by_label("Pillola della fermentazione", exact=True)).to_have_value(pill["id"])
    page.get_by_role("button", name="Avanti", exact=True).click()
    page.get_by_role("button", name="Avanti", exact=True).click()
    summary = page.get_by_role("region", name="Riepilogo della fermentazione", exact=True)
    expect(summary).to_contain_text("IPA guidata")
    expect(summary).to_contain_text(pill["mac"])
    expect(summary).to_contain_text("Solo monitoraggio")
    screenshot(page, "riepilogo", width)
    assert api.get("/api/fermentations/active").json()["fermentations"] == []
    assert api.get("/api/pills").json()["pills"][0]["available"] is True
    with page.expect_response(
        lambda response: (
            response.request.method == "POST" and response.url.endswith("/api/fermentations")
        )
    ) as creation:
        page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
    assert creation.value.status == 201
    assert creation.value.request.post_data_json == {
        "name": "IPA guidata",
        "pill_id": pill["id"],
        "control_mode": "monitor_only",
    }
    cycle = creation.value.json()["fermentation"]
    expect(page).to_have_url(f"{str(api.base_url).rstrip('/')}/?fermentation={cycle['id']}")
    expect(page.get_by_role("tab", name="Andamento", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.get_by_role("status", name="Esito operazione", exact=True)).to_contain_text(
        "avviata"
    )
    expect(
        page.get_by_role("heading", name="In attesa della prima lettura della fermentazione")
    ).to_be_visible()
    expect(page.get_by_role("region", name="Densità", exact=True)).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
def test_thermal_choices_validate_the_inclusive_band_and_cancel_without_reserving(
    page: Page, api: httpx.Client, width: int
) -> None:
    with thermal_simulator("heating") as simulator:
        device = register_thermal(api, simulator, "heating")
        pill = api.get("/api/pills").json()["pills"][0]
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(f"{api.base_url}?page=new")
        page.get_by_label("Nome della fermentazione", exact=True).fill("IPA corretta")
        page.get_by_label("Pillola della fermentazione", exact=True).select_option(pill["id"])
        page.get_by_role("button", name="Avanti", exact=True).click()
        page.get_by_label("Modalità della fermentazione", exact=True).select_option("heating")
        page.get_by_label("Dispositivo di riscaldamento", exact=True).select_option(device["id"])
        for invalid in ("", "0", "4.01"):
            page.get_by_label("Isteresi (°C)", exact=True).fill(invalid)
            page.get_by_role("button", name="Avanti", exact=True).click()
            expect(page.get_by_role("alert")).to_contain_text("isteresi positiva")
            expect(page.get_by_role("heading", name="Regolazione", exact=True)).to_be_visible()
        page.get_by_label("Isteresi (°C)", exact=True).fill("4")
        page.get_by_role("button", name="Avanti", exact=True).click()
        summary = page.get_by_role("region", name="Riepilogo della fermentazione", exact=True)
        expect(summary).to_contain_text(device["name"])
        expect(summary).to_contain_text("18–22 °C")
        expect(summary).to_contain_text("4 °C")
        page.get_by_role("button", name="Indietro", exact=True).click()
        expect(page.get_by_label("Isteresi (°C)", exact=True)).to_have_value("4")
        expect(page.get_by_label("Dispositivo di riscaldamento", exact=True)).to_have_value(
            device["id"]
        )
        screenshot(page, "regolazione", width)
        page.get_by_role("button", name="Avanti", exact=True).click()
        page.get_by_role("button", name="Annulla", exact=True).click()
        expect(page).to_have_url(str(api.base_url).rstrip("/") + "/")
        assert api.get("/api/fermentations/active").json()["fermentations"] == []
        assert api.get("/api/pills").json()["pills"][0]["available"] is True
        assert api.get("/api/thermal-devices").json()["devices"][0]["available"] is True
        page.get_by_role("link", name="Nuova fermentazione", exact=True).first.click()
        expect(page.get_by_label("Nome della fermentazione", exact=True)).to_have_value("")
        expect(page.get_by_label("Pillola della fermentazione", exact=True)).to_have_value("")


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("final_mode", ["monitor_only", "heating"])
def test_switching_modes_sends_only_the_final_configuration(
    page: Page, api: httpx.Client, width: int, final_mode: str
) -> None:
    with thermal_simulator("heating") as simulator:
        device = register_thermal(api, simulator, "heating")
        pill = api.get("/api/pills").json()["pills"][0]
        # The real contract accepts names beyond the prototype's old length limit.
        name = "IPA " * 30
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(f"{api.base_url}?page=new")
        page.get_by_label("Nome della fermentazione", exact=True).fill(name)
        page.get_by_label("Pillola della fermentazione", exact=True).select_option(pill["id"])
        page.get_by_role("button", name="Avanti", exact=True).click()
        mode = page.get_by_label("Modalità della fermentazione", exact=True)
        mode.select_option("heating")
        page.get_by_label("Dispositivo di riscaldamento", exact=True).select_option(device["id"])
        page.get_by_label("Isteresi (°C)", exact=True).fill("4")
        mode.select_option("monitor_only")
        expect(page.get_by_label("Temperatura minima (°C)", exact=True)).to_have_count(0)
        expect(page.get_by_label("Dispositivo di riscaldamento", exact=True)).to_have_count(0)
        mode.select_option(final_mode)
        if final_mode == "heating":
            expect(page.get_by_label("Dispositivo di riscaldamento", exact=True)).to_have_value(
                device["id"]
            )
            expect(page.get_by_label("Isteresi (°C)", exact=True)).to_have_value("4")
        page.get_by_role("button", name="Avanti", exact=True).click()
        expected = {"name": name.strip(), "pill_id": pill["id"], "control_mode": final_mode}
        if final_mode == "heating":
            expected.update(
                heater_id=device["id"], temperature_min=18, temperature_max=22, hysteresis=4
            )
        with page.expect_response(
            lambda response: (
                response.request.method == "POST" and response.url.endswith("/api/fermentations")
            )
        ) as creation:
            page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
        assert creation.value.status == 201
        assert creation.value.request.post_data_json == expected
        cycle = creation.value.json()["fermentation"]
        expect(page).to_have_url(f"{str(api.base_url).rstrip('/')}/?fermentation={cycle['id']}")
        registered = api.get("/api/thermal-devices").json()["devices"][0]
        assert registered["available"] is (final_mode == "monitor_only")
        assert registered["reserved_fermentation_id"] == (
            cycle["id"] if final_mode == "heating" else None
        )
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("failure", ["validation", "unavailable", "network"])
def test_failed_start_preserves_review_and_can_be_retried(
    page: Page, api: httpx.Client, width: int, failure: str
) -> None:
    pill = api.get("/api/pills").json()["pills"][0]
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=new")
    page.get_by_label("Nome della fermentazione", exact=True).fill("IPA da riprovare")
    page.get_by_label("Pillola della fermentazione", exact=True).select_option(pill["id"])
    page.get_by_role("button", name="Avanti", exact=True).click()
    page.get_by_role("button", name="Avanti", exact=True).click()

    def fail_start(route: Route) -> None:
        if route.request.method != "POST":
            route.continue_()
        elif failure == "validation":
            route.fulfill(status=422, json={"detail": [{"msg": "Configurazione non valida"}]})
        elif failure == "unavailable":
            route.fulfill(status=503, json={"detail": "Archivio temporaneamente non disponibile"})
        else:
            route.abort("connectionfailed")

    page.route("**/api/fermentations", fail_start)
    page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
    expected_error = {
        "validation": "Configurazione non valida",
        "unavailable": "Archivio temporaneamente non disponibile",
        "network": "Non è stato possibile confermare l’avvio",
    }[failure]
    expect(page.get_by_role("alert")).to_contain_text(expected_error)
    expect(page.get_by_role("region", name="Riepilogo della fermentazione")).to_contain_text(
        "IPA da riprovare"
    )
    expect(page.get_by_role("status", name="Esito operazione", exact=True)).to_have_count(0)
    assert api.get("/api/fermentations/active").json()["fermentations"] == []
    assert api.get("/api/pills").json()["pills"][0]["available"] is True
    page.unroute("**/api/fermentations", fail_start)
    page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
    expect(
        page.get_by_role("heading", name="Dettaglio: IPA da riprovare", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("tab", name="Andamento", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    assert len(api.get("/api/fermentations/active").json()["fermentations"]) == 1


@pytest.mark.parametrize("width", [1440, 390])
def test_concurrent_device_reservation_keeps_choices_and_allows_correction(
    page: Page, api: httpx.Client, width: int
) -> None:
    with thermal_simulator("heating") as first, thermal_simulator("heating-secondary") as second:
        occupied = register_thermal(api, first, "heating")
        spare = register_thermal(api, second, "heating")
        pill = api.get("/api/pills").json()["pills"][0]
        other_pill = api.post(
            "/api/pills", json={"name": "Altra pillola", "mac": "11:22:33:44:55:66"}
        ).json()["pill"]
        page.set_viewport_size({"width": width, "height": 1000})
        page.goto(f"{api.base_url}?page=new")
        page.get_by_label("Nome della fermentazione", exact=True).fill("IPA da conservare")
        page.get_by_label("Pillola della fermentazione", exact=True).select_option(pill["id"])
        page.get_by_role("button", name="Avanti", exact=True).click()
        page.get_by_label("Modalità della fermentazione", exact=True).select_option("heating")
        page.get_by_label("Dispositivo di riscaldamento", exact=True).select_option(occupied["id"])
        page.get_by_label("Temperatura minima (°C)", exact=True).fill("17")
        page.get_by_label("Temperatura massima (°C)", exact=True).fill("21")
        page.get_by_label("Isteresi (°C)", exact=True).fill("1.5")
        page.get_by_role("button", name="Avanti", exact=True).click()
        competitors = []

        def competing_start(route: Route) -> None:
            if route.request.method == "POST":
                competitors.append(
                    thermal_cycle(api, "heating", {"heater": occupied}, other_pill["id"])
                )
            route.continue_()

        page.route("**/api/fermentations", competing_start)
        with page.expect_response(
            lambda response: (
                response.request.method == "POST" and response.url.endswith("/api/fermentations")
            )
        ) as conflict:
            page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
        assert conflict.value.status == 409
        expect(page.get_by_role("alert")).to_contain_text("riservato")
        expect(page.get_by_role("status", name="Esito operazione", exact=True)).to_have_count(0)
        summary = page.get_by_role("region", name="Riepilogo della fermentazione", exact=True)
        expect(summary).to_contain_text("IPA da conservare")
        expect(summary).to_contain_text("17–21 °C")
        expect(summary).to_contain_text("1.5 °C")
        page.unroute("**/api/fermentations", competing_start)
        page.get_by_role("button", name="Indietro", exact=True).click()
        expect(page.get_by_label("Modalità della fermentazione", exact=True)).to_have_value(
            "heating"
        )
        expect(page.get_by_label("Isteresi (°C)", exact=True)).to_have_value("1.5")
        field = page.get_by_label("Dispositivo di riscaldamento", exact=True)
        expect(field).to_have_value(occupied["id"])
        expect(field.locator(f'option[value="{occupied["id"]}"]')).to_be_disabled()
        field.select_option(spare["id"])
        page.get_by_role("button", name="Indietro", exact=True).click()
        expect(page.get_by_label("Nome della fermentazione", exact=True)).to_have_value(
            "IPA da conservare"
        )
        expect(page.get_by_label("Pillola della fermentazione", exact=True)).to_have_value(
            pill["id"]
        )
        page.get_by_role("button", name="Avanti", exact=True).click()
        page.get_by_role("button", name="Avanti", exact=True).click()
        page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
        expect(
            page.get_by_role("heading", name="Dettaglio: IPA da conservare", exact=True)
        ).to_be_visible()
        active = api.get("/api/fermentations/active").json()["fermentations"]
        assert len(active) == 2
        created = next(cycle for cycle in active if cycle["name"] == "IPA da conservare")
        assert created["pill_id"] == pill["id"]
        assert created["heater_id"] == spare["id"]
        assert created["temperature_min"] == 17
        assert created["temperature_max"] == 21
        assert created["hysteresis"] == 1.5
        devices = {
            device["id"]: device for device in api.get("/api/thermal-devices").json()["devices"]
        }
        assert devices[occupied["id"]]["reserved_fermentation_id"] == competitors[0]["id"]
        assert devices[spare["id"]]["reserved_fermentation_id"] == created["id"]


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("leave", [False, True])
def test_pending_start_cannot_be_repeated_or_override_later_navigation(
    page: Page, api: httpx.Client, width: int, leave: bool
) -> None:
    pill = api.get("/api/pills").json()["pills"][0]
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=new")
    page.get_by_label("Nome della fermentazione", exact=True).fill("IPA risposta lenta")
    page.get_by_label("Pillola della fermentazione", exact=True).select_option(pill["id"])
    page.get_by_role("button", name="Avanti", exact=True).click()
    page.get_by_role("button", name="Avanti", exact=True).click()
    held: list[tuple[Route, APIResponse]] = []

    def hold_response(route: Route) -> None:
        if route.request.method == "POST":
            held.append((route, route.fetch()))
        else:
            route.continue_()

    page.route("**/api/fermentations", hold_response)
    page.get_by_role("button", name="Avvia fermentazione", exact=True).dblclick()
    deadline = time.monotonic() + 10
    while not held and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    assert len(held) == 1
    route, response = held[0]
    try:
        assert response.status == 201
        expect(page.get_by_role("button", name="Avvio in corso…", exact=True)).to_be_disabled()
        for label in ("Indietro", "Annulla"):
            expect(page.get_by_role("button", name=label, exact=True)).to_be_disabled()
        expect(page.get_by_role("status", name="Esito operazione", exact=True)).to_have_count(0)
        page.keyboard.press("Enter")
        assert len(held) == 1
        cycles = api.get("/api/fermentations/active").json()["fermentations"]
        assert len(cycles) == 1
        assert api.get("/api/pills").json()["pills"][0]["available"] is False
        if leave:
            with page.expect_event(
                "requestfailed",
                predicate=lambda request: (
                    request.method == "POST" and request.url.endswith("/api/fermentations")
                ),
            ):
                page.get_by_role("navigation", name="Navigazione principale").get_by_role(
                    "link", name="Home", exact=True
                ).click()
            with suppress(PlaywrightError):
                route.fulfill(response=response)
            expect(page).to_have_url(str(api.base_url).rstrip("/") + "/")
            expect(
                page.get_by_role("heading", name="IPA risposta lenta", exact=True)
            ).to_be_visible()
            expect(page.get_by_role("status", name="Esito operazione", exact=True)).to_have_count(0)
        else:
            route.fulfill(response=response)
            expect(page).to_have_url(
                f"{str(api.base_url).rstrip('/')}/?fermentation={cycles[0]['id']}"
            )
            expect(page.get_by_role("tab", name="Andamento", exact=True)).to_have_attribute(
                "aria-selected", "true"
            )
            expect(page.get_by_role("status", name="Esito operazione", exact=True)).to_contain_text(
                "avviata"
            )
    finally:
        with suppress(PlaywrightError):
            route.abort()

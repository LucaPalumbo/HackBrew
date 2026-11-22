"""Thermal registry management through real desktop and mobile browsers."""

import os
from contextlib import suppress
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import APIResponse, Page, Route, expect
from playwright.sync_api import Error as PlaywrightError

from tests.thermal import thermal_simulator
from tests.thermal_regulation import register_thermal, thermal_cycle, wait_cycle


@pytest.mark.parametrize("width", [1440, 390])
def test_manage_device_and_keep_historic_identity(
    page: Page, api: httpx.Client, width: int
) -> None:
    page.set_viewport_size({"width": width, "height": 1000})
    with thermal_simulator("heating") as simulator:
        page.goto(f"{api.base_url}?page=devices&tab=thermal")
        page.get_by_role("button", name="Aggiungi dispositivo termico", exact=True).click()
        page.get_by_label("Nome del dispositivo termico", exact=True).fill("Fascia IPA")
        page.get_by_label("Funzioni del dispositivo", exact=True).select_option("heating")
        page.get_by_label("Indirizzo HTTP", exact=True).fill(str(simulator.base_url))
        page.get_by_role("button", name="Registra dispositivo termico", exact=True).click()
        card = page.get_by_role("region", name="Dispositivo termico Fascia IPA", exact=True)
        expect(card).to_contain_text("Disponibile")
        card.get_by_role("button", name="Verifica collegamento", exact=True).click()
        expect(card).to_contain_text("Spento confermato")
        device = api.get("/api/thermal-devices").json()["devices"][0]
        cycle = thermal_cycle(api, "heating", {"heater": device})
        wait_cycle(api, cycle, lambda current: current["regulation"]["actual_mode"] == "off")
        expect(card.get_by_role("button", name="Modifica", exact=True)).to_be_disabled()
        expect(card.get_by_role("link", name=cycle["name"], exact=True)).to_be_visible()
        simulator.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
        expect(card.get_by_role("button", name="Rimuovi", exact=True)).to_be_disabled()
        simulator.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        wait_cycle(api, cycle, lambda current: not current["thermal_reserved"])
        expect(card.get_by_role("button", name="Modifica", exact=True)).to_be_enabled()
        card.get_by_role("button", name="Modifica", exact=True).click()
        editor = page.get_by_role("region", name="Modifica dispositivo termico", exact=True)
        expect(editor.get_by_label("Funzioni del dispositivo", exact=True)).to_be_disabled()
        editor.get_by_label("Nome del dispositivo termico", exact=True).fill("Fascia nuova")
        editor.get_by_label("Indirizzo HTTP", exact=True).fill("http://thermal-heating:1")
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            page.screenshot(path=Path(directory) / f"gestione-termici-{width}.png", full_page=True)
        editor.get_by_role("button", name="Salva modifiche", exact=True).click()
        current = page.get_by_role("region", name="Dispositivo termico Fascia nuova", exact=True)
        expect(current).to_contain_text("Non verificato")
        expect(current).to_contain_text("Stato sconosciuto")
        expect(current).not_to_contain_text("Spento confermato")
        page.reload()
        expect(current).to_contain_text("http://thermal-heating:1")
        current.get_by_role("button", name="Rimuovi", exact=True).click()
        dialog = page.get_by_role("dialog", name="Rimuovi dispositivo termico", exact=True)
        dialog.get_by_role("button", name="Annulla", exact=True).click()
        expect(current.get_by_role("button", name="Rimuovi", exact=True)).to_be_focused()
        current.get_by_role("button", name="Rimuovi", exact=True).click()
        dialog.get_by_role("button", name="Rimuovi dispositivo", exact=True).click()
        expect(current).to_have_count(0)
        expect(page.get_by_role("status", name="Esito registro termico")).to_contain_text("rimosso")
        page.goto(f"{api.base_url}?fermentation={cycle['id']}&tab=management")
        expect(page.get_by_role("region", name="Associazioni della fermentazione")).to_contain_text(
            "Fascia IPA"
        )
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("remove", [False, True])
def test_late_reservation_preserves_the_draft_and_allows_retry_after_off(
    page: Page,
    api: httpx.Client,
    width: int,
    remove: bool,
) -> None:
    page.set_viewport_size({"width": width, "height": 1000})
    with thermal_simulator("heating") as simulator:
        device = register_thermal(api, simulator, "heating")
        page.goto(f"{api.base_url}?page=devices&tab=thermal")
        card = page.get_by_role("region", name=f"Dispositivo termico {device['name']}", exact=True)
        card.get_by_role("button", name="Rimuovi" if remove else "Modifica", exact=True).click()
        surface = page.get_by_role(
            "dialog" if remove else "region",
            name="Rimuovi dispositivo termico" if remove else "Modifica dispositivo termico",
            exact=True,
        )
        if not remove:
            surface.get_by_label("Nome del dispositivo termico", exact=True).fill(
                "Bozza conservata"
            )
        cycles = []

        def reserve(route: Route) -> None:
            if route.request.method == ("DELETE" if remove else "PATCH"):
                cycles.append(thermal_cycle(api, "heating", {"heater": device}))
            route.continue_()

        url = f"**/api/thermal-devices/{device['id']}"
        page.route(url, reserve)
        button = surface.get_by_role(
            "button", name="Rimuovi dispositivo" if remove else "Salva modifiche", exact=True
        )
        button.click()
        expect(surface.get_by_role("alert")).to_contain_text("riservato")
        expect(page.get_by_role("status", name="Esito registro termico")).to_have_count(0)
        if not remove:
            expect(surface.get_by_label("Nome del dispositivo termico", exact=True)).to_have_value(
                "Bozza conservata"
            )
        expect(button).to_be_disabled()
        page.unroute(url, reserve)
        api.post(f"/api/fermentations/{cycles[0]['id']}/end").raise_for_status()
        wait_cycle(api, cycles[0], lambda current: not current["thermal_reserved"])
        expect(button).to_be_enabled()
        button.click()
        expect(page.get_by_role("status", name="Esito registro termico")).to_contain_text(
            "rimosso" if remove else "aggiornato"
        )


@pytest.mark.parametrize("action", ["register", "edit", "remove"])
@pytest.mark.parametrize("failure", ["503", "network"])
def test_failed_mutations_keep_the_form_and_never_show_success(
    page: Page,
    api: httpx.Client,
    action: str,
    failure: str,
) -> None:
    page.set_viewport_size({"width": 390, "height": 1000})
    with thermal_simulator("heating") as simulator:
        device = None if action == "register" else register_thermal(api, simulator, "heating")
        page.goto(f"{api.base_url}?page=devices&tab=thermal")
        if action == "register":
            page.get_by_role("button", name="Aggiungi dispositivo termico", exact=True).click()
            page.get_by_label("Nome del dispositivo termico", exact=True).fill("Nuova fascia")
            page.get_by_label("Indirizzo HTTP", exact=True).fill(str(simulator.base_url))
        else:
            page.get_by_role(
                "button", name="Rimuovi" if action == "remove" else "Modifica", exact=True
            ).click()
        removing = action == "remove"
        surface = page.get_by_role(
            "dialog" if removing else "region",
            name="Rimuovi dispositivo termico"
            if removing
            else "Registrazione dispositivo termico"
            if action == "register"
            else "Modifica dispositivo termico",
            exact=True,
        )
        method = {"register": "POST", "edit": "PATCH", "remove": "DELETE"}[action]

        def fail(route: Route) -> None:
            if route.request.method != method:
                route.continue_()
            elif failure == "network":
                route.abort()
            else:
                route.fulfill(
                    status=503, json={"detail": "Archivio temporaneamente non disponibile."}
                )

        pattern = "**/api/thermal-devices**"
        page.route(pattern, fail)
        button = surface.get_by_role(
            "button",
            name={
                "register": "Registra dispositivo termico",
                "edit": "Salva modifiche",
                "remove": "Rimuovi dispositivo",
            }[action],
            exact=True,
        )
        button.click()
        expect(surface.get_by_role("alert")).to_be_visible()
        expect(page.get_by_role("status", name="Esito registro termico")).to_have_count(0)
        assert len(api.get("/api/thermal-devices").json()["devices"]) == (
            0 if device is None else 1
        )
        expect(button).to_be_enabled()
        page.unroute(pattern, fail)
        button.click()
        expect(page.get_by_role("status", name="Esito registro termico")).to_be_visible()


@pytest.mark.parametrize("remove", [False, True])
@pytest.mark.parametrize("leave", [False, True])
def test_mutation_waits_for_ack_guards_repeated_submit_and_survives_navigation(
    page: Page,
    api: httpx.Client,
    remove: bool,
    leave: bool,
) -> None:
    with thermal_simulator("heating") as simulator:
        device = register_thermal(api, simulator, "heating")
        page.goto(f"{api.base_url}?page=devices&tab=thermal")
        page.get_by_role("button", name="Rimuovi" if remove else "Modifica", exact=True).click()
        surface = page.get_by_role(
            "dialog" if remove else "region",
            name="Rimuovi dispositivo termico" if remove else "Modifica dispositivo termico",
            exact=True,
        )
        if not remove:
            surface.get_by_label("Nome del dispositivo termico", exact=True).fill("Salvato davvero")
        pending: list[tuple[Route, APIResponse]] = []

        def hold(route: Route) -> None:
            if route.request.method == ("DELETE" if remove else "PATCH"):
                pending.append((route, route.fetch()))
            else:
                route.continue_()

        page.route(f"**/api/thermal-devices/{device['id']}", hold)
        surface.get_by_role(
            "button", name="Rimuovi dispositivo" if remove else "Salva modifiche", exact=True
        ).click()
        expect(surface.get_by_role("button", name="Annulla", exact=True)).to_be_disabled()
        expect(page.get_by_role("status", name="Esito registro termico")).to_have_count(0)
        if not remove:
            surface.locator("form").dispatch_event("submit")
        else:
            surface.get_by_role("button", name="Operazione in corso…", exact=True).dispatch_event(
                "click"
            )
        assert len(pending) == 1
        if leave:
            page.goto(f"{api.base_url}?page=home")
        route, response = pending[0]
        with suppress(PlaywrightError):
            route.fulfill(response=response)
        if leave:
            expect(page.get_by_role("status", name="Esito registro termico")).to_have_count(0)
            page.goto(f"{api.base_url}?page=devices&tab=thermal")
        else:
            expect(page.get_by_role("status", name="Esito registro termico")).to_be_visible()
        if remove:
            expect(
                page.get_by_role("region", name=f"Dispositivo termico {device['name']}", exact=True)
            ).to_have_count(0)
        else:
            expect(
                page.get_by_role("region", name="Dispositivo termico Salvato davvero", exact=True)
            ).to_be_visible()


def test_invalid_and_duplicate_address_edits_keep_the_original_until_corrected(
    page: Page, api: httpx.Client
) -> None:
    page.set_viewport_size({"width": 390, "height": 1000})
    devices = [
        api.post(
            "/api/thermal-devices",
            json={
                "name": name,
                "capability": "heating",
                "base_url": url,
            },
        ).json()["device"]
        for name, url in (
            ("Fascia originale", "http://first.local"),
            ("Altro", "http://duplicate.local"),
        )
    ]
    page.goto(f"{api.base_url}?page=devices&tab=thermal")
    card = page.get_by_role("region", name="Dispositivo termico Fascia originale", exact=True)
    card.get_by_role("button", name="Modifica", exact=True).click()
    editor = page.get_by_role("region", name="Modifica dispositivo termico", exact=True)
    editor.get_by_label("Nome del dispositivo termico", exact=True).fill("Bozza nuova")
    editor.get_by_label("Indirizzo HTTP", exact=True).fill("http://DUPLICATE.local:80/")
    editor.get_by_role("button", name="Salva modifiche", exact=True).click()
    expect(editor.get_by_role("alert")).to_contain_text("già registrato")
    expect(card).to_contain_text("http://first.local")
    editor.get_by_label("Indirizzo HTTP", exact=True).fill("ftp://first.local")
    editor.get_by_role("button", name="Salva modifiche", exact=True).click()
    expect(editor.get_by_role("alert")).to_contain_text("indirizzo HTTP(S)")
    expect(editor.get_by_label("Nome del dispositivo termico", exact=True)).to_have_value(
        "Bozza nuova"
    )
    assert (
        next(
            d
            for d in api.get("/api/thermal-devices").json()["devices"]
            if d["id"] == devices[0]["id"]
        )["name"]
        == "Fascia originale"
    )
    editor.get_by_label("Indirizzo HTTP", exact=True).fill("https://correct.local")
    editor.get_by_role("button", name="Salva modifiche", exact=True).click()
    expect(
        page.get_by_role("region", name="Dispositivo termico Bozza nuova", exact=True)
    ).to_contain_text("https://correct.local")


@pytest.mark.parametrize("old_connection_fails", [False, True])
def test_delayed_check_ack_cannot_replace_the_new_address_with_the_old_confirmation(
    page: Page, api: httpx.Client, old_connection_fails: bool
) -> None:
    with thermal_simulator("heating") as simulator:
        device = register_thermal(api, simulator, "heating")
        page.goto(f"{api.base_url}?page=devices&tab=thermal")
        held: list[tuple[Route, APIResponse]] = []
        page.route(
            f"**/api/thermal-devices/{device['id']}/check",
            lambda route: held.append((route, route.fetch())),
        )
        card = page.get_by_role("region", name=f"Dispositivo termico {device['name']}", exact=True)
        card.get_by_role("button", name="Verifica collegamento", exact=True).click()
        expect(card.get_by_role("button", name="Verifica in corso…", exact=True)).to_be_disabled()
        card.get_by_role("button", name="Modifica", exact=True).click()
        page.get_by_label("Indirizzo HTTP", exact=True).fill("http://thermal-heating:1")
        page.get_by_role("button", name="Salva modifiche", exact=True).click()
        expect(page.get_by_role("status", name="Esito registro termico")).to_contain_text(
            "aggiornato"
        )
        expect(card).to_contain_text("Non verificato")
        route, response = held[0]
        if old_connection_fails:
            route.abort()
        else:
            route.fulfill(response=response)
        expect(card.get_by_role("button", name="Verifica collegamento", exact=True)).to_be_enabled()
        expect(card).to_contain_text("Stato sconosciuto")
        expect(card).not_to_contain_text("Spento confermato")
        expect(card).not_to_contain_text("Ultima conferma precedente")
        expect(card.get_by_role("alert")).to_have_count(0)

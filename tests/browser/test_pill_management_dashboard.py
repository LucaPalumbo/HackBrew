"""Real registry editing and historic identities through desktop and mobile UI."""

import os
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import APIResponse, Page, Route, expect
from playwright.sync_api import Error as PlaywrightError

from tests.browser.navigation import finish_fermentation
from tests.payloads import gateway_lettura


@pytest.fixture
def api(empty_api: httpx.Client) -> httpx.Client:
    return empty_api


@pytest.mark.parametrize("width", [1440, 390])
def test_register_diagnose_rename_and_confirm_removal_without_losing_history(
    page: Page, empty_api: httpx.Client, width: int
) -> None:
    api = empty_api
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=devices")
    expect(page.get_by_role("tab", name="Pillole", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    page.get_by_role("button", name="Aggiungi pillola", exact=True).click()
    page.get_by_label("Nome della pillola", exact=True).fill("Pillola IPA")
    page.get_by_label("MAC Bluetooth", exact=True).fill("aa-bb-cc-dd-ee-ff")
    page.get_by_role("button", name="Registra pillola", exact=True).click()
    card = page.get_by_role("region", name="Pillola Pillola IPA", exact=True)
    expect(card).to_contain_text("Libera")
    pill = api.get("/api/pills").json()["pills"][0]
    expect(card).to_contain_text("AA:BB:CC:DD:EE:FF")
    expect(card).to_contain_text("Nessuna lettura ricevuta")
    api.post(
        "/telemetry",
        json=gateway_lettura(
            timestamp=datetime.now(UTC).timestamp(), gravity_velocity=-2.5, accel_x=-0.25
        ),
    ).raise_for_status()
    expect(card).to_contain_text("1.050")
    card.get_by_role("link", name="Esplora letture", exact=True).click()
    expect(page).to_have_url(f"{str(api.base_url).rstrip('/')}/?page=diagnostics&pill={pill['id']}")
    expect(page.get_by_label("Pillola diagnostica", exact=True)).to_have_value(pill["id"])
    expect(page.get_by_role("region", name="Velocità densità", exact=True)).to_contain_text("-2,5")
    expect(page.get_by_role("region", name="Accelerazione X", exact=True)).to_contain_text("-0,25")
    assert api.get("/api/fermentations/active").json()["fermentations"] == []
    page.go_back()
    cycle = api.post(
        "/api/fermentations", json={"name": "Birra precedente", "pill_id": pill["id"]}
    ).json()["fermentation"]
    api.post(
        "/telemetry",
        json=gateway_lettura(timestamp=datetime.now(UTC).timestamp(), specific_gravity=1040),
    ).raise_for_status()
    expect(card).to_contain_text("Birra precedente")
    expect(card.get_by_role("button", name="Rinomina", exact=True)).to_be_disabled()
    expect(card.get_by_role("button", name="Rimuovi", exact=True)).to_be_disabled()
    card.get_by_role("link", name="Birra precedente", exact=True).click()
    expect(
        page.get_by_role("heading", name="Dettaglio: Birra precedente", exact=True)
    ).to_be_visible()
    finish_fermentation(page)
    expect(
        page.get_by_role("heading", name="Storico: Birra precedente", exact=True)
    ).to_be_visible()
    page.get_by_role("navigation", name="Navigazione principale").get_by_role(
        "link", name="Dispositivi", exact=True
    ).click()
    card.get_by_role("button", name="Rinomina", exact=True).click()
    expect(page.get_by_label("MAC Bluetooth", exact=True)).to_have_attribute("readonly", "")
    page.get_by_label("Nome della pillola", exact=True).fill("Pillola rinominata")
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        page.screenshot(path=Path(directory) / f"pill-editor-{width}.png", full_page=True)
    page.get_by_role("button", name="Salva nome", exact=True).click()
    card = page.get_by_role("region", name="Pillola Pillola rinominata", exact=True)
    expect(card).to_be_visible()
    page.reload()
    expect(card).to_contain_text("1.040")
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        page.screenshot(path=Path(directory) / f"pill-registry-{width}.png", full_page=True)
    card.get_by_role("button", name="Rimuovi", exact=True).click()
    confirmation = page.get_by_role("dialog", name="Rimuovi pillola", exact=True)
    expect(confirmation).to_contain_text("Pillola rinominata")
    expect(confirmation).to_contain_text("AA:BB:CC:DD:EE:FF")
    confirmation.get_by_role("button", name="Annulla", exact=True).click()
    expect(confirmation).not_to_be_visible()
    expect(card.get_by_role("button", name="Rimuovi", exact=True)).to_be_focused()
    expect(card).to_be_visible()
    assert len(api.get("/api/pills").json()["pills"]) == 1
    card.get_by_role("button", name="Rimuovi", exact=True).click()
    confirmation.get_by_role("button", name="Conferma rimozione", exact=True).click()
    expect(card).to_have_count(0)
    assert api.get("/api/bridge/pills").json()["pills"] == []
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 404
    historical = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
    assert historical["pill_name"] == "Pillola IPA"
    assert historical["pill_mac"] == pill["mac"]
    page.goto(f"{str(api.base_url).rstrip('/')}/?fermentation={cycle['id']}")
    expect(
        page.get_by_role("heading", name="Storico: Birra precedente", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("region", name="Densità", exact=True)).to_contain_text("1.040")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("operation", ["rename", "remove"])
def test_late_assignment_conflict_preserves_editor_or_confirmation_and_allows_retry(
    page: Page, api: httpx.Client, width: int, operation: str
) -> None:
    pill = api.post(
        "/api/pills", json={"name": "Pillola contesa", "mac": "AA:BB:CC:DD:EE:FF"}
    ).json()["pill"]
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=devices")
    card = page.get_by_role("region", name="Pillola Pillola contesa", exact=True)
    if operation == "rename":
        card.get_by_role("button", name="Rinomina", exact=True).click()
        page.get_by_label("Nome della pillola", exact=True).fill("Bozza conservata")
        editor = page.get_by_role("region", name="Rinomina pillola", exact=True)
        action = editor.get_by_role("button", name="Salva nome", exact=True)
    else:
        card.get_by_role("button", name="Rimuovi", exact=True).click()
        editor = page.get_by_role("dialog", name="Rimuovi pillola", exact=True)
        action = editor.get_by_role("button", name="Conferma rimozione", exact=True)
    method = "PATCH" if operation == "rename" else "DELETE"
    competitors: list[str] = []

    def competing_start(route: Route) -> None:
        if route.request.method == method and not competitors:
            response = api.post(
                "/api/fermentations", json={"name": "Avvio concorrente", "pill_id": pill["id"]}
            )
            assert response.status_code == 201
            competitors.append(response.json()["fermentation"]["id"])
        route.continue_()

    page.route("**/api/pills/*", competing_start)
    with page.expect_response(
        lambda response: (
            response.request.method == method and response.url.endswith(f"/api/pills/{pill['id']}")
        )
    ) as conflict:
        action.click()
    assert conflict.value.status == 409
    expect(editor.get_by_role("alert")).to_contain_text("fermentazione attiva")
    expect(editor).to_be_visible()
    expect(page.get_by_role("status", name="Esito registro", exact=True)).to_have_count(0)
    assert api.get("/api/pills").json()["pills"][0]["name"] == "Pillola contesa"
    if operation == "rename":
        expect(page.get_by_label("Nome della pillola", exact=True)).to_have_value(
            "Bozza conservata"
        )
    api.post(f"/api/fermentations/{competitors[0]}/end").raise_for_status()
    expect(action).to_be_enabled()
    action.click()
    expect(page.get_by_role("status", name="Esito registro", exact=True)).to_contain_text(
        "rinominata" if operation == "rename" else "rimossa"
    )
    if operation == "rename":
        expect(
            page.get_by_role("region", name="Pillola Bozza conservata", exact=True)
        ).to_be_visible()
        assert api.get("/api/pills").json()["pills"][0]["name"] == "Bozza conservata"
    else:
        expect(editor).not_to_be_visible()
        expect(card).to_have_count(0)
        assert api.get("/api/pills").json()["pills"] == []


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("operation", ["rename", "remove"])
@pytest.mark.parametrize("failure", ["network", "unavailable"])
def test_failed_registry_change_keeps_input_and_can_be_retried(
    page: Page, api: httpx.Client, width: int, operation: str, failure: str
) -> None:
    pill = api.post(
        "/api/pills", json={"name": "Pillola da correggere", "mac": "AA:BB:CC:DD:EE:FF"}
    ).json()["pill"]
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=devices")
    card = page.get_by_role("region", name="Pillola Pillola da correggere", exact=True)
    if operation == "rename":
        card.get_by_role("button", name="Rinomina", exact=True).click()
        editor = page.get_by_role("region", name="Rinomina pillola", exact=True)
        action = editor.get_by_role("button", name="Salva nome", exact=True)
        page.get_by_label("Nome della pillola", exact=True).fill("   ")
        action.click()
        expect(editor.get_by_role("alert")).to_contain_text("Inserisci nome")
        page.get_by_label("Nome della pillola", exact=True).fill("Nome conservato")
    else:
        card.get_by_role("button", name="Rimuovi", exact=True).click()
        editor = page.get_by_role("dialog", name="Rimuovi pillola", exact=True)
        action = editor.get_by_role("button", name="Conferma rimozione", exact=True)
    method = "PATCH" if operation == "rename" else "DELETE"
    failed = False

    def fail_once(route: Route) -> None:
        nonlocal failed
        if route.request.method != method or failed:
            route.continue_()
            return
        failed = True
        if failure == "network":
            route.abort("connectionfailed")
        else:
            route.fulfill(status=503, json={"detail": "Registro temporaneamente non disponibile"})

    page.route("**/api/pills/*", fail_once)
    action.click()
    expect(editor.get_by_role("alert")).to_contain_text(
        "Non è stato possibile confermare"
        if failure == "network"
        else "Registro temporaneamente non disponibile"
    )
    expect(page.get_by_role("status", name="Esito registro", exact=True)).to_have_count(0)
    expect(editor).to_be_visible()
    assert api.get("/api/pills").json()["pills"] == [pill]
    if operation == "rename":
        expect(page.get_by_label("Nome della pillola", exact=True)).to_have_value("Nome conservato")
    action.click()
    expect(page.get_by_role("status", name="Esito registro", exact=True)).to_contain_text(
        "rinominata" if operation == "rename" else "rimossa"
    )
    if operation == "rename":
        assert api.get("/api/pills").json()["pills"][0]["name"] == "Nome conservato"
    else:
        assert api.get("/api/pills").json()["pills"] == []


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize(
    "operation,leave", [("register", False), ("rename", False), ("remove", False), ("rename", True)]
)
def test_pending_change_is_submitted_once_and_cannot_update_a_later_page(
    page: Page, api: httpx.Client, width: int, operation: str, leave: bool
) -> None:
    pill = None
    if operation != "register":
        pill = api.post(
            "/api/pills", json={"name": "Pillola lenta", "mac": "AA:BB:CC:DD:EE:FF"}
        ).json()["pill"]
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=devices")
    if operation == "register":
        page.get_by_role("button", name="Aggiungi pillola", exact=True).click()
        page.get_by_label("Nome della pillola", exact=True).fill("Nome confermato")
        page.get_by_label("MAC Bluetooth", exact=True).fill("AA:BB:CC:DD:EE:FF")
        action = page.get_by_role("button", name="Registra pillola", exact=True)
    elif operation == "rename":
        page.get_by_role("region", name="Pillola Pillola lenta", exact=True).get_by_role(
            "button", name="Rinomina", exact=True
        ).click()
        page.get_by_label("Nome della pillola", exact=True).fill("Nome confermato")
        action = page.get_by_role("button", name="Salva nome", exact=True)
    else:
        page.get_by_role("region", name="Pillola Pillola lenta", exact=True).get_by_role(
            "button", name="Rimuovi", exact=True
        ).click()
        action = page.get_by_role("button", name="Conferma rimozione", exact=True)
    method = {"register": "POST", "rename": "PATCH", "remove": "DELETE"}[operation]
    held: list[tuple[Route, APIResponse]] = []

    def hold_response(route: Route) -> None:
        if route.request.method == method:
            held.append((route, route.fetch()))
        else:
            route.continue_()

    page.route("**/api/pills**", hold_response)
    action.dblclick()
    deadline = time.monotonic() + 10
    while not held and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    assert len(held) == 1
    route, response = held[0]
    try:
        assert response.status == {"register": 201, "rename": 200, "remove": 204}[operation]
        pending = page.get_by_role(
            "button", name="Rimozione…" if operation == "remove" else "Salvataggio…", exact=True
        )
        expect(pending).to_be_disabled()
        expect(page.get_by_role("button", name="Annulla", exact=True)).to_be_disabled()
        expect(page.get_by_role("status", name="Esito registro", exact=True)).to_have_count(0)
        page.keyboard.press("Enter")
        assert len(held) == 1
        if leave:
            with page.expect_event(
                "requestfailed",
                predicate=lambda request: request.method == method and "/api/pills" in request.url,
            ):
                page.get_by_role("navigation", name="Navigazione principale").get_by_role(
                    "link", name="Home", exact=True
                ).click()
            with suppress(PlaywrightError):
                route.fulfill(response=response)
            expect(page).to_have_url(str(api.base_url).rstrip("/") + "/")
            expect(page.get_by_role("status", name="Esito registro", exact=True)).to_have_count(0)
            page.get_by_role("navigation", name="Navigazione principale").get_by_role(
                "link", name="Dispositivi", exact=True
            ).click()
            expect(
                page.get_by_role("region", name="Pillola Nome confermato", exact=True)
            ).to_be_visible()
            expect(page.get_by_role("status", name="Esito registro", exact=True)).to_have_count(0)
        else:
            route.fulfill(response=response)
            expect(page.get_by_role("status", name="Esito registro", exact=True)).to_contain_text(
                {"register": "registrata", "rename": "rinominata", "remove": "rimossa"}[operation]
            )
        current = api.get("/api/pills").json()["pills"]
        if operation == "remove":
            assert current == []
        else:
            assert len(current) == 1
            assert current[0]["name"] == "Nome confermato"
            if pill is not None:
                assert current[0]["id"] == pill["id"]
        assert len(held) == 1
    finally:
        with suppress(PlaywrightError):
            route.abort()


@pytest.mark.parametrize("width", [1440, 390])
def test_device_tabs_and_selected_diagnostics_survive_history_and_removal(
    page: Page, api: httpx.Client, width: int
) -> None:
    first = api.post(
        "/api/pills", json={"name": "Prima pillola", "mac": "AA:BB:CC:DD:EE:FF"}
    ).json()["pill"]
    second = api.post(
        "/api/pills", json={"name": "Seconda pillola", "mac": "11:22:33:44:55:66"}
    ).json()["pill"]
    for pill, gravity in ((first, 1050), (second, 1040)):
        api.post(
            "/telemetry", json=gateway_lettura(pill_mac=pill["mac"], specific_gravity=gravity)
        ).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=devices")
    pills_tab = page.get_by_role("tab", name="Pillole", exact=True)
    thermal_tab = page.get_by_role("tab", name="Dispositivi termici", exact=True)
    pills_tab.focus()
    pills_tab.press("ArrowRight")
    expect(thermal_tab).to_be_focused()
    expect(thermal_tab).to_have_attribute("aria-selected", "true")
    expect(page).to_have_url(f"{str(api.base_url).rstrip('/')}/?page=devices&tab=thermal")
    thermal_tab.press("Home")
    expect(pills_tab).to_be_focused()
    expect(pills_tab).to_have_attribute("aria-selected", "true")
    page.go_back()
    expect(thermal_tab).to_have_attribute("aria-selected", "true")
    page.reload()
    expect(thermal_tab).to_have_attribute("aria-selected", "true")
    expect(
        page.get_by_role("heading", name="Registra un dispositivo termico", exact=True)
    ).to_be_visible()
    pills_tab.click()
    page.get_by_role("region", name="Pillola Seconda pillola", exact=True).get_by_role(
        "link", name="Esplora letture", exact=True
    ).click()
    expect(page.get_by_label("Pillola diagnostica", exact=True)).to_have_value(second["id"])
    expect(page.get_by_role("region", name="Densità", exact=True)).to_contain_text("1.040")
    page.reload()
    expect(page.get_by_label("Pillola diagnostica", exact=True)).to_have_value(second["id"])
    page.get_by_label("Pillola diagnostica", exact=True).select_option(first["id"])
    expect(page.get_by_role("region", name="Densità", exact=True)).to_contain_text("1.050")
    page.go_back()
    expect(page.get_by_label("Pillola diagnostica", exact=True)).to_have_value(second["id"])
    expect(page.get_by_role("region", name="Densità", exact=True)).to_contain_text("1.040")
    api.delete(f"/api/pills/{second['id']}").raise_for_status()
    expect(page.get_by_role("heading", name="Pillola non disponibile", exact=True)).to_be_visible()
    expect(page.get_by_role("region", name="Densità", exact=True)).to_have_count(0)
    page.reload()
    expect(page.get_by_role("heading", name="Pillola non disponibile", exact=True)).to_be_visible()
    page.get_by_label("Pillola diagnostica", exact=True).select_option(first["id"])
    expect(page.get_by_role("region", name="Densità", exact=True)).to_contain_text("1.050")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_registry_keeps_last_values_and_expires_confirmed_contact_offline(
    page: Page, api: httpx.Client
) -> None:
    api.patch("/api/settings", json={"communication_timeout_seconds": 30}).raise_for_status()
    api.post(
        "/api/pills", json={"name": "Pillola offline", "mac": "AA:BB:CC:DD:EE:FF"}
    ).raise_for_status()
    timestamp = datetime.now(UTC).timestamp()
    api.post("/telemetry", json=gateway_lettura(timestamp=timestamp)).raise_for_status()
    page.clock.install()
    page.set_viewport_size({"width": 390, "height": 1000})
    page.goto(f"{api.base_url}?page=devices")
    card = page.get_by_role("region", name="Pillola Pillola offline", exact=True)
    expect(card).to_contain_text("Comunicazione entro il timeout")

    page.context.set_offline(True)
    expect(page.get_by_label("Collegamento live")).to_contain_text("Riconnessione automatica")
    page.clock.fast_forward(31000)
    expect(card).to_contain_text("Ultima comunicazione confermata oltre il timeout")
    expect(card).to_contain_text("1.050")
    api.post(
        "/telemetry", json=gateway_lettura(timestamp=timestamp + 1, specific_gravity=1040)
    ).raise_for_status()
    expect(card).to_contain_text("1.050")
    page.context.set_offline(False)
    expect(card).to_contain_text("1.040", timeout=10000)
    expect(card).to_contain_text("Comunicazione entro il timeout")


@pytest.mark.parametrize("width", [1440, 390])
def test_invalid_mac_keeps_registration_draft_for_correction(
    page: Page, api: httpx.Client, width: int
) -> None:
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?page=devices")
    page.get_by_role("button", name="Aggiungi pillola", exact=True).click()
    page.get_by_label("Nome della pillola", exact=True).fill("Bozza registrazione")
    page.get_by_label("MAC Bluetooth", exact=True).fill("MAC non valido")
    with page.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith("/api/pills")
    ) as invalid:
        page.get_by_role("button", name="Registra pillola", exact=True).click()
    assert invalid.value.status == 422
    expect(
        page.get_by_role("region", name="Registrazione pillola", exact=True).get_by_role("alert")
    ).to_contain_text("MAC Bluetooth valido")
    expect(page.get_by_label("Nome della pillola", exact=True)).to_have_value("Bozza registrazione")
    expect(page.get_by_label("MAC Bluetooth", exact=True)).to_have_value("MAC non valido")
    assert api.get("/api/pills").json()["pills"] == []
    expect(page.get_by_role("status", name="Esito registro", exact=True)).to_have_count(0)
    page.get_by_label("MAC Bluetooth", exact=True).fill("aabbccddeeff")
    page.get_by_role("button", name="Registra pillola", exact=True).click()
    expect(
        page.get_by_role("region", name="Pillola Bozza registrazione", exact=True)
    ).to_contain_text("AA:BB:CC:DD:EE:FF")

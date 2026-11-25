"""Raw readings are an explicit, independent view of the public history."""

import os
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from playwright.sync_api import APIResponse, Page, Route, expect
from playwright.sync_api import Error as PlaywrightError

from tests.payloads import fermentation_payload, gateway_lettura


@pytest.mark.parametrize("width", [1440, 390])
def test_raw_readings_open_only_on_request_and_restore_focus(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Dati su richiesta")
    ).json()["fermentation"]
    timestamp = datetime.fromisoformat(cycle["started_at"]).timestamp() + 1
    api.post("/telemetry", json=gateway_lettura(timestamp=timestamp)).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    expect(page.get_by_role("img", name="Grafico a linee: 1 lettura", exact=True)).to_be_visible()
    expect(page.get_by_role("table", name="Letture della fermentazione")).to_have_count(0)
    opener = page.get_by_role("button", name="Dati grezzi", exact=True)
    opener.click()
    dialog = page.get_by_role("dialog", name="Dati grezzi", exact=True)
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("table", name="Letture della fermentazione")).to_be_visible()
    expect(dialog.get_by_role("combobox", name="Ambito dei dati")).to_have_value("period")
    box = dialog.bounding_box()
    assert box is not None
    if width == 390:
        assert box["x"] == 0 and box["y"] == 0
        assert box["width"] == 390 and box["height"] == 1000
    else:
        assert box["x"] > 0 and box["width"] < width
    dialog.get_by_role("button", name="Chiudi dati grezzi").focus()
    page.keyboard.press("Shift+Tab")
    assert dialog.evaluate("element => element.contains(document.activeElement)")
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()


@pytest.mark.parametrize("width", [1440, 390])
def test_scope_and_pagination_preserve_the_graph_selection(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Due ambiti")).json()[
        "fermentation"
    ]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp() + 1
    for index in range(205):
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=base + index * 60, specific_gravity=1060 if index == 0 else 1050.125
            ),
        ).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    page.get_by_role("button", name="1h", exact=True).click()
    expect(page.get_by_role("img", name="Grafico a linee: 61 letture", exact=True)).to_be_visible()
    page.get_by_label("Batteria %", exact=True).check()
    selected = page.get_by_label("Intervallo visualizzato").inner_text()
    page.get_by_role("button", name="Dati grezzi", exact=True).click()
    dialog = page.get_by_role("dialog", name="Dati grezzi", exact=True)
    table = dialog.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("row")).to_have_count(62)
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_have_count(0)
    dialog.get_by_role("combobox", name="Ambito dei dati").select_option("all")
    expect(table.get_by_role("row")).to_have_count(201)

    failed_pages: list[Route] = []

    def fail_page(route: Route) -> None:
        if "before=" in route.request.url:
            failed_pages.append(route)
        else:
            route.continue_()

    page.route("**/api/fermentations/*/readings?*", fail_page)
    with page.expect_request(
        lambda request: "/readings?" in request.url and "before=" in request.url
    ):
        dialog.get_by_role("button", name="Letture precedenti", exact=True).click()
    expect(dialog.get_by_text("Caricamento dati grezzi…", exact=True)).to_be_visible()
    assert dialog.evaluate("element => element.contains(document.activeElement)")
    page.keyboard.press("Shift+Tab")
    assert dialog.evaluate("element => element.contains(document.activeElement)")
    assert failed_pages
    failed_pages[0].fulfill(status=503, json={"detail": "Unavailable"})
    expect(dialog.get_by_role("alert")).to_contain_text("Non è stato possibile")
    assert dialog.evaluate("element => element.contains(document.activeElement)")
    expect(
        dialog.get_by_text("Nessuna lettura nell’ambito selezionato.", exact=True)
    ).to_have_count(0)
    page.unroute("**/api/fermentations/*/readings?*")
    dialog.get_by_role("button", name="Riprova dati grezzi", exact=True).click()
    expect(table.get_by_role("row")).to_have_count(6)
    assert dialog.evaluate("element => element.contains(document.activeElement)")
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_be_visible()
    expect(dialog.get_by_role("button", name="Letture precedenti", exact=True)).to_be_disabled()
    dialog.get_by_role("button", name="Letture più recenti", exact=True).click()
    expect(table.get_by_role("row")).to_have_count(201)
    dialog.get_by_role("combobox", name="Ambito dei dati").select_option("period")
    expect(table.get_by_role("row")).to_have_count(62)
    expect(dialog.get_by_role("button", name="Letture più recenti", exact=True)).to_be_disabled()
    page.keyboard.press("Escape")
    expect(page.get_by_label("Intervallo visualizzato")).to_have_text(selected)
    expect(page.get_by_label("Batteria %", exact=True)).to_be_checked()
    expect(page.get_by_role("img", name="Grafico a linee: 61 letture", exact=True)).to_be_visible()


@pytest.mark.parametrize("width", [1440, 390])
def test_original_values_and_quality_are_independent_of_visible_chart_series(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Valori originali")
    ).json()["fermentation"]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp()
    first = gateway_lettura(
        timestamp=base + 0.123456,
        temperature=18.125,
        valid=False,
        gravity_velocity=-99.5,
        accel_x=0,
        accel_z=-2.75,
    )
    first.pop("accel_y")
    second = gateway_lettura(timestamp=base + 0.223456, valid=True, gravity_velocity=0)
    third = gateway_lettura(timestamp=base + 0.323456, battery=0)
    for key in ("valid", "gravity_velocity", "accel_x", "accel_y", "accel_z"):
        third.pop(key)
    for payload in (first, second, third):
        api.post("/telemetry", json=payload).raise_for_status()
    original = api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"][0]
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    expect(page.get_by_role("img", name="Grafico a linee: 3 letture", exact=True)).to_be_visible()
    expect(page.get_by_role("checkbox", checked=True)).to_have_count(2)
    page.get_by_role("button", name="Dati grezzi", exact=True).click()
    dialog = page.get_by_role("dialog", name="Dati grezzi", exact=True)
    table = dialog.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("row")).to_have_count(4)
    row = table.get_by_role("row").nth(1)
    expect(row.get_by_role("cell", name="-99,5", exact=True)).to_be_visible()
    expect(row.get_by_role("cell", name="Non valida", exact=True)).to_be_visible()
    expect(row.get_by_role("cell", name="Non disponibile", exact=True)).to_have_count(1)
    expect(row.get_by_role("cell", name="0", exact=True)).to_have_count(1)
    expect(row.get_by_text(f"Unix: {original['timestamp']}", exact=True)).to_be_visible()
    expect(row.get_by_role("cell", name=original["received_at"], exact=True)).to_be_visible()
    expect(row.get_by_role("cell", name=original["pill_mac"], exact=True)).to_be_visible()
    expect(row.get_by_role("cell", name=original["pill_id"], exact=True)).to_be_visible()
    expect(
        table.get_by_role("row").nth(2).get_by_role("cell", name="Valida", exact=True)
    ).to_be_visible()
    missing = table.get_by_role("row").nth(3)
    expect(missing.get_by_role("cell", name="Non dichiarata", exact=True)).to_be_visible()
    expect(missing.get_by_role("cell", name="Non disponibile", exact=True)).to_have_count(4)
    expect(missing.get_by_role("cell", name="0", exact=True)).to_have_count(1)
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        dialog.screenshot(path=Path(directory) / f"dati-grezzi-{width}.png")


@pytest.mark.parametrize("width", [1440, 390])
def test_loading_empty_error_and_retry_are_distinct(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Stati dei dati")).json()[
        "fermentation"
    ]
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    opener = page.get_by_role("button", name="Dati grezzi", exact=True)
    opener.click()
    dialog = page.get_by_role("dialog", name="Dati grezzi", exact=True)
    expect(
        dialog.get_by_text("Nessuna lettura nell’ambito selezionato.", exact=True)
    ).to_be_visible()
    expect(dialog.get_by_role("alert")).to_have_count(0)
    page.keyboard.press("Escape")
    timestamp = datetime.fromisoformat(cycle["started_at"]).timestamp() + 1
    api.post("/telemetry", json=gateway_lettura(timestamp=timestamp)).raise_for_status()
    expect(page.get_by_role("img", name="Grafico a linee: 1 lettura", exact=True)).to_be_visible()
    held: list[Route] = []
    pattern = f"**/api/fermentations/{cycle['id']}/readings?*"
    page.route(pattern, lambda route: held.append(route))
    opener.click()
    expect(dialog.get_by_text("Caricamento dati grezzi…", exact=True)).to_be_visible()
    expect(
        dialog.get_by_text("Nessuna lettura nell’ambito selezionato.", exact=True)
    ).to_have_count(0)
    assert held
    held[0].fulfill(status=503, json={"detail": "Unavailable"})
    expect(dialog.get_by_role("alert")).to_contain_text("Non è stato possibile")
    expect(
        dialog.get_by_text("Nessuna lettura nell’ambito selezionato.", exact=True)
    ).to_have_count(0)
    page.unroute(pattern)
    dialog.get_by_role("button", name="Riprova dati grezzi", exact=True).click()
    expect(dialog.get_by_role("table").get_by_role("row")).to_have_count(2)
    expect(dialog.get_by_role("alert")).to_have_count(0)


@pytest.mark.parametrize("width", [1440, 390])
def test_obsolete_scope_response_and_changing_cycle_cannot_replace_raw_readings(
    page: Page, api: httpx.Client, width: int
) -> None:
    first = api.post("/api/fermentations", json=fermentation_payload(api, "Prima tabella")).json()[
        "fermentation"
    ]
    pill = api.post(
        "/api/pills", json={"name": "Seconda pillola", "mac": "11:22:33:44:55:66"}
    ).json()["pill"]
    second = api.post(
        "/api/fermentations", json={"name": "Seconda tabella", "pill_id": pill["id"]}
    ).json()["fermentation"]
    base = (
        max(datetime.fromisoformat(cycle["started_at"]).timestamp() for cycle in (first, second))
        + 1
    )
    for offset, gravity in ((0, 1060), (3600, 1050), (7200, 1040)):
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=base + offset, specific_gravity=gravity)
        ).raise_for_status()
    api.post(
        "/telemetry",
        json=gateway_lettura(timestamp=base, pill_mac=pill["mac"], specific_gravity=1099),
    ).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?fermentation={second['id']}")
    page.goto(f"{api.base_url}?fermentation={first['id']}")
    page.get_by_role("button", name="1h", exact=True).click()
    expect(page.get_by_role("img", name="Grafico a linee: 2 letture", exact=True)).to_be_visible()
    page.get_by_role("button", name="Dati grezzi", exact=True).click()
    dialog = page.get_by_role("dialog", name="Dati grezzi", exact=True)
    table = dialog.get_by_role("table")
    expect(table.get_by_role("row")).to_have_count(3)
    delayed: list[tuple[Route, APIResponse]] = []

    def wait_for_delayed_response() -> None:
        deadline = time.monotonic() + 5
        while not delayed and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        assert delayed

    def hold_all(route: Route) -> None:
        query = parse_qs(urlsplit(route.request.url).query)
        if float(query["from_timestamp"][0]) < base:
            delayed.append((route, route.fetch()))
        else:
            route.continue_()

    pattern = f"**/api/fermentations/{first['id']}/readings?*"
    page.route(pattern, hold_all)
    with page.expect_request(lambda request: "/readings?" in request.url):
        dialog.get_by_role("combobox", name="Ambito dei dati").select_option("all")
    expect(dialog.get_by_text("Caricamento dati grezzi…", exact=True)).to_be_visible()
    wait_for_delayed_response()
    dialog.get_by_role("combobox", name="Ambito dei dati").select_option("period")
    expect(table.get_by_role("row")).to_have_count(3)
    assert delayed
    route, response = delayed.pop()
    with suppress(PlaywrightError):
        route.fulfill(response=response)
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_have_count(0)
    with page.expect_request(lambda request: "/readings?" in request.url):
        dialog.get_by_role("combobox", name="Ambito dei dati").select_option("all")
    expect(dialog.get_by_text("Caricamento dati grezzi…", exact=True)).to_be_visible()
    wait_for_delayed_response()
    page.go_back()
    expect(
        page.get_by_role("heading", name="Dettaglio: Seconda tabella", exact=True)
    ).to_be_visible()
    expect(dialog).to_have_count(0)
    for route, response in delayed:
        with suppress(PlaywrightError):
            route.fulfill(response=response)
    page.get_by_role("button", name="Dati grezzi", exact=True).click()
    expect(dialog.get_by_role("table").get_by_role("row")).to_have_count(2)
    expect(dialog.get_by_role("cell", name="1.099", exact=True)).to_be_visible()
    expect(dialog.get_by_role("cell", name="1.050", exact=True)).to_have_count(0)

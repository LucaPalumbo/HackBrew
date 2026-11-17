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


@pytest.mark.parametrize("width", [1440, 390])
def test_home_navigation_and_first_start_are_focused(
    page: Page, empty_api: httpx.Client, width: int
) -> None:
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(str(empty_api.base_url))
    navigation = page.get_by_role("navigation", name="Navigazione principale")
    for name in ("Home", "Archivio", "Dispositivi", "Impostazioni"):
        expect(navigation.get_by_role("link", name=name, exact=True)).to_be_visible()
    expect(navigation.get_by_role("link", name="Home", exact=True)).to_have_attribute(
        "aria-current", "page"
    )
    expect(page.get_by_role("heading", name="Inizia dalla prima fermentazione.")).to_be_visible()
    expect(page.get_by_label("Nome della fermentazione", exact=True)).to_have_count(0)
    expect(page.get_by_role("table")).to_have_count(0)
    page.get_by_role("link", name="Nuova fermentazione", exact=True).first.click()
    expect(page.get_by_label("Nome della fermentazione", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Avvia fermentazione", exact=True)).to_be_disabled()
    page.go_back()
    expect(page.get_by_role("heading", name="Inizia dalla prima fermentazione.")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
def test_home_cards_follow_each_pillola_and_open_an_isolated_detail(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycles = []
    for name, mac, gravity in (
        ("Prima IPA", "AA:BB:CC:DD:EE:FF", 1050),
        ("Seconda birra", "11:22:33:44:55:66", 1040),
    ):
        pill = api.post("/api/pills", json={"name": name, "mac": mac}).json()["pill"]
        cycle = api.post("/api/fermentations", json={"name": name, "pill_id": pill["id"]}).json()[
            "fermentation"
        ]
        cycles.append(cycle)
        api.post(
            "/telemetry",
            json=gateway_lettura(
                pill_mac=mac, timestamp=datetime.now(UTC).timestamp(), specific_gravity=gravity
            ),
        ).raise_for_status()
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(str(api.base_url))
    cards = page.get_by_role("region", name="Fermentazioni", exact=True)
    first = cards.get_by_role("button", name="Apri Prima IPA", exact=False)
    second = cards.get_by_role("button", name="Apri Seconda birra", exact=False)
    expect(first).to_contain_text("1.050")
    expect(first).to_contain_text("Batteria")
    expect(second).to_contain_text("1.040")
    expect(cards.get_by_role("button")).to_have_count(2)
    expect(page.get_by_role("table")).to_have_count(0)
    expect(page.get_by_label("Nome della fermentazione", exact=True)).to_have_count(0)
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=path / f"home-navigation-{width}.png", full_page=True)
    first.click()
    expect(page).to_have_url(str(api.base_url).rstrip("/") + "/?fermentation=" + cycles[0]["id"])
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("cell", name="1.050", exact=True)).to_be_visible()
    api.post(
        "/telemetry",
        json=gateway_lettura(
            pill_mac="11:22:33:44:55:66",
            timestamp=datetime.now(UTC).timestamp(),
            specific_gravity=1020,
        ),
    ).raise_for_status()
    expect(table.get_by_role("cell", name="1.020", exact=True)).to_have_count(0)
    page.reload()
    expect(table.get_by_role("cell", name="1.050", exact=True)).to_be_visible()
    page.go_back()
    expect(second).to_contain_text("1.020")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
def test_home_shows_only_three_recent_concluded_cycles_until_a_new_cycle_starts(
    page: Page, api: httpx.Client, width: int
) -> None:
    pill = api.post("/api/pills", json={"name": "Pillola", "mac": "AA:BB:CC:DD:EE:FF"}).json()[
        "pill"
    ]
    for name, gravity in (("Prima", 1060), ("Seconda", 1050), ("Terza", 1040), ("Ultima", 1030)):
        cycle = api.post("/api/fermentations", json={"name": name, "pill_id": pill["id"]}).json()[
            "fermentation"
        ]
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=datetime.now(UTC).timestamp(), specific_gravity=gravity),
        ).raise_for_status()
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(str(api.base_url))
    cards = page.get_by_role("region", name="Fermentazioni", exact=True)
    expect(cards.get_by_role("button")).to_have_count(3)
    expect(cards.get_by_role("button").nth(0)).to_contain_text("Ultima")
    expect(cards.get_by_role("button").nth(0)).to_contain_text("1.030")
    expect(cards.get_by_role("button").nth(1)).to_contain_text("Terza")
    expect(cards.get_by_role("button").nth(2)).to_contain_text("Seconda")
    expect(cards.get_by_text("Batteria", exact=False)).to_have_count(0)
    expect(cards.get_by_role("button").nth(0)).to_contain_text("Avvio")
    expect(cards.get_by_role("button").nth(0)).to_contain_text("Termine")
    api.post(
        "/api/fermentations", json={"name": "Nuova attiva", "pill_id": pill["id"]}
    ).raise_for_status()
    expect(cards.get_by_role("button")).to_have_count(1)
    expect(cards.get_by_role("button")).to_contain_text("Nuova attiva")
    expect(cards.get_by_role("button")).to_contain_text("Nessuna lettura registrata")
    expect(cards.get_by_text("1.030", exact=False)).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_failed_recent_history_is_not_presented_as_first_start(
    page: Page, api: httpx.Client
) -> None:
    pill = api.post("/api/pills", json={"name": "Pillola", "mac": "AA:BB:CC:DD:EE:FF"}).json()[
        "pill"
    ]
    cycle = api.post(
        "/api/fermentations", json={"name": "Birra conservata", "pill_id": pill["id"]}
    ).json()["fermentation"]
    api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
    page.route(
        "**/api/fermentations?status=concluded*", lambda route: route.fulfill(status=503, json={})
    )
    page.goto(str(api.base_url))
    expect(page.get_by_role("alert")).to_contain_text("fermentazioni recenti")
    expect(page.get_by_role("heading", name="Inizia dalla prima fermentazione.")).to_have_count(0)
    page.unroute("**/api/fermentations?status=concluded*")
    page.get_by_role("button", name="Riprova fermentazioni recenti", exact=True).click()
    expect(page.get_by_role("button", name="Apri Birra conservata", exact=False)).to_be_visible()
    expect(page.get_by_role("alert")).to_have_count(0)

import os
import re
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import APIResponse, Page, Route, expect
from playwright.sync_api import Error as PlaywrightError

from tests.payloads import fermentation_payload, gateway_lettura


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_create_parallel_cycles_open_live_details_and_end_only_selected_cycle(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    first_pill = api.get("/api/pills").json()["pills"][0]
    second_pill = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url))
    page.get_by_label("Nome della fermentazione").fill("IPA parallela")
    page.get_by_label("Pillola della fermentazione").select_option(first_pill["id"])
    page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
    expect(page.get_by_role("heading", name="IPA parallela", exact=True)).to_be_visible()
    page.get_by_label("Nome della fermentazione").fill("Stout parallela")
    page.get_by_label("Pillola della fermentazione").select_option(second_pill["id"])
    page.get_by_role("button", name="Avvia fermentazione", exact=True).click()
    overview = page.get_by_role("region", name="Fermentazioni", exact=True)
    first_card = overview.get_by_role("button", name=re.compile("^Apri IPA parallela"))
    second_card = overview.get_by_role("button", name=re.compile("^Apri Stout parallela"))
    expect(first_card).to_contain_text("Solo monitoraggio")
    expect(second_card).to_contain_text("In corso")
    for pill, gravity in ((first_pill, 1050), (second_pill, 1040)):
        assert (
            api.post(
                "/telemetry",
                json=gateway_lettura(
                    pill_mac=pill["mac"],
                    timestamp=datetime.now(UTC).timestamp(),
                    specific_gravity=gravity,
                ),
            ).status_code
            == 200
        )
    expect(first_card).to_contain_text("1.050")
    expect(second_card).to_contain_text("1.040")
    assert overview.get_by_role("button", name=re.compile("^Apri ")).count() == 2
    first_card.click()
    first = next(
        row
        for row in api.get("/api/fermentations/active").json()["fermentations"]
        if row["name"] == "IPA parallela"
    )
    second = next(
        row
        for row in api.get("/api/fermentations/active").json()["fermentations"]
        if row["name"] == "Stout parallela"
    )
    expect(page).to_have_url(re.compile("fermentation=" + first["id"]))
    expect(page.get_by_role("region", name="Dati della fermentazione")).to_be_focused()
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("cell", name="1.050", exact=True)).to_be_visible()
    page.reload()
    expect(table.get_by_role("cell", name="1.050", exact=True)).to_be_visible()
    second_card.click()
    expect(table.get_by_role("cell", name="1.040", exact=True)).to_be_visible()
    page.go_back()
    expect(table.get_by_role("cell", name="1.050", exact=True)).to_be_visible()
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(
                pill_mac=second_pill["mac"],
                timestamp=datetime.now(UTC).timestamp(),
                specific_gravity=1020,
            ),
        ).status_code
        == 200
    )
    expect(second_card).to_contain_text("1.020")
    expect(page).to_have_url(re.compile("fermentation=" + first["id"]))
    expect(table.get_by_role("cell", name="1.050", exact=True)).to_be_visible()
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(
                pill_mac=first_pill["mac"],
                timestamp=datetime.now(UTC).timestamp(),
                specific_gravity=1030,
            ),
        ).status_code
        == 200
    )
    expect(table.get_by_role("cell", name="1.030", exact=True)).to_be_visible()
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=path / f"fermentazioni-parallele-{width}.png", full_page=True)
    page.get_by_role("button", name="Termina fermentazione", exact=True).click()
    expect(page.get_by_role("heading", name="Storico: IPA parallela", exact=True)).to_be_visible()
    expect(first_card).to_contain_text("Conclusa")
    assert (
        api.get(f"/api/fermentations/{second['id']}").json()["fermentation"]["status"] == "active"
    )
    page.reload()
    expect(page.get_by_role("button", name="Termina fermentazione", exact=True)).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_pagination_keeps_requested_page_when_live_update_interrupts_loading(
    page: Page,
    api: httpx.Client,
) -> None:
    for number in range(21):
        created = api.post(
            "/api/fermentations", json=fermentation_payload(api, f"Archivio {number:02d}")
        ).json()["fermentation"]
        api.post(f"/api/fermentations/{created['id']}/end").raise_for_status()
    api.post(
        "/api/fermentations", json=fermentation_payload(api, "Attiva per paging")
    ).raise_for_status()
    page.goto(str(api.base_url))
    overview = page.get_by_role("region", name="Fermentazioni", exact=True)
    expect(overview.get_by_role("button", name=re.compile("^Apri Attiva"))).to_be_visible()
    held: Route | None = None

    def hold_first_older_page(route: Route) -> None:
        nonlocal held
        if "offset=20" in route.request.url and held is None:
            held = route
            return
        route.continue_()

    page.route("**/api/fermentations?*", hold_first_older_page)
    with page.expect_request(lambda request: "offset=20" in request.url):
        page.get_by_role("button", name="Altre fermentazioni", exact=True).click()
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=datetime.now(UTC).timestamp())
        ).status_code
        == 200
    )
    page.wait_for_timeout(1100)
    assert held is not None
    with suppress(PlaywrightError):
        held.continue_()
    expect(overview.get_by_role("button", name=re.compile("^Apri Archivio 00"))).to_be_visible()
    expect(overview.get_by_role("button", name=re.compile("^Apri Attiva"))).to_have_count(0)


def test_delayed_reading_updates_concluded_detail_without_reopening_it(
    page: Page,
    api: httpx.Client,
) -> None:
    first = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA conclusa in attesa")
    ).json()["fermentation"]
    ended = api.post(f"/api/fermentations/{first['id']}/end").json()["fermentation"]
    current = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA successiva")
    ).json()["fermentation"]
    page.goto(str(api.base_url) + "?fermentation=" + first["id"])
    expect(
        page.get_by_text("Nessuna lettura registrata per questa fermentazione.", exact=True)
    ).to_be_visible()
    timestamp = datetime.fromisoformat(first["started_at"]).timestamp()
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=timestamp, specific_gravity=1060)
        ).status_code
        == 200
    )
    expect(
        page.get_by_role("table", name="Letture della fermentazione").get_by_role(
            "cell", name="1.060", exact=True
        )
    ).to_be_visible()
    expect(
        page.get_by_role("heading", name="Storico: IPA conclusa in attesa", exact=True)
    ).to_be_visible()
    assert api.get(f"/api/fermentations/{first['id']}").json()["fermentation"] == ended
    assert api.get(f"/api/fermentations/{current['id']}/readings").json()["readings"] == []


def test_frequent_live_updates_do_not_cancel_slow_cards_and_detail_loads_forever(
    page: Page,
    api: httpx.Client,
) -> None:
    fermentation = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA rete lenta")
    ).json()["fermentation"]
    pending: list[tuple[Route, APIResponse]] = []
    release_new_requests = False

    def delay_reads(route: Route) -> None:
        if route.request.method != "GET" or release_new_requests:
            route.continue_()
            return
        pending.append((route, route.fetch()))

    page.route("**/api/fermentations**", delay_reads)
    page.goto(str(api.base_url) + "?fermentation=" + fermentation["id"])
    page.wait_for_timeout(200)
    initial_requests = list(pending)
    assert initial_requests
    try:
        for gravity in (1050, 1040, 1030):
            assert (
                api.post(
                    "/telemetry",
                    json=gateway_lettura(
                        timestamp=datetime.now(UTC).timestamp(), specific_gravity=gravity
                    ),
                ).status_code
                == 200
            )
            page.wait_for_timeout(1100)
        release_new_requests = True
        for route, response in initial_requests:
            # Cancelled requests in the regression must still reach the UI assertions.
            with suppress(PlaywrightError):
                route.fulfill(response=response)
            pending.remove((route, response))
        card = page.get_by_role("button", name=re.compile("^Apri IPA rete lenta"))
        expect(card).to_contain_text("1.030")
        table = page.get_by_role("table", name="Letture della fermentazione")
        expect(table.get_by_role("cell", name="1.030", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Termina fermentazione", exact=True)).to_be_enabled()
    finally:
        for route, _ in pending:
            with suppress(PlaywrightError):
                route.abort()


def test_background_retry_does_not_invent_empty_cards_after_failed_initial_load(
    page: Page,
    api: httpx.Client,
) -> None:
    api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA da recuperare")
    ).raise_for_status()
    pending: list[tuple[Route, APIResponse]] = []
    failed = False
    release_new_requests = False

    def fail_then_delay(route: Route) -> None:
        nonlocal failed
        if not failed:
            failed = True
            route.fulfill(status=503, json={"detail": "Unavailable"})
        elif release_new_requests:
            route.continue_()
        else:
            pending.append((route, route.fetch()))

    page.route("**/api/fermentations?*", fail_then_delay)
    page.goto(str(api.base_url))
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=datetime.now(UTC).timestamp())
        ).status_code
        == 200
    )
    page.wait_for_timeout(1300)
    assert pending
    overview = page.get_by_role("region", name="Fermentazioni", exact=True)
    try:
        expect(overview.get_by_text("Nessuna fermentazione registrata.", exact=True)).to_have_count(
            0
        )
        expect(overview.get_by_role("alert")).to_contain_text("Non è stato possibile recuperare")
        release_new_requests = True
        for route, response in pending:
            route.fulfill(response=response)
        pending.clear()
        expect(
            overview.get_by_role("button", name=re.compile("^Apri IPA da recuperare"))
        ).to_be_visible()
        expect(overview.get_by_role("alert")).to_have_count(0)
    finally:
        for route, _ in pending:
            with suppress(PlaywrightError):
                route.abort()

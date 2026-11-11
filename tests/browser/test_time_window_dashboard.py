from collections.abc import Iterator
from datetime import datetime

import httpx
import pytest
from playwright.sync_api import Browser, Page, expect

from tests.payloads import fermentation_payload, gateway_lettura


@pytest.fixture
def page(browser: Browser, api: httpx.Client, width: int) -> Iterator[Page]:
    context = browser.new_context(
        locale="it-IT",
        has_touch=width == 390,
        is_mobile=width == 390,
        viewport={"width": width, "height": 1000},
    )
    yield context.new_page()
    context.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_period_loads_all_pages_and_freezes_until_return_to_live(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Periodo")).json()[
        "fermentation"
    ]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp()
    for index in range(405):
        api.post("/telemetry", json=gateway_lettura(timestamp=base + index * 60)).raise_for_status()
    page.goto(str(api.base_url) + "?fermentation=" + cycle["id"])
    expect(page.get_by_role("img", name="Grafico a linee: 405 letture", exact=True)).to_be_visible()
    page.get_by_label("Batteria %", exact=True).uncheck()
    for rows in (201, 6):
        page.get_by_role("button", name="Letture precedenti", exact=True).click()
        expect(
            page.get_by_role("table", name="Letture della fermentazione").get_by_role("row")
        ).to_have_count(rows)
    page.get_by_role("button", name="1h", exact=True).click()
    expect(page.get_by_role("button", name="Letture più recenti", exact=True)).to_be_disabled()
    expect(page.get_by_label("Batteria %", exact=True)).not_to_be_checked()
    expect(page.get_by_role("img", name="Grafico a linee: 61 letture", exact=True)).to_be_visible()
    selected = page.get_by_label("Intervallo visualizzato").inner_text()
    api.post("/telemetry", json=gateway_lettura(timestamp=base + 405 * 60)).raise_for_status()
    page.wait_for_timeout(1500)
    expect(page.get_by_label("Intervallo visualizzato")).to_have_text(selected)
    other = api.post("/api/pills", json={"name": "Altra", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    api.post(
        "/api/fermentations", json={"name": "Altro ciclo", "pill_id": other["id"]}
    ).raise_for_status()
    api.post(
        "/telemetry", json=gateway_lettura(pill_mac=other["mac"], timestamp=base + 90000)
    ).raise_for_status()
    page.wait_for_timeout(1200)
    expect(page.get_by_label("Intervallo visualizzato")).to_have_text(selected)
    page.get_by_role("button", name="Torna al live", exact=True).click()
    expect(page.get_by_label("Intervallo visualizzato")).not_to_have_text(selected)
    page.route(
        "**/api/fermentations/*/readings?*", lambda route: route.fulfill(status=503, body="{}")
    )
    page.get_by_role("button", name="6h", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Non è stato possibile")
    page.unroute("**/api/fermentations/*/readings?*")
    page.get_by_role("button", name="Riprova storico", exact=True).click()
    expect(page.get_by_role("alert")).to_have_count(0)


@pytest.mark.parametrize("width", [1440, 390])
def test_chart_gestures_and_keyboard_controls_expose_the_selected_interval(
    page: Page, api: httpx.Client, width: int
) -> None:
    page.set_viewport_size({"width": width, "height": 1000})
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Gesti")).json()[
        "fermentation"
    ]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp()
    for index in range(12):
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=base + index * 3600)
        ).raise_for_status()
    page.goto(str(api.base_url) + "?fermentation=" + cycle["id"])
    interval = page.get_by_label("Intervallo visualizzato")
    expect(interval).to_be_visible()
    canvas = page.get_by_role("img", name="Grafico a linee:", exact=False)
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    assert box is not None
    x, y = box["x"] + box["width"] * 0.6, box["y"] + box["height"] * 0.5
    before = interval.inner_text()
    page.mouse.move(x, y)
    page.mouse.wheel(0, -200)
    expect(interval).not_to_have_text(before)
    before = interval.inner_text()
    page.mouse.move(x - 80, y)
    page.mouse.down()
    page.mouse.move(x + 30, y, steps=8)
    page.mouse.up()
    expect(interval).not_to_have_text(before)
    page.get_by_role("button", name="Trascina per spostare", exact=True).click()
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    assert box is not None
    x, y = box["x"] + box["width"] * 0.6, box["y"] + box["height"] * 0.5
    before = interval.inner_text()
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 50, y, steps=8)
    page.mouse.up()
    expect(interval).not_to_have_text(before)
    before = interval.inner_text()
    page.get_by_label("Inizio intervallo", exact=True).focus()
    page.keyboard.press("ArrowRight")
    expect(interval).not_to_have_text(before)
    page.get_by_role("button", name="Tutto", exact=True).click()
    expect(page.get_by_role("img", name="Grafico a linee: 12 letture", exact=True)).to_be_visible()
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    assert box is not None
    x, y = box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5
    session = page.context.new_cdp_session(page)
    before = interval.inner_text()
    session.send(
        "Input.dispatchTouchEvent",
        {
            "type": "touchStart",
            "touchPoints": [{"x": x - 30, "y": y, "id": 1}, {"x": x + 30, "y": y, "id": 2}],
        },
    )
    session.send(
        "Input.dispatchTouchEvent",
        {
            "type": "touchMove",
            "touchPoints": [{"x": x - 70, "y": y, "id": 1}, {"x": x + 70, "y": y, "id": 2}],
        },
    )
    session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    expect(interval).not_to_have_text(before)
    before = interval.inner_text()
    session.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 3}]},
    )
    session.send(
        "Input.dispatchTouchEvent",
        {"type": "touchMove", "touchPoints": [{"x": x + 40, "y": y, "id": 3}]},
    )
    session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    expect(interval).not_to_have_text(before)
    session.detach()

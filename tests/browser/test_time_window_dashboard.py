from collections.abc import Iterator
from datetime import datetime
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from playwright.sync_api import APIResponse, Browser, Page, Route, expect

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
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=base + index * 60, specific_gravity=1.080 - index * 0.0001
            ),
        ).raise_for_status()
    page.goto(str(api.base_url) + "?fermentation=" + cycle["id"])
    # Loading all pages shares the application's ten-second request budget.
    expect(page.get_by_role("img", name="Grafico a linee: 405 letture", exact=True)).to_be_visible(
        timeout=15000
    )
    page.get_by_label("Batteria %", exact=True).uncheck()
    for rows in (201, 6):
        page.get_by_role("button", name="Letture precedenti", exact=True).click()
        expect(
            page.get_by_role("table", name="Letture della fermentazione").get_by_role("row")
        ).to_have_count(rows)
    page.get_by_role("button", name="1h", exact=True).click()
    preview = page.get_by_role("img", name="Anteprima densità: 405 letture", exact=True)
    expect(preview).to_be_visible()
    points = preview.locator("polyline").get_attribute("points")
    assert points is not None and len(points.split()) == 405
    assert float(points.split()[0].split(",")[1]) == 8
    assert float(points.split()[-1].split(",")[1]) == 72
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        page.get_by_role("region", name="Navigazione temporale").screenshot(
            path=Path(directory) / f"navigatore-{width}.png"
        )
    preview_box = preview.bounding_box()
    chart_box = page.get_by_role(
        "img", name="Grafico a linee: 61 letture", exact=True
    ).bounding_box()
    assert preview_box is not None and chart_box is not None
    assert preview_box["y"] < chart_box["y"]
    assert preview_box["width"] > chart_box["width"] * 0.85
    expect(page.get_by_role("button", name="Letture più recenti", exact=True)).to_be_disabled()
    expect(page.get_by_label("Batteria %", exact=True)).not_to_be_checked()
    expect(page.get_by_role("img", name="Grafico a linee: 61 letture", exact=True)).to_be_visible()
    selected = page.get_by_label("Intervallo visualizzato").inner_text()
    api.post("/telemetry", json=gateway_lettura(timestamp=base + 405 * 60)).raise_for_status()
    page.wait_for_timeout(1500)
    expect(page.get_by_label("Intervallo visualizzato")).to_have_text(selected)
    expect(
        page.get_by_role("img", name="Anteprima densità: 406 letture", exact=True)
    ).to_be_visible()
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
    expect(
        page.get_by_role("img", name="Anteprima densità: 406 letture", exact=True)
    ).to_be_visible()
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


@pytest.mark.parametrize("width", [1440, 390])
def test_overview_window_moves_without_changing_duration_and_clamps_to_bounds(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Finestra mobile")
    ).json()["fermentation"]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp()
    for index in range(12):
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=base + index * 3600)
        ).raise_for_status()
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    page.get_by_role("button", name="1h", exact=True).click()
    selection = page.get_by_role("slider", name="Periodo selezionato", exact=True)
    expect(selection).to_be_visible()
    start = page.get_by_label("Inizio intervallo", exact=True)
    end = page.get_by_label("Fine intervallo", exact=True)
    minimum = float(start.get_attribute("min") or "nan")
    assert float(end.input_value()) - float(start.input_value()) == pytest.approx(3600)
    selection.scroll_into_view_if_needed()
    box = selection.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] * 0.85)
    page.mouse.down()
    page.mouse.move(box["x"] - 50, box["y"] + box["height"] * 0.85, steps=8)
    page.mouse.up()
    expect(start).not_to_have_value(str(base + 36000))
    assert float(start.input_value()) < base + 36000
    assert float(end.input_value()) - float(start.input_value()) == pytest.approx(3600)
    selection.focus()
    selection.press("Home")
    assert float(start.input_value()) == minimum
    selection.press("ArrowLeft")
    assert float(start.input_value()) == minimum
    selection.press("End")
    assert float(end.input_value()) == pytest.approx(base + 39600, rel=0, abs=0.00001)
    assert float(end.input_value()) - float(start.input_value()) == pytest.approx(3600)
    expect(page.get_by_text("Intervallo fermo", exact=True)).to_be_visible()
    selection.scroll_into_view_if_needed()
    box = selection.bounding_box()
    assert box is not None
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] * 0.85
    session = page.context.new_cdp_session(page)
    session.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]},
    )
    session.send(
        "Input.dispatchTouchEvent",
        {"type": "touchMove", "touchPoints": [{"x": x - 40, "y": y, "id": 1}]},
    )
    session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    session.detach()
    assert float(end.input_value()) < base + 39600
    assert float(end.input_value()) - float(start.input_value()) == pytest.approx(3600)
    # Both real thumbs share the preview. Move the start thumb with the mouse,
    # independently of the center region and keyboard alternatives.
    page.get_by_role("button", name="Tutto", exact=True).click()
    start.scroll_into_view_if_needed()
    box = start.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 12, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] / 2, steps=8)
    page.mouse.up()
    assert float(start.input_value()) > minimum + 1000
    assert float(end.input_value()) == pytest.approx(base + 39600, rel=0, abs=0.00001)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
def test_empty_and_single_reading_keep_tiny_windows_accessible(
    page: Page, api: httpx.Client, width: int
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Prima lettura")).json()[
        "fermentation"
    ]
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    expect(
        page.get_by_text("In attesa della prima lettura della fermentazione", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("region", name="Navigazione temporale")).to_have_count(0)
    base = datetime.fromisoformat(cycle["started_at"]).timestamp()
    api.post("/telemetry", json=gateway_lettura(timestamp=base + 1)).raise_for_status()
    expect(page.get_by_role("img", name="Anteprima densità: 1 lettura", exact=True)).to_be_visible()
    start = page.get_by_label("Inizio intervallo", exact=True)
    end = page.get_by_label("Fine intervallo", exact=True)
    start.focus()
    start.press("End")
    assert 0 < float(end.input_value()) - float(start.input_value()) < 0.002
    start.press("ArrowRight")
    end.focus()
    end.press("Home")
    assert float(start.input_value()) < float(end.input_value())
    window = page.get_by_role("slider", name="Periodo selezionato", exact=True)
    window.focus()
    window.press("Home")
    window.press("End")
    assert float(start.input_value()) < float(end.input_value())
    page.get_by_role("button", name="Ingrandisci", exact=True).click()
    expect(page.get_by_text("Caricamento storico…", exact=True)).to_have_count(0)
    assert float(start.input_value()) < float(end.input_value())
    assert errors == []


@pytest.mark.parametrize("width", [1440, 390])
def test_late_history_response_does_not_replace_the_newer_period(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Risposte invertite")
    ).json()["fermentation"]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp()
    for index in range(12):
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=base + index * 3600)
        ).raise_for_status()
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    expect(page.get_by_role("img", name="Grafico a linee: 12 letture", exact=True)).to_be_visible()
    page.get_by_label("Batteria %", exact=True).check()
    delayed: list[tuple[Route, APIResponse]] = []

    def hold_old_context(route: Route) -> None:
        query = parse_qs(urlsplit(route.request.url).query)
        if float(query["from_timestamp"][0]) == base + 18000:
            delayed.append((route, route.fetch()))
        else:
            route.continue_()

    page.route("**/chart-context?*", hold_old_context)
    with page.expect_request(lambda request: "/chart-context?" in request.url):
        page.get_by_role("button", name="6h", exact=True).click()
    page.get_by_role("button", name="1h", exact=True).click()
    expect(page.get_by_role("img", name="Grafico a linee: 2 letture", exact=True)).to_be_visible()
    selected = page.get_by_label("Intervallo visualizzato").inner_text()
    assert len(delayed) == 1
    for route, response in delayed:
        route.fulfill(response=response)
    page.wait_for_timeout(200)
    expect(page.get_by_label("Intervallo visualizzato")).to_have_text(selected)
    expect(page.get_by_label("Batteria %", exact=True)).to_be_checked()
    expect(page.get_by_role("img", name="Grafico a linee: 2 letture", exact=True)).to_be_visible()
    expect(
        page.get_by_role("img", name="Anteprima densità: 12 letture", exact=True)
    ).to_be_visible()

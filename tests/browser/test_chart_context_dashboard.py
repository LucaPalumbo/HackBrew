"""Observe rendered curve geometry, never private Chart.js datasets."""

import os
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.browser.navigation import open_raw_readings
from tests.payloads import fermentation_payload, gateway_lettura


def select_window(page: Page, start: float, end: float) -> None:
    with page.expect_response(lambda response: "/chart-context?" in response.url):
        for label, value in (("Inizio intervallo", start), ("Fine intervallo", end)):
            page.get_by_label(label, exact=True).evaluate(
                """(input, value) => {
                  input.value = String(value);
                  input.dispatchEvent(new Event('input', {bubbles: true}));
                }""",
                value,
            )
    expect(page.get_by_text("Caricamento storico…", exact=True)).to_have_count(0)
    assert float(page.get_by_label("Fine intervallo", exact=True).input_value()) == pytest.approx(
        end, rel=0, abs=0.00001
    )


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("span", [100, 10000000])
def test_crossing_curve_fills_the_window_with_visible_scales_and_no_synthetic_samples(
    page: Page, api: httpx.Client, width: int, span: int
) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Zoom reale")).json()[
        "fermentation"
    ]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp() + 1
    for offset, temperature in ((0, 0), (span, 40)):
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=base + offset, temperature=temperature, accel_x=0.5),
        ).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    chart = page.get_by_role("region", name="Grafico delle misure", exact=True)
    expect(chart.get_by_role("checkbox", checked=True)).to_have_count(2)
    # Optional series must also be absent from the initial rendered canvas,
    # before toggling a checkbox can synchronize Chart.js visibility.
    assert chart.get_by_role("img").evaluate("""canvas => {
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 0; i < pixels.length; i += 4)
        if (pixels[i] < 40 && pixels[i+1] > 110 && pixels[i+2] > 110 &&
            pixels[i+3] > 100) return false;
      return true;
    }""")
    chart.get_by_role("checkbox", name="Densità SG", exact=True).uncheck()
    select_window(page, base + span / 2 - 10, base + span / 2 + 10)
    canvas = chart.get_by_role("img", name="Grafico a linee: 0 letture", exact=True)
    expect(canvas).to_be_visible()
    # A real segment must span both axes of the visible bitmap. Keeping the
    # outside extrema as Y bounds would flatten this line to 20% of its height.
    page.wait_for_function(
        """canvas => {
      const {width, height} = canvas;
      const rgba = canvas.getContext('2d').getImageData(0, 0, width, height).data;
      let left = width, right = 0, top = height, bottom = 0;
      for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        const i = (y * width + x) * 4;
        if (rgba[i] > 120 && rgba[i] > rgba[i+1] * 1.6 && rgba[i] > rgba[i+2] * 1.6 &&
            rgba[i+3] > 100) {
          left = Math.min(left, x); right = Math.max(right, x);
          top = Math.min(top, y); bottom = Math.max(bottom, y);
        }
      }
      return right - left > width * .55 && bottom - top > height * .45;
    }""",
        arg=canvas.element_handle(),
    )
    canvas.hover()
    expect(chart.get_by_role("status", name="Valori nel grafico", exact=True)).to_have_count(0)
    if (directory := os.environ.get("HACKBREW_SCREENSHOT_DIR")) and span == 100:
        chart.screenshot(path=Path(directory) / f"grafico-contesto-{width}.png")
    ordinary = api.get(
        f"/api/fermentations/{cycle['id']}/readings",
        params={"from_timestamp": base + span / 2 - 10, "to_timestamp": base + span / 2 + 10},
    ).json()
    assert ordinary["readings"] == []
    assert len(api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"]) == 2
    select_window(page, base - 0.9, base - 0.5)
    # There is only a successor here: no predecessor means no extrapolated line.
    assert canvas.evaluate("""canvas => {
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 0; i < pixels.length; i += 4)
        if (pixels[i] > 120 && pixels[i] > pixels[i+1] * 1.6 && pixels[i] > pixels[i+2] * 1.6 &&
            pixels[i+3] > 100) return false;
      return true;
    }""")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1440, 390])
def test_each_optional_curve_uses_usable_context_across_invalid_rows(
    page: Page, api: httpx.Client, width: int
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Contesto opzionale")
    ).json()["fermentation"]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp() + 1
    for offset in (0, 10, 20, 30, 40):
        payload = gateway_lettura(
            timestamp=base + offset,
            valid=offset in (0, 40),
            gravity_velocity=offset - 20,
            accel_x=offset - 20,
        )
        if offset in (10, 20, 30):
            payload.pop("accel_x")
            payload["gravity_velocity"] = -999
        api.post("/telemetry", json=payload).raise_for_status()
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{api.base_url}?fermentation={cycle['id']}")
    chart = page.get_by_role("region", name="Grafico delle misure", exact=True)
    expect(chart.get_by_role("img", name="Grafico a linee: 5 letture", exact=True)).to_be_visible()
    for checkbox in chart.get_by_role("checkbox").all():
        checkbox.uncheck()
    select_window(page, base + 15, base + 25)
    expect(chart.get_by_role("img", name="Grafico a linee: 1 lettura", exact=True)).to_be_visible()
    expect(page.get_by_text("Caricamento storico…", exact=True)).to_have_count(0)
    canvas = chart.get_by_role("img")
    for label, kind in (
        ("Velocità densità · punti SG/giorno", "velocity"),
        ("Accelerazione X · unità non specificata", "acceleration"),
    ):
        checkbox = chart.get_by_role("checkbox", name=label, exact=True)
        checkbox.check()
        if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
            canvas.screenshot(path=Path(directory) / f"contesto-{kind}-{width}.png")
        page.wait_for_function(
            """({canvas, kind}) => {
          const {width, height} = canvas;
          const data = canvas.getContext('2d').getImageData(0, 0, width, height).data;
          let left = width, right = 0, top = height, bottom = 0;
          for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
            const i = (y * width + x) * 4, r = data[i], g = data[i+1], b = data[i+2];
            const colored = kind === 'velocity'
              ? b > 110 && b > r * 1.15 && b > g * 1.4 && r > 70
              : g > 70 && b > 70 && r < 80;
            if (colored && data[i+3] > 100) {
              left = Math.min(left, x); right = Math.max(right, x);
              top = Math.min(top, y); bottom = Math.max(bottom, y);
            }
          }
          return right - left > width * .55 && bottom - top > height * .45;
        }""",
            arg={"canvas": canvas.element_handle(), "kind": kind},
        )
        checkbox.uncheck()
    open_raw_readings(page)
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("row")).to_have_count(2)
    expect(table.get_by_role("cell", name="Non valida", exact=True)).to_be_visible()

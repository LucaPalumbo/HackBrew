"""The combined chart and its exact values are observable through the browser."""

import os
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.payloads import fermentation_payload, gateway_lettura


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_one_chart_exposes_seven_series_and_exact_values(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Misure complete")
    ).json()["fermentation"]
    timestamp = datetime.fromisoformat(cycle["started_at"]).timestamp() + 0.000123
    api.post(
        "/telemetry",
        json=gateway_lettura(
            timestamp=timestamp,
            valid=True,
            gravity_velocity=-2.125,
            accel_x=-1.25,
            accel_y=0.75,
            accel_z=2.5,
        ),
    ).raise_for_status()
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url) + "?fermentation=" + cycle["id"])
    chart = page.get_by_role("region", name="Grafico delle misure", exact=True)
    expect(chart.get_by_role("img", name="Grafico a linee: 1 lettura", exact=True)).to_be_visible()
    expect(page.get_by_role("img")).to_have_count(1)
    legend = chart.get_by_role("group", name="Serie del grafico", exact=True)
    expect(legend.get_by_role("checkbox")).to_have_count(7)
    for label in (
        "Temperatura °C",
        "Densità SG",
        "Batteria %",
        "Velocità densità · punti SG/giorno",
        "Accelerazione X · unità non specificata",
        "Accelerazione Y · unità non specificata",
        "Accelerazione Z · unità non specificata",
    ):
        expect(legend.get_by_role("checkbox", name=label, exact=True)).to_be_checked()
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("columnheader")).to_have_count(8)
    for value in ("1.050125", "19,6875", "63,2734375", "-2,125", "-1,25", "0,75", "2,5"):
        expect(table.get_by_role("cell", name=value, exact=True)).to_be_visible()
    if width == 390:
        temperature_toggle = legend.get_by_role("checkbox", name="Temperatura °C", exact=True)
        temperature_toggle.uncheck()
        expect(chart.get_by_label("Scala graduata", exact=True)).to_have_value("density")
        temperature_toggle.check()
        scroller = page.get_by_label("Scorri le letture storiche", exact=True)
        scroller.focus()
        scroller.press("ArrowRight")
        page.wait_for_function("element => element.scrollLeft > 0", arg=scroller.element_handle())
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_sparse_samples_are_connected_by_a_visible_line_and_legend_controls_it(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Campioni distanti")
    ).json()["fermentation"]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp() + 0.000123
    for offset, temperature, gravity, battery, x, y, z in (
        (0, 17.125, 1060, 83.5, -1.5, 0.25, 2.75),
        (259200, 23.75, 1030, 67.25, 1.75, -0.5, 0.25),
    ):
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=base + offset,
                temperature=temperature,
                specific_gravity=gravity,
                battery=battery,
                valid=True,
                gravity_velocity=-2.125,
                accel_x=x,
                accel_y=y,
                accel_z=z,
            ),
        ).raise_for_status()
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url) + "?fermentation=" + cycle["id"])
    chart = page.get_by_role("region", name="Grafico delle misure", exact=True)
    canvas = chart.get_by_role("img", name="Grafico a linee: 2 letture", exact=True)
    expect(canvas).to_be_visible()
    if width == 390:
        chart.get_by_label("Scala graduata", exact=True).select_option("density")
        expect(chart.get_by_role("checkbox", checked=True)).to_have_count(7)
        chart.get_by_label("Scala graduata", exact=True).select_option("temperature")
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        chart.screenshot(path=Path(directory) / f"grafico-combinato-{width}.png")
    for checkbox in chart.get_by_role("checkbox").all():
        if checkbox.get_attribute("aria-label") != "Temperatura °C":
            checkbox.uncheck()
    # Observe the painted bitmap, not any Chart.js object: two isolated markers
    # cannot paint a red trace across the middle third of the canvas.
    page.wait_for_function(
        """canvas => {
      const {width, height} = canvas;
      const pixels = canvas.getContext('2d').getImageData(0, 0, width, height).data;
      let columns = 0;
      for (let x = Math.floor(width / 3); x < Math.floor(width * 2 / 3); x++) {
        for (let y = 0; y < height; y++) {
          const i = (y * width + x) * 4;
          if (pixels[i] > 120 && pixels[i] > pixels[i+1] * 1.6 &&
              pixels[i] > pixels[i+2] * 1.6 && pixels[i+3] > 100) {
            columns++; break;
          }
        }
      }
      return columns > width / 8;
    }""",
        arg=canvas.element_handle(),
    )
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        chart.screenshot(path=Path(directory) / f"linea-campioni-distanti-{width}.png")
    canvas.hover()
    tooltip = chart.get_by_role("status", name="Valori nel grafico", exact=True)
    expect(tooltip).to_contain_text("°C")
    chart.get_by_role("checkbox", name="Temperatura °C", exact=True).uncheck()
    expect(chart.get_by_text("Nessuna serie selezionata.", exact=False)).to_be_visible()
    expect(
        page.get_by_role("table", name="Letture della fermentazione").get_by_role("row")
    ).to_have_count(3)
    temperature_toggle = chart.get_by_role("checkbox", name="Temperatura °C", exact=True)
    temperature_toggle.focus()
    temperature_toggle.press("Space")
    expect(temperature_toggle).to_be_checked()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_missing_optional_values_and_invalid_velocity_do_not_hide_other_measurements(
    page: Page, api: httpx.Client
) -> None:
    cycle = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Qualità delle misure")
    ).json()["fermentation"]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp() + 0.000123
    page.goto(str(api.base_url) + "?fermentation=" + cycle["id"])
    expect(
        page.get_by_text("Nessuna lettura registrata per questa fermentazione.", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("img")).to_have_count(0)
    first = gateway_lettura(
        timestamp=base,
        temperature=18.125,
        valid=False,
        gravity_velocity=-99.5,
        accel_x=-1.125,
        accel_y=0.625,
        accel_z=2.75,
    )
    api.post("/telemetry", json=first).raise_for_status()
    table = page.get_by_role("table", name="Letture della fermentazione")
    row = table.get_by_role("row").nth(1)
    expect(
        row.get_by_role("cell", name="Non disponibile (velocità non valida)", exact=True)
    ).to_be_visible()
    expect(row.get_by_role("cell", name="18,125", exact=True)).to_be_visible()
    expect(row.get_by_role("cell", name="-1,125", exact=True)).to_be_visible()
    expect(row.get_by_role("cell", name="-99,5", exact=True)).to_have_count(0)
    optional = gateway_lettura(timestamp=base + 1, specific_gravity=1042.125, battery=0)
    for field in ("valid", "gravity_velocity", "accel_x", "accel_y", "accel_z"):
        del optional[field]
    api.post("/telemetry", json=optional).raise_for_status()
    expect(table.get_by_role("row")).to_have_count(3)
    missing = table.get_by_role("row").nth(2)
    expect(missing.get_by_role("cell", name="Non disponibile", exact=True)).to_have_count(4)
    expect(missing.get_by_role("cell", name="0", exact=True)).to_have_count(1)
    expect(missing.get_by_role("cell", name="1.042125", exact=True)).to_be_visible()
    page.reload()
    expect(table.get_by_role("row")).to_have_count(3)


def test_live_chart_preserves_selected_series_and_separates_parallel_sources(
    page: Page, api: httpx.Client
) -> None:
    first_pill = api.get("/api/pills").json()["pills"][0]
    second_pill = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    first = api.post(
        "/api/fermentations", json={"name": "IPA grafico", "pill_id": first_pill["id"]}
    ).json()["fermentation"]
    second = api.post(
        "/api/fermentations", json={"name": "Stout grafico", "pill_id": second_pill["id"]}
    ).json()["fermentation"]
    base = (
        max(datetime.fromisoformat(cycle["started_at"]).timestamp() for cycle in (first, second))
        + 0.000123
    )
    api.post(
        "/telemetry", json=gateway_lettura(timestamp=base, valid=True, accel_x=-0.125)
    ).raise_for_status()
    page.goto(str(api.base_url) + "?fermentation=" + first["id"])
    chart = page.get_by_role("region", name="Grafico delle misure", exact=True)
    density = chart.get_by_role("checkbox", name="Densità SG", exact=True)
    expect(density).to_be_checked()
    density.uncheck()
    api.post(
        "/telemetry",
        json=gateway_lettura(
            pill_mac=second_pill["mac"], timestamp=base, specific_gravity=1099, accel_x=999
        ),
    ).raise_for_status()
    api.post(
        "/telemetry",
        json=gateway_lettura(
            timestamp=base + 3, specific_gravity=1040.125, valid=True, accel_x=-0.75
        ),
    ).raise_for_status()
    expect(chart.get_by_role("img", name="Grafico a linee: 2 letture", exact=True)).to_be_visible()
    expect(density).not_to_be_checked()
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("cell", name="999", exact=True)).to_have_count(0)
    expect(table.get_by_role("cell", name="-0,75", exact=True)).to_be_visible()
    # Equal acquisition timestamps stay distinct; the delayed sample is inserted in order.
    for gravity, x in ((1045.25, -0.5), (1046.125, -0.625)):
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=base + 1, specific_gravity=gravity, valid=True, accel_x=x
            ),
        ).raise_for_status()
    expect(table.get_by_role("row")).to_have_count(5)
    for index, displayed_gravity in enumerate(
        ("1.050125", "1.04525", "1.046125", "1.040125"), start=1
    ):
        expect(
            table.get_by_role("row")
            .nth(index)
            .get_by_role("cell", name=displayed_gravity, exact=True)
        ).to_be_visible()
    expect(density).not_to_be_checked()
    assert page.url.endswith("fermentation=" + first["id"])


def test_tooltip_shows_one_complete_original_sample_when_timestamps_are_equal(
    page: Page, api: httpx.Client
) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Stesso istante")).json()[
        "fermentation"
    ]
    timestamp = datetime.fromisoformat(cycle["started_at"]).timestamp() + 0.000123
    for temperature, gravity, battery, velocity, x, y, z in (
        (18, 1060, 80, -1, 1, 2, 3),
        (22, 1040, 60, -2, 4, 5, 6),
    ):
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=timestamp,
                temperature=temperature,
                specific_gravity=gravity,
                battery=battery,
                valid=True,
                gravity_velocity=velocity,
                accel_x=x,
                accel_y=y,
                accel_z=z,
            ),
        ).raise_for_status()
    page.goto(str(api.base_url) + "?fermentation=" + cycle["id"])
    chart = page.get_by_role("region", name="Grafico delle misure", exact=True)
    chart.get_by_role("img", name="Grafico a linee: 2 letture", exact=True).hover()
    tooltip = chart.get_by_role("status", name="Valori nel grafico", exact=True)
    expect(tooltip.get_by_role("definition")).to_have_count(7)
    values = tooltip.get_by_role("definition").all_text_contents()
    assert values in (
        [
            "18,0 °C",
            "1.060 SG",
            "80 %",
            "-1 punti SG/giorno",
            "1 unità non specificata",
            "2 unità non specificata",
            "3 unità non specificata",
        ],
        [
            "22,0 °C",
            "1.040 SG",
            "60 %",
            "-2 punti SG/giorno",
            "4 unità non specificata",
            "5 unità non specificata",
            "6 unità non specificata",
        ],
    )

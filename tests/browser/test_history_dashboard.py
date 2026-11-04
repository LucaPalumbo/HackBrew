from datetime import UTC, datetime

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.payloads import fermentation_payload, gateway_lettura


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_active_charts_and_table_update_with_real_letture(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    api.post("/api/fermentations", json=fermentation_payload(api, "IPA live")).raise_for_status()
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url))
    expect(
        page.get_by_text("I grafici appariranno alla prima lettura.", exact=True)
    ).to_be_visible()
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=datetime.now(UTC).timestamp())
        ).status_code
        == 200
    )
    expect(page.get_by_role("img", name="Densità SG: 1 lettura")).to_be_visible()
    expect(page.get_by_role("img", name="Temperatura °C: 1 lettura")).to_be_visible()
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("cell", name="1.050", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="19,7", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="63", exact=True)).to_be_visible()

    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=datetime.now(UTC).timestamp(),
                specific_gravity=1040.125,
                temperature=20.5,
                battery=62,
            ),
        ).status_code
        == 200
    )
    expect(page.get_by_role("img", name="Densità SG: 2 letture")).to_be_visible()
    expect(table.get_by_role("cell", name="1.040", exact=True)).to_be_visible()
    expect(table.get_by_role("row")).to_have_count(3)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_selected_concluded_history_stays_separate_from_new_live_data_and_survives_reload(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    page.set_default_timeout(5000)
    for name, gravity, temperature, battery in [
        ("Prima IPA", 1060, 18, 80),
        ("Seconda stout", 1040, 20, 60),
    ]:
        fermentation = api.post("/api/fermentations", json=fermentation_payload(api, name)).json()[
            "fermentation"
        ]
        assert (
            api.post(
                "/telemetry",
                json=gateway_lettura(
                    timestamp=datetime.now(UTC).timestamp(),
                    specific_gravity=gravity,
                    temperature=temperature,
                    battery=battery,
                ),
            ).status_code
            == 200
        )
        assert api.post(f"/api/fermentations/{fermentation['id']}/end").status_code == 200
    assert (
        api.post("/api/fermentations", json=fermentation_payload(api, "Terza attiva")).status_code
        == 201
    )
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=datetime.now(UTC).timestamp(), specific_gravity=1030),
        ).status_code
        == 200
    )
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url))
    page.get_by_role("button", name="Apri Prima IPA").click()
    expect(page.get_by_role("heading", name="Storico: Prima IPA", exact=True)).to_be_visible()
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="18,0", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="80", exact=True)).to_be_visible()
    expect(page.get_by_label("Riepilogo storico")).to_contain_text("1.060 SG")

    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=datetime.now(UTC).timestamp(), specific_gravity=1020),
        ).status_code
        == 200
    )
    expect(page.get_by_role("heading", name="Storico: Prima IPA", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name="Storico: Prima IPA", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_be_visible()

    page.get_by_role("button", name="Apri Seconda stout").click()
    expect(page.get_by_role("heading", name="Storico: Seconda stout", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="1.040", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="60", exact=True)).to_be_visible()
    page.go_back()
    expect(page.get_by_role("heading", name="Storico: Prima IPA", exact=True)).to_be_visible()
    page.get_by_role("button", name="Monitoraggio attuale", exact=True).click()
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.020", exact=True)
    ).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

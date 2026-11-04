from datetime import datetime

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.payloads import fermentation_payload, gateway_lettura


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_delayed_samples_enrich_history_without_replacing_current_values(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    first = api.post("/api/fermentations", json=fermentation_payload(api, "Prima IPA")).json()[
        "fermentation"
    ]
    first_timestamp = datetime.fromisoformat(first["started_at"]).timestamp() + 0.000123
    assert api.post(f"/api/fermentations/{first['id']}/end").status_code == 200
    second = api.post("/api/fermentations", json=fermentation_payload(api, "Seconda IPA")).json()[
        "fermentation"
    ]
    second_start = datetime.fromisoformat(second["started_at"]).timestamp()
    newest = gateway_lettura(timestamp=second_start + 0.000124, specific_gravity=1040)
    assert api.post("/telemetry", json=newest).status_code == 200
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url))
    density = page.get_by_role("region", name="Densità")
    expect(density.get_by_text("1.040", exact=True)).to_be_visible()
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(table.get_by_role("row")).to_have_count(2)

    older = gateway_lettura(timestamp=second_start + 0.000123, specific_gravity=1050)
    for _ in range(2):
        assert api.post("/telemetry", json=older).status_code == 200
    expect(table.get_by_role("cell", name="1.050", exact=True)).to_be_visible()
    expect(table.get_by_role("row")).to_have_count(3)
    expect(density.get_by_text("1.040", exact=True)).to_be_visible()
    expect(
        table.get_by_role("row").nth(1).get_by_role("cell", name="1.050", exact=True)
    ).to_be_visible()
    expect(
        table.get_by_role("row").nth(2).get_by_role("cell", name="1.040", exact=True)
    ).to_be_visible()
    assert api.post("/telemetry", json=newest).status_code == 200
    expect(table.get_by_role("row")).to_have_count(3)

    for _ in range(2):
        assert (
            api.post(
                "/telemetry", json=gateway_lettura(timestamp=first_timestamp, specific_gravity=1060)
            ).status_code
            == 200
        )
    expect(density.get_by_text("1.040", exact=True)).to_be_visible()
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Apri Prima IPA").click()
    expect(table.get_by_role("row")).to_have_count(2)
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_be_visible()
    page.get_by_role("button", name="Monitoraggio attuale", exact=True).click()
    expect(density.get_by_text("1.040", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

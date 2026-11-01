import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.payloads import gateway_lettura


def test_dashboard_explains_that_no_lettura_has_arrived(page: Page, api: httpx.Client) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(str(api.base_url))

    expect(page.get_by_role("heading", name="In attesa della prima lettura")).to_be_visible()
    expect(page.get_by_role("button", name="Aggiorna lettura")).to_be_enabled()


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_latest_lettura_is_visible_and_refreshable_on_desktop_and_phone(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url))

    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.050", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("region", name="Temperatura").get_by_text("19,7", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("region", name="Batteria").get_by_text("63", exact=True)
    ).to_be_visible()
    expect(page.get_by_label("Acquisizione della lettura")).to_have_attribute(
        "datetime", "2023-11-14T22:13:20.123Z"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=path / f"dashboard-{width}.png", full_page=True)

    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=1700000001.123456, specific_gravity=1040.125),
        ).status_code
        == 200
    )
    page.get_by_role("button", name="Aggiorna lettura").click()
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible()
    page.reload()
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible()

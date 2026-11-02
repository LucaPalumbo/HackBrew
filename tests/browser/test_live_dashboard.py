from datetime import UTC, datetime

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.payloads import gateway_lettura


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_new_letture_update_open_dashboard_without_reload(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url))
    expect(page.get_by_role("heading", name="In attesa della prima lettura")).to_be_visible()
    timestamp = int(datetime.now(UTC).timestamp())
    assert api.post("/telemetry", json=gateway_lettura(timestamp=timestamp)).status_code == 200
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.050", exact=True)
    ).to_be_visible()

    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=timestamp + 1, specific_gravity=1040.125, temperature=20.5, battery=62
            ),
        ).status_code
        == 200
    )
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("region", name="Temperatura").get_by_text("20,5", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("region", name="Batteria").get_by_text("62", exact=True)
    ).to_be_visible()
    expect(page.get_by_label("Acquisizione della lettura")).to_have_attribute(
        "datetime",
        datetime.fromtimestamp(timestamp + 1, UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    )
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_lettura_becomes_stale_without_new_events_and_keeps_real_values(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    timestamp = int(datetime.now(UTC).timestamp())
    assert api.post("/telemetry", json=gateway_lettura(timestamp=timestamp)).status_code == 200
    page.set_viewport_size({"width": width, "height": height})
    # The server's clock determines freshness even if the browser clock is wrong.
    page.clock.install(time=datetime(2000, 1, 1, tzinfo=UTC))
    page.goto(str(api.base_url))
    expect(page.get_by_label("Stato dei dati")).to_have_text("Lettura disponibile")
    acquired_at = page.get_by_label("Acquisizione della lettura").get_attribute("datetime")

    page.clock.fast_forward(61_000)
    expect(page.get_by_label("Stato dei dati")).to_have_text("Dati non aggiornati")
    expect(page.get_by_label("Acquisizione della lettura")).to_have_attribute(
        "datetime", acquired_at or ""
    )
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.050", exact=True)
    ).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    assert api.post("/telemetry", json=gateway_lettura(timestamp=timestamp + 1)).status_code == 200
    expect(page.get_by_label("Stato dei dati")).to_have_text("Lettura disponibile")


def test_dashboard_recovers_persisted_lettura_after_failed_live_connection(
    page: Page, api: httpx.Client
) -> None:
    timestamp = int(datetime.now(UTC).timestamp()) - 120
    assert api.post("/telemetry", json=gateway_lettura(timestamp=timestamp)).status_code == 200
    page.route("**/api/readings/events", lambda route: route.abort("internetdisconnected"))
    page.goto(str(api.base_url))
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.050", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("alert")).to_contain_text("Riconnessione automatica")
    expect(page.get_by_label("Stato dei dati")).to_have_text("Dati non aggiornati")

    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=timestamp + 1, specific_gravity=1040.125)
        ).status_code
        == 200
    )
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.050", exact=True)
    ).to_be_visible()
    page.unroute("**/api/readings/events")

    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible(timeout=10000)
    expect(page.get_by_label("Collegamento live")).to_have_text("Collegamento live attivo")
    expect(page.get_by_role("alert")).to_have_count(0)


def test_live_connection_recovers_after_browser_goes_offline(page: Page, api: httpx.Client) -> None:
    timestamp = int(datetime.now(UTC).timestamp())
    assert api.post("/telemetry", json=gateway_lettura(timestamp=timestamp)).status_code == 200
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(str(api.base_url))
    expect(page.get_by_label("Collegamento live")).to_have_text("Collegamento live attivo")

    page.context.set_offline(True)
    expect(page.get_by_role("alert")).to_contain_text("Riconnessione automatica")
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=timestamp + 1, specific_gravity=1030.125)
        ).status_code
        == 200
    )
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.050", exact=True)
    ).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    page.context.set_offline(False)
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.030", exact=True)
    ).to_be_visible(timeout=10000)
    expect(page.get_by_label("Collegamento live")).to_have_text("Collegamento live attivo")
    expect(page.get_by_role("alert")).to_have_count(0)

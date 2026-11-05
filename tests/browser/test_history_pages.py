from datetime import datetime

import httpx
from playwright.sync_api import Page, expect

from tests.payloads import fermentation_payload, gateway_lettura


def test_phone_can_page_through_all_original_letture(page: Page, api: httpx.Client) -> None:
    fermentation = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA lunga")
    ).json()["fermentation"]
    base = datetime.fromisoformat(fermentation["started_at"]).timestamp() + 0.000123
    for number in range(205):
        gravity = 1060 if number == 0 else 1040 if number == 204 else 1050.125
        assert (
            api.post(
                "/telemetry",
                json=gateway_lettura(timestamp=base + number * 0.000001, specific_gravity=gravity),
            ).status_code
            == 200
        )
    assert api.post(f"/api/fermentations/{fermentation['id']}/end").status_code == 200
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(str(api.base_url))
    page.get_by_role("button", name="Apri IPA lunga").click()
    table = page.get_by_role("table", name="Letture della fermentazione")
    expect(page.get_by_role("img", name="Grafico a linee: 200 letture")).to_be_visible()
    expect(table.get_by_role("row")).to_have_count(201)
    expect(table.get_by_role("cell", name="1.040", exact=True)).to_be_visible()
    page.get_by_role("button", name="Letture precedenti", exact=True).click()
    expect(page.get_by_role("img", name="Grafico a linee: 5 letture")).to_be_visible()
    expect(table.get_by_role("row")).to_have_count(6)
    expect(table.get_by_role("cell", name="1.060", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Letture precedenti", exact=True)).to_be_disabled()
    page.get_by_role("button", name="Letture più recenti", exact=True).click()
    expect(page.get_by_role("img", name="Grafico a linee: 200 letture")).to_be_visible()
    expect(table.get_by_role("cell", name="1.040", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_empty_concluded_history_and_failed_load_do_not_show_diagnostic_values(
    page: Page, api: httpx.Client
) -> None:
    fermentation = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Senza letture")
    ).json()["fermentation"]
    assert api.post(f"/api/fermentations/{fermentation['id']}/end").status_code == 200
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
    page.goto(str(api.base_url))
    page.route("**/api/fermentations/*/readings?*", lambda route: route.abort("connectionfailed"))
    page.get_by_role("button", name="Apri Senza letture").click()
    expect(page.get_by_role("alert")).to_contain_text("Non è stato possibile recuperare lo storico")
    expect(page.get_by_role("region", name="Densità")).to_have_count(0)
    expect(page.get_by_role("table", name="Letture della fermentazione")).to_have_count(0)
    page.unroute("**/api/fermentations/*/readings?*")
    page.get_by_role("button", name="Riprova storico").click()
    expect(page.get_by_role("heading", name="Storico: Senza letture", exact=True)).to_be_visible()
    expect(
        page.get_by_text("Nessuna lettura registrata per questa fermentazione.", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("img")).to_have_count(0)
    expect(page.get_by_role("alert")).to_have_count(0)

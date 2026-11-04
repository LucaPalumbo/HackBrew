from datetime import UTC, datetime

import httpx
import pytest
from playwright.sync_api import Page, Route, expect

from tests.payloads import fermentation_payload, gateway_lettura


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_start_read_and_end_fermentazione_without_reusing_diagnostic_history(
    page: Page, api: httpx.Client, width: int, height: int
) -> None:
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
    page.set_viewport_size({"width": width, "height": height})
    page.goto(str(api.base_url))
    page.get_by_label("Nome della fermentazione").fill("Prima IPA")
    page.get_by_label("Pillola della fermentazione").select_option(index=1)
    page.get_by_role("button", name="Avvia fermentazione").click()
    expect(page.get_by_role("heading", name="Prima IPA", exact=True)).to_be_visible()
    expect(
        page.get_by_role("heading", name="In attesa della prima lettura della fermentazione")
    ).to_be_visible()
    expect(page.get_by_role("region", name="Densità")).to_have_count(0)
    first = api.get("/api/fermentations/active").json()["fermentation"]

    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=datetime.now(UTC).timestamp(), specific_gravity=1040.125
            ),
        ).status_code
        == 200
    )
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name="Prima IPA", exact=True)).to_be_visible()
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    page.get_by_role("button", name="Termina fermentazione").click()
    expect(page.get_by_role("status", name="Esito operazione")).to_contain_text("conclusa")
    assert api.get("/api/fermentations/active").json()["fermentation"] is None
    ended = api.get(f"/api/fermentations/{first['id']}").json()["fermentation"]
    assert ended["status"] == "concluded"
    assert ended["ended_at"]
    assert len(api.get(f"/api/fermentations/{first['id']}/readings").json()["readings"]) == 1

    page.get_by_label("Nome della fermentazione").fill("Seconda IPA")
    page.get_by_label("Pillola della fermentazione").select_option(index=1)
    page.get_by_role("button", name="Avvia fermentazione").click()
    expect(page.get_by_role("heading", name="Seconda IPA", exact=True)).to_be_visible()
    expect(
        page.get_by_role("heading", name="In attesa della prima lettura della fermentazione")
    ).to_be_visible()
    expect(page.get_by_role("region", name="Densità")).to_have_count(0)
    page.reload()
    expect(page.get_by_role("heading", name="Seconda IPA", exact=True)).to_be_visible()
    expect(
        page.get_by_role("heading", name="In attesa della prima lettura della fermentazione")
    ).to_be_visible()


def test_invalid_name_and_conflicting_start_are_visible_without_replacing_active_state(
    page: Page, api: httpx.Client
) -> None:
    page.goto(str(api.base_url))
    page.get_by_label("Nome della fermentazione").fill("   ")
    page.get_by_label("Pillola della fermentazione").select_option(index=1)
    page.get_by_role("button", name="Avvia fermentazione").click()
    expect(page.get_by_role("alert")).to_have_text("Inserisci un nome per la fermentazione.")
    assert api.get("/api/fermentations/active").json()["fermentation"] is None

    def competing_start(route: Route) -> None:
        assert (
            api.post(
                "/api/fermentations", json=fermentation_payload(api, "IPA già attiva")
            ).status_code
            == 201
        )
        route.continue_()

    page.route("**/api/fermentations", competing_start)
    page.get_by_label("Nome della fermentazione").fill("IPA concorrente")
    page.get_by_role("button", name="Avvia fermentazione").click()
    expect(page.get_by_role("alert")).to_contain_text("già una fermentazione attiva")
    expect(page.get_by_role("status", name="Esito operazione")).to_have_count(0)
    expect(page.get_by_role("heading", name="IPA già attiva", exact=True)).to_be_visible()
    assert api.get("/api/fermentations/active").json()["fermentation"]["name"] == "IPA già attiva"


def test_failed_end_keeps_active_state_and_can_be_retried(page: Page, api: httpx.Client) -> None:
    first = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA da terminare")
    ).json()["fermentation"]
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(str(api.base_url))
    page.route("**/api/fermentations/*/end", lambda route: route.abort("connectionfailed"))
    page.get_by_role("button", name="Termina fermentazione").click()
    expect(page.get_by_role("alert")).to_contain_text("Non è stato possibile confermare")
    expect(page.get_by_role("status", name="Esito operazione")).to_have_count(0)
    expect(page.get_by_role("heading", name="IPA da terminare", exact=True)).to_be_visible()
    assert api.get("/api/fermentations/active").json()["fermentation"]["id"] == first["id"]
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    page.unroute("**/api/fermentations/*/end")
    page.get_by_role("button", name="Termina fermentazione").click()
    expect(page.get_by_role("status", name="Esito operazione")).to_contain_text("conclusa")
    expect(page.get_by_role("alert")).to_have_count(0)
    assert api.get("/api/fermentations/active").json()["fermentation"] is None


def test_long_fermentazione_name_remains_readable_on_phone(page: Page, api: httpx.Client) -> None:
    name = "IPA" * 50
    assert api.post("/api/fermentations", json=fermentation_payload(api, name)).status_code == 201
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(str(api.base_url))
    expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Termina fermentazione")).to_be_enabled()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

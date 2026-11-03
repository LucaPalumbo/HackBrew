from datetime import UTC, datetime

import httpx
from playwright.sync_api import Page, expect

from tests.payloads import gateway_lettura


def test_selected_history_recovers_automatically_after_a_failed_load_and_reconnection(
    page: Page, api: httpx.Client
) -> None:
    first = api.post("/api/fermentations", json={"name": "Storico da recuperare"}).json()[
        "fermentation"
    ]
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=datetime.now(UTC).timestamp(), specific_gravity=1060),
        ).status_code
        == 200
    )
    assert api.post(f"/api/fermentations/{first['id']}/end").status_code == 200
    assert api.post("/api/fermentations", json={"name": "Attiva"}).status_code == 201
    page.goto(str(api.base_url))
    page.route("**/api/fermentations/*/readings?*", lambda route: route.abort("connectionfailed"))
    page.get_by_role("button", name="Apri Storico da recuperare").click()
    expect(page.get_by_role("alert")).to_contain_text("Non è stato possibile recuperare lo storico")
    page.context.set_offline(True)
    expect(page.get_by_label("Collegamento live")).to_contain_text("Riconnessione automatica")
    page.unroute("**/api/fermentations/*/readings?*")
    page.context.set_offline(False)

    expect(page.get_by_label("Collegamento live")).to_have_text("Collegamento live attivo")
    expect(
        page.get_by_role("heading", name="Storico: Storico da recuperare", exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role("table", name="Letture della fermentazione").get_by_role(
            "cell", name="1.060", exact=True
        )
    ).to_be_visible()
    expect(page.get_by_role("alert")).to_have_count(0)


def test_failed_initial_snapshot_does_not_invent_an_empty_fermentazione_state(
    page: Page, api: httpx.Client
) -> None:
    assert api.post("/api/fermentations", json={"name": "IPA già avviata"}).status_code == 201
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=datetime.now(UTC).timestamp(), specific_gravity=1040),
        ).status_code
        == 200
    )
    page.route("**/api/readings/latest", lambda route: route.abort("connectionfailed"))
    page.route("**/api/readings/events", lambda route: route.abort("connectionfailed"))
    page.goto(str(api.base_url))
    expect(
        page.get_by_role("alert").filter(has_text="Non è stato possibile recuperare la lettura")
    ).to_be_visible()
    expect(page.get_by_role("button", name="Avvia fermentazione", exact=True)).to_have_count(0)
    expect(page.get_by_text("Nessuna fermentazione attiva", exact=True)).to_have_count(0)
    expect(page.get_by_label("Stato dei dati")).to_have_text("Stato dei dati non disponibile")

    page.unroute("**/api/readings/latest")
    page.unroute("**/api/readings/events")
    expect(page.get_by_role("heading", name="IPA già avviata", exact=True)).to_be_visible(
        timeout=10000
    )
    expect(
        page.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible()

"""Observe real service outages through HTTP and two open browser pages."""

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from playwright.sync_api import Page, expect, sync_playwright

from tests.database import reset_test_database
from tests.payloads import fermentation_payload, gateway_lettura, register_test_pill


def phase(ready: str, restored: str, page: Page) -> None:
    directory = Path(os.environ["HACKBREW_RECOVERY_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ready).touch()
    print(f"Recovery: {ready}", flush=True)
    deadline = time.monotonic() + 120
    while not (directory / restored).exists():
        if time.monotonic() >= deadline:
            raise AssertionError(f"Services did not reach phase {restored}")
        page.wait_for_timeout(100)


def wait_for_application(api: httpx.Client, page: Page) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if api.get("/api/health", timeout=3).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        page.wait_for_timeout(200)
    raise AssertionError("The application did not recover its database connection")


def submit_reading(api: httpx.Client, gravity: float, expected_gravity: float) -> dict[str, Any]:
    payload = gateway_lettura(timestamp=datetime.now(UTC).timestamp(), specific_gravity=gravity)
    response = api.post("/telemetry", json=payload)
    assert response.status_code == 200
    reading: dict[str, Any] = response.json()["reading"]
    assert reading["specific_gravity"] == expected_gravity
    assert reading["timestamp"] == payload["timestamp"]
    return reading


def seed(api: httpx.Client) -> dict[str, Any]:
    reset_test_database()
    register_test_pill(api)
    closed = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Storico recupero")
    ).json()["fermentation"]
    submit_reading(api, 1060.125, 1.060125)
    closed = api.post(f"/api/fermentations/{closed['id']}/end").json()["fermentation"]
    active = api.post(
        "/api/fermentations", json=fermentation_payload(api, "Recupero attiva")
    ).json()["fermentation"]
    reading = submit_reading(api, 1040.125, 1.040125)
    return {
        "closed": closed,
        "active": active,
        "reading": reading,
        "closed_history": api.get(f"/api/fermentations/{closed['id']}/readings").json()["readings"],
        "active_history": api.get(f"/api/fermentations/{active['id']}/readings").json()["readings"],
    }


def assert_persisted_state(api: httpx.Client, expected: dict[str, Any]) -> None:
    assert api.get("/api/fermentations/active").json()["fermentation"] == expected["active"]
    for kind in ("closed", "active"):
        identifier = expected[kind]["id"]
        assert api.get(f"/api/fermentations/{identifier}").json()["fermentation"] == expected[kind]
        assert (
            api.get(f"/api/fermentations/{identifier}/readings").json()["readings"]
            == expected[f"{kind}_history"]
        )
    assert api.get("/api/readings/latest").json()["reading"] == expected["reading"]


def verify_database_outage(
    api: httpx.Client, current: Page, archive: Page, expected: dict[str, Any]
) -> None:
    acquired_at = current.get_by_label("Acquisizione della lettura").get_attribute("datetime")
    phase("stop-mongo", "mongo-down", current)
    rejected = gateway_lettura(timestamp=datetime.now(UTC).timestamp(), specific_gravity=1010.125)
    operations = [
        ("POST", "/telemetry", rejected),
        (
            "POST",
            "/api/fermentations",
            {"name": "Non salvata", "pill_id": expected["active"]["pill_id"]},
        ),
        ("POST", "/api/pills", {"name": "Non registrata", "mac": "11:22:33:44:55:66"}),
        ("POST", f"/api/fermentations/{expected['active']['id']}/end", None),
        ("GET", "/api/readings/latest", None),
        ("GET", "/api/thermal-devices", None),
        (
            "POST",
            "/api/thermal-devices",
            {"name": "Non salvato", "capability": "both", "base_url": "http://thermal-both:8000"},
        ),
        ("POST", "/api/thermal-devices/unknown/check", None),
        ("GET", "/api/fermentations/active", None),
        ("GET", f"/api/fermentations/{expected['closed']['id']}", None),
        ("GET", f"/api/fermentations/{expected['closed']['id']}/readings", None),
    ]
    for method, path, body in operations:
        response = api.request(method, path, json=body)
        assert response.status_code == 503, (method, path, response.text)
        assert "non disponibile" in response.json()["detail"]
    with api.stream("GET", "/api/readings/events") as stream:
        event = None
        for line in stream.iter_lines():
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            if not line and event:
                break
        assert event == "unavailable"

    expect(current.get_by_label("Collegamento live")).to_contain_text("Riconnessione automatica")
    expect(
        current.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
    ).to_be_visible()
    assert (
        current.get_by_label("Acquisizione della lettura").get_attribute("datetime") == acquired_at
    )
    current.get_by_role("button", name="Termina fermentazione").click()
    expect(current.get_by_role("alert").filter(has_text="Archivio delle letture")).to_be_visible()
    expect(current.get_by_role("status", name="Esito operazione")).to_have_count(0)
    expect(current.get_by_role("heading", name="Recupero attiva", exact=True)).to_be_visible()
    archive.reload()
    expect(
        archive.get_by_role("alert").filter(has_text="Non è stato possibile recuperare lo storico")
    ).to_be_visible()

    phase("start-mongo", "mongo-up", current)
    wait_for_application(api, current)
    assert_persisted_state(api, expected)
    expect(
        archive.get_by_role("heading", name="Storico: Storico recupero", exact=True)
    ).to_be_visible(timeout=20000)
    expect(
        archive.get_by_role("table", name="Letture della fermentazione").get_by_role(
            "cell", name="1.060", exact=True
        )
    ).to_be_visible()
    expect(archive.get_by_role("alert")).to_have_count(0)
    # A new acquisition resumes monitoring; the rejected payload is never replayed.
    reading = submit_reading(api, 1030.125, 1.030125)
    expected["reading"] = reading
    expected["active_history"].append(reading)
    expect(
        current.get_by_role("region", name="Densità").get_by_text("1.030", exact=True)
    ).to_be_visible(timeout=20000)
    assert_persisted_state(api, expected)


def verify_application_recreation(
    api: httpx.Client, current: Page, archive: Page, expected: dict[str, Any]
) -> None:
    acquired_at = current.get_by_label("Acquisizione della lettura").get_attribute("datetime")
    phase("stop-app", "app-down", current)
    try:
        api.post(
            "/telemetry",
            json=gateway_lettura(
                timestamp=datetime.now(UTC).timestamp(), specific_gravity=1005.125
            ),
        )
    except httpx.TransportError:
        pass
    else:
        raise AssertionError("The stopped application unexpectedly accepted a request")
    expect(current.get_by_label("Collegamento live")).to_contain_text(
        "Riconnessione automatica", timeout=15000
    )
    expect(
        current.get_by_role("region", name="Densità").get_by_text("1.030", exact=True)
    ).to_be_visible()
    assert (
        current.get_by_label("Acquisizione della lettura").get_attribute("datetime") == acquired_at
    )
    expect(
        archive.get_by_role("heading", name="Storico: Storico recupero", exact=True)
    ).to_be_visible()

    phase("recreate-services", "services-up", current)
    wait_for_application(api, current)
    assert_persisted_state(api, expected)
    expect(current.get_by_label("Collegamento live")).to_have_text(
        "Collegamento live attivo", timeout=90000
    )
    expect(archive.get_by_label("Collegamento live")).to_have_text(
        "Collegamento live attivo", timeout=90000
    )
    reading = submit_reading(api, 1020.125, 1.020125)
    expected["reading"] = reading
    expected["active_history"].append(reading)
    expect(
        current.get_by_role("region", name="Densità").get_by_text("1.020", exact=True)
    ).to_be_visible(timeout=20000)
    expect(
        archive.get_by_role("heading", name="Storico: Storico recupero", exact=True)
    ).to_be_visible()
    assert_persisted_state(api, expected)
    current.get_by_role("button", name="Termina fermentazione").click()
    expect(current.get_by_role("status", name="Esito operazione")).to_contain_text("conclusa")
    assert api.get("/api/fermentations/active").json()["fermentation"] is None
    assert (
        api.post(
            "/api/fermentations", json=fermentation_payload(api, "Nuovo monitoraggio")
        ).status_code
        == 201
    )


def main() -> None:
    if os.environ["MONGODB_DATABASE"] != "hackbrew_test":
        raise RuntimeError("Recovery checks require the isolated hackbrew_test database")
    with httpx.Client(base_url=os.environ["HACKBREW_BASE_URL"], timeout=10) as api:
        expected = seed(api)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            current = browser.new_page(locale="it-IT", viewport={"width": 390, "height": 844})
            archive = browser.new_page(locale="it-IT", viewport={"width": 1440, "height": 1000})
            current.goto(str(api.base_url))
            archive.goto(str(api.base_url))
            archive.get_by_role("button", name="Apri Storico recupero").click()
            expect(
                archive.get_by_role("heading", name="Storico: Storico recupero", exact=True)
            ).to_be_visible()
            expect(
                current.get_by_role("region", name="Densità").get_by_text("1.040", exact=True)
            ).to_be_visible()
            verify_database_outage(api, current, archive, expected)
            verify_application_recreation(api, current, archive, expected)
            browser.close()
    print(
        "Recovery: MongoDB, app e container ricreati; stato, storico e live verificati.", flush=True
    )


if __name__ == "__main__":
    main()

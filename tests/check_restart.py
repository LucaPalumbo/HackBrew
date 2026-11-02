"""Verify public state across an externally managed application restart."""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any

import httpx
from playwright.sync_api import expect, sync_playwright

from tests.database import reset_test_database
from tests.fermentations import assert_single_concurrent_start
from tests.payloads import gateway_lettura


def start_with_reading(
    api: httpx.Client, name: str, gravity: float, expected_gravity: float
) -> dict[str, Any]:
    response = api.post("/api/fermentations", json={"name": name})
    response.raise_for_status()
    fermentation: dict[str, Any] = response.json()["fermentation"]
    timestamp = datetime.fromisoformat(fermentation["started_at"]).timestamp() + 0.000123
    response = api.post(
        "/telemetry", json=gateway_lettura(timestamp=timestamp, specific_gravity=gravity)
    )
    response.raise_for_status()
    reading = response.json()["reading"]
    assert reading["specific_gravity"] == expected_gravity
    assert reading["temperature"] == 19.6875
    assert reading["battery"] == 63.2734375
    assert reading["timestamp"] == timestamp
    return fermentation


def seed(api: httpx.Client) -> dict[str, Any]:
    reset_test_database()
    first = start_with_reading(api, "Persistenza conclusa", 1040.125, 1.040125)
    response = api.post(f"/api/fermentations/{first['id']}/end")
    response.raise_for_status()
    concluded = response.json()["fermentation"]
    active = start_with_reading(api, "Persistenza attiva", 1050.125, 1.050125)
    return {
        "concluded": concluded,
        "active": active,
        "reading": api.get("/api/readings/latest").json()["reading"],
        "concluded_readings": api.get(f"/api/fermentations/{first['id']}/readings").json()[
            "readings"
        ],
        "active_readings": api.get(f"/api/fermentations/{active['id']}/readings").json()[
            "readings"
        ],
    }


def verify(api: httpx.Client, expected: dict[str, Any]) -> None:
    for status in ("concluded", "active"):
        identifier = expected[status]["id"]
        assert (
            api.get(f"/api/fermentations/{identifier}").json()["fermentation"] == expected[status]
        )
        history = api.get(f"/api/fermentations/{identifier}/readings").json()["readings"]
        assert len(history) == 1
        assert history == expected[f"{status}_readings"]
    assert api.get("/api/readings/latest").json()["reading"] == expected["reading"]
    assert api.get("/api/fermentations/active").json()["fermentation"] == expected["active"]
    assert api.post("/api/fermentations", json={"name": "Avvio bloccato"}).status_code == 409

    concluded = api.get("/api/fermentations", params={"q": "Persistenza conclusa"}).json()[
        "fermentations"
    ]
    assert [entry["id"] for entry in concluded] == [expected["concluded"]["id"]]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(locale="it-IT", viewport={"width": 390, "height": 844})
        page.set_default_timeout(5000)
        page.goto(str(api.base_url))
        page.get_by_role("button", name="Apri Persistenza conclusa").click()
        expect(
            page.get_by_role("heading", name="Storico: Persistenza conclusa", exact=True)
        ).to_be_visible()
        expect(page.get_by_role("img", name="Densità SG: 1 lettura")).to_be_visible()
        table = page.get_by_role("table", name="Letture della fermentazione")
        expect(table.get_by_role("cell", name="1.040", exact=True)).to_be_visible()
        expect(table.get_by_role("cell", name="63", exact=True)).to_be_visible()
        page.reload()
        expect(
            page.get_by_role("heading", name="Storico: Persistenza conclusa", exact=True)
        ).to_be_visible()
        expect(table.get_by_role("cell", name="1.040", exact=True)).to_be_visible()
        browser.close()

    assert api.post(f"/api/fermentations/{expected['active']['id']}/end").status_code == 200
    assert_single_concurrent_start(api)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["seed", "verify"])
    phase = parser.parse_args().phase
    if os.environ["MONGODB_DATABASE"] != "hackbrew_test":
        raise RuntimeError("Restart checks require the isolated hackbrew_test database")

    with httpx.Client(base_url=os.environ["HACKBREW_BASE_URL"], timeout=10) as api:
        if phase == "seed":
            print(json.dumps(seed(api)))
        else:
            verify(api, json.load(sys.stdin))
            print("Persistence verify: fermentazioni, letture e vincolo concorrente preservati.")


if __name__ == "__main__":
    main()

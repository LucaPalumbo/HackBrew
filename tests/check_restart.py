"""Verify public state across an externally managed application restart."""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import httpx
from playwright.sync_api import expect, sync_playwright

from tests.database import reset_test_database
from tests.fermentations import assert_single_concurrent_start
from tests.payloads import fermentation_payload, gateway_lettura, register_test_pill


def start_with_reading(
    api: httpx.Client, name: str, gravity: float, expected_gravity: float
) -> dict[str, Any]:
    response = api.post("/api/fermentations", json=fermentation_payload(api, name))
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
    register_test_pill(api)
    first = start_with_reading(api, "Persistenza conclusa", 1040.125, 1.040125)
    response = api.post(f"/api/fermentations/{first['id']}/end")
    response.raise_for_status()
    concluded = response.json()["fermentation"]
    active = start_with_reading(api, "Persistenza attiva", 1050.125, 1.050125)
    other = api.post(
        "/api/pills", json={"name": "Seconda pillola", "mac": "11:22:33:44:55:66"}
    ).json()["pill"]
    other_reading = api.post(
        "/telemetry", json=gateway_lettura(pill_mac=other["mac"], specific_gravity=1080.125)
    ).json()["reading"]
    expected = {
        "pills": api.get("/api/pills").json()["pills"],
        "other_pill": other,
        "other_reading": other_reading,
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
    return expected


def verify(api: httpx.Client, expected: dict[str, Any]) -> None:
    assert api.get("/api/pills").json()["pills"] == expected["pills"]
    assert (
        api.get("/api/readings/latest", params={"pill_id": expected["other_pill"]["id"]}).json()[
            "reading"
        ]
        == expected["other_reading"]
    )
    for status, gravity in (("concluded", 1040.125), ("active", 1050.125)):
        reading = expected[f"{status}_readings"][0]
        payload = gateway_lettura(timestamp=reading["timestamp"], specific_gravity=gravity)
        with ThreadPoolExecutor(max_workers=6) as pool:
            responses = list(
                pool.map(lambda body: api.post("/telemetry", json=body), [payload] * 12)
            )
        assert all(response.status_code == 200 for response in responses)
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
    assert (
        api.post("/api/fermentations", json=fermentation_payload(api, "Avvio bloccato")).status_code
        == 409
    )

    timestamp = expected["reading"]["timestamp"] + 0.000001
    payload = gateway_lettura(timestamp=timestamp, specific_gravity=1030.125)
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda _: api.post("/telemetry", json=payload), range(12)))
    assert all(response.status_code == 200 for response in responses)
    active_history = api.get(f"/api/fermentations/{expected['active']['id']}/readings").json()[
        "readings"
    ]
    assert len(active_history) == 2
    assert active_history[-1]["timestamp"] == timestamp
    assert api.get("/api/readings/latest").json()["reading"]["specific_gravity"] == 1.030125

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

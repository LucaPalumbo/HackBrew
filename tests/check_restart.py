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

from tests.database import arrange_single_active_index, reset_test_database
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


def seed_upgrade(api: httpx.Client) -> dict[str, Any]:
    reset_test_database()
    register_test_pill(api)
    fermentation = start_with_reading(api, "Preservata da versione 9", 1050.125, 1.050125)
    other = api.post(
        "/api/pills", json={"name": "Seconda pillola", "mac": "11:22:33:44:55:66"}
    ).json()["pill"]
    expected = {
        "fermentation": fermentation,
        "pills": api.get("/api/pills").json()["pills"],
        "readings": api.get(f"/api/fermentations/{fermentation['id']}/readings").json()["readings"],
        "other_pill": other,
    }
    arrange_single_active_index()
    return expected


def verify_upgrade(api: httpx.Client, expected: dict[str, Any]) -> None:
    identifier = expected["fermentation"]["id"]
    assert (
        api.get(f"/api/fermentations/{identifier}").json()["fermentation"]
        == expected["fermentation"]
    )
    assert (
        api.get(f"/api/fermentations/{identifier}/readings").json()["readings"]
        == expected["readings"]
    )
    assert api.get("/api/pills").json()["pills"] == expected["pills"]
    second = api.post(
        "/api/fermentations",
        json={"name": "Ora parallela", "pill_id": expected["other_pill"]["id"]},
    )
    assert second.status_code == 201
    assert (
        api.post("/api/fermentations", json=fermentation_payload(api, "Riuso bloccato")).status_code
        == 409
    )
    assert len(api.get("/api/fermentations/active").json()["fermentations"]) == 2


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
    other_active = api.post(
        "/api/fermentations", json={"name": "Seconda persistenza attiva", "pill_id": other["id"]}
    ).json()["fermentation"]
    other_timestamp = datetime.fromisoformat(other_active["started_at"]).timestamp() + 0.000123
    other_reading = api.post(
        "/telemetry",
        json=gateway_lettura(
            pill_mac=other["mac"], timestamp=other_timestamp, specific_gravity=1080.125
        ),
    ).json()["reading"]
    expected = {
        "pills": api.get("/api/pills").json()["pills"],
        "bridge_registry": api.get("/api/bridge/pills").json(),
        "other_pill": other,
        "other_active": other_active,
        "other_history": api.get(f"/api/fermentations/{other_active['id']}/readings").json()[
            "readings"
        ],
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
    for capability in ("heating", "cooling", "both"):
        response = api.post(
            "/api/thermal-devices",
            json={
                "name": f"Persistenza {capability}",
                "capability": capability,
                "base_url": f"http://thermal-{capability}:8000",
            },
        )
        response.raise_for_status()
        identifier = response.json()["device"]["id"]
        assert (
            api.post(f"/api/thermal-devices/{identifier}/check").json()["device"][
                "verification_status"
            ]
            == "confirmed"
        )
    expected["thermal_devices"] = api.get("/api/thermal-devices").json()["devices"]
    return expected


def verify(api: httpx.Client, expected: dict[str, Any]) -> None:
    assert api.get("/api/thermal-devices").json()["devices"] == expected["thermal_devices"]
    assert api.get("/api/pills").json()["pills"] == expected["pills"]
    assert api.get("/api/bridge/pills").json() == expected["bridge_registry"]
    assert (
        api.get("/api/readings/latest", params={"pill_id": expected["other_pill"]["id"]}).json()[
            "reading"
        ]
        == expected["other_reading"]
    )
    other_id = expected["other_active"]["id"]
    assert (
        api.get(f"/api/fermentations/{other_id}").json()["fermentation"] == expected["other_active"]
    )
    assert (
        api.get(f"/api/fermentations/{other_id}/readings").json()["readings"]
        == expected["other_history"]
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
    active = api.get("/api/fermentations/active").json()
    assert active["fermentation"] is None
    assert {row["id"] for row in active["fermentations"]} == {expected["active"]["id"], other_id}
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
        expect(page.get_by_role("img", name="Grafico a linee: 1 lettura")).to_be_visible()
        table = page.get_by_role("table", name="Letture della fermentazione")
        expect(table.get_by_role("cell", name="1.040125", exact=True)).to_be_visible()
        expect(table.get_by_role("cell", name="63,2734375", exact=True)).to_be_visible()
        page.reload()
        expect(
            page.get_by_role("heading", name="Storico: Persistenza conclusa", exact=True)
        ).to_be_visible()
        expect(table.get_by_role("cell", name="1.040125", exact=True)).to_be_visible()
        browser.close()

    assert api.post(f"/api/fermentations/{expected['active']['id']}/end").status_code == 200
    assert_single_concurrent_start(api)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=["upgrade-seed", "upgrade-verify", "persistence-seed", "persistence-verify"],
    )
    phase = parser.parse_args().phase
    if os.environ["MONGODB_DATABASE"] != "hackbrew_test":
        raise RuntimeError("Restart checks require the isolated hackbrew_test database")

    with httpx.Client(base_url=os.environ["HACKBREW_BASE_URL"], timeout=10) as api:
        if phase.endswith("-seed"):
            print(json.dumps(seed_upgrade(api) if phase == "upgrade-seed" else seed(api)))
        else:
            expected = json.load(sys.stdin)
            if phase == "upgrade-verify":
                verify_upgrade(api, expected)
                print(
                    "Upgrade verify: vincolo per pillola installato "
                    "senza perdita dei dati della versione 9."
                )
            else:
                verify(api, expected)
                print(
                    "Persistence verify: due fermentazioni attive, "
                    "letture e vincoli per pillola preservati."
                )


if __name__ == "__main__":
    main()

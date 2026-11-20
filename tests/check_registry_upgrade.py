"""Observe standalone conversion and registry persistence through public HTTP."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from tests.database import arrange_registry_before_management, reset_test_database
from tests.payloads import gateway_lettura


def seed(api: httpx.Client) -> dict[str, Any]:
    reset_test_database()
    pills = [
        api.post("/api/pills", json={"name": name, "mac": mac}).json()["pill"]
        for name, mac in (
            ("Pillola storica A", "AA:BB:CC:DD:EE:FF"),
            ("Pillola storica B", "11:22:33:44:55:66"),
        )
    ]
    now = datetime.now(UTC).timestamp()
    # Legacy records predate lifecycle transactions and registry metadata.
    cycles = [
        {
            "_id": str(uuid4()),
            "name": f"Birra storica {index}",
            "pill_id": pill["id"],
            "pill_name": pill["name"],
            "pill_mac": pill["mac"],
            "status": "concluded",
            "started_at": now - 3600,
            "ended_at": now - 60,
        }
        for index, pill in enumerate(pills)
    ]
    arrange_registry_before_management(cycles)
    expected: dict[str, Any] = {"pills": pills, "cycles": []}
    for index, (pill, cycle) in enumerate(zip(pills, cycles, strict=True)):
        api.post(
            "/telemetry",
            json=gateway_lettura(
                pill_mac=pill["mac"],
                timestamp=now - 1800 + 0.000123,
                specific_gravity=1040.125 + index * 10,
            ),
        ).raise_for_status()
        detail = api.get(f"/api/fermentations/{cycle['_id']}").json()["fermentation"]
        readings = api.get(f"/api/fermentations/{cycle['_id']}/readings").json()["readings"]
        assert len(readings) == 1
        expected["cycles"].append({"fermentation": detail, "readings": readings})
    expected["bridge"] = api.get("/api/bridge/pills").json()
    expected["diagnostics"] = [
        api.get("/api/readings/latest", params={"pill_id": pill["id"]}).json()["reading"]
        for pill in pills
    ]
    return expected


def verify_history(api: httpx.Client, expected: dict[str, Any]) -> None:
    for original in expected["cycles"]:
        identifier = original["fermentation"]["id"]
        assert (
            api.get(f"/api/fermentations/{identifier}").json()["fermentation"]
            == original["fermentation"]
        )
        assert (
            api.get(f"/api/fermentations/{identifier}/readings").json()["readings"]
            == original["readings"]
        )


def upgrade(api: httpx.Client, expected: dict[str, Any]) -> dict[str, Any]:
    assert api.get("/api/pills").json()["pills"] == expected["pills"]
    assert api.get("/api/bridge/pills").json() == expected["bridge"]
    verify_history(api, expected)
    for pill, reading in zip(expected["pills"], expected["diagnostics"], strict=True):
        assert (
            api.get("/api/readings/latest", params={"pill_id": pill["id"]}).json()["reading"]
            == reading
        )
    first, second = expected["pills"]
    api.patch(f"/api/pills/{first['id']}", json={"name": "Nome aggiornato"}).raise_for_status()
    api.delete(f"/api/pills/{second['id']}").raise_for_status()
    response = api.post(
        "/api/fermentations", json={"name": "Nuovo ciclo dopo conversione", "pill_id": first["id"]}
    )
    assert response.status_code == 201
    expected["active"] = response.json()["fermentation"]
    expected["managed_pills"] = api.get("/api/pills").json()["pills"]
    expected["managed_bridge"] = api.get("/api/bridge/pills").json()
    verify_history(api, expected)
    return expected


def verify(api: httpx.Client, expected: dict[str, Any]) -> None:
    assert api.get("/api/pills").json()["pills"] == expected["managed_pills"]
    assert api.get("/api/bridge/pills").json() == expected["managed_bridge"]
    identifier = expected["active"]["id"]
    assert api.get(f"/api/fermentations/{identifier}").json()["fermentation"] == expected["active"]
    assert api.get(f"/api/fermentations/{identifier}/readings").json()["readings"] == []
    first, removed = expected["pills"]
    assert (
        api.get("/api/readings/latest", params={"pill_id": first["id"]}).json()["reading"]
        == expected["diagnostics"][0]
    )
    assert api.get("/api/readings/latest", params={"pill_id": removed["id"]}).status_code == 404
    assert api.post("/telemetry", json=gateway_lettura(pill_mac=removed["mac"])).status_code == 404
    verify_history(api, expected)
    restored = api.post("/api/pills", json={"name": "Pillola recuperata", "mac": removed["mac"]})
    assert restored.status_code == 201
    assert restored.json()["pill"]["id"] == removed["id"]
    assert (
        api.get("/api/readings/latest", params={"pill_id": removed["id"]}).json()["reading"]
        == expected["diagnostics"][1]
    )
    verify_history(api, expected)


def main() -> None:
    if os.environ["MONGODB_DATABASE"] != "hackbrew_test":
        raise RuntimeError("Registry upgrade checks require the isolated hackbrew_test database")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["seed", "upgrade", "verify"])
    phase = parser.parse_args().phase
    with httpx.Client(base_url=os.environ["HACKBREW_BASE_URL"], timeout=10) as api:
        if phase == "seed":
            print(json.dumps(seed(api)))
        elif phase == "upgrade":
            print(json.dumps(upgrade(api, json.load(sys.stdin))))
        else:
            verify(api, json.load(sys.stdin))
            print(
                "Registry upgrade: standalone converted; renamed/removed identities, "
                "history, readings and bridge preserved after container recreation."
            )


if __name__ == "__main__":
    main()

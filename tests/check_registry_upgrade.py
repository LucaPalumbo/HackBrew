"""Observe standalone conversion and registry persistence through public HTTP."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from tests.database import (
    arrange_registry_before_management,
    arrange_thermal_registry_before_management,
    reset_test_database,
)
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
    devices = [
        api.post(
            "/api/thermal-devices",
            json={
                "name": f"Storico {capability}",
                "capability": capability,
                "base_url": f"http://legacy-{capability}.local",
            },
        ).json()["device"]
        for capability in ("heating", "cooling")
    ]
    control = {
        "status": "stopped",
        "reason": "Spegnimento confermato.",
        "desired_mode": "off",
        "actual_mode": "off",
        "confirmed_at": None,
        "command": None,
        "last_sent_at": None,
        "needs_off": False,
        "error": None,
    }
    legacy_cycle = {
        **cycles[0],
        "_id": str(uuid4()),
        "name": "Birra con equipaggiamento storico",
        "started_at": now - 10800,
        "ended_at": now - 7200,
        "control_mode": "heating_cooling",
        "heater_id": devices[0]["id"],
        "heater_name": devices[0]["name"],
        "heater_reserved": False,
        "cooler_id": devices[1]["id"],
        "combined_id": None,
        "devices": [
            {
                "id": device["id"],
                "name": device["name"],
                "capability": device["capability"],
                "role": role,
            }
            for device, role in zip(devices, ("heater", "cooler"), strict=True)
        ],
        "reserved_device_ids": [],
        "thermal_reserved": False,
        "control_revision": 1,
        "temperature_min": 18,
        "temperature_max": 22,
        "hysteresis": 0.5,
        "thermal_settings_revision": 0,
        "thermal_settings_history": [
            {
                "revision": 0,
                "changed_at": now - 10800,
                "temperature_min": 18,
                "temperature_max": 22,
                "hysteresis": 0.5,
            }
        ],
        "regulation": {
            **control,
            "devices": {device["id"]: {**control, "reserved": False} for device in devices},
        },
    }
    arrange_thermal_registry_before_management(devices, legacy_cycle)
    historic = api.get(f"/api/fermentations/{legacy_cycle['_id']}").json()["fermentation"]
    # Address associations did not change before registry editing existed.
    for assignment, device in zip(historic["devices"], devices, strict=True):
        assignment["base_url"] = device["base_url"]
    expected["thermal_history"] = historic
    expected["thermal_devices"] = devices
    return expected


def verify_history(api: httpx.Client, expected: dict[str, Any]) -> None:
    historic = expected["thermal_history"]
    assert api.get(f"/api/fermentations/{historic['id']}").json()["fermentation"] == historic
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
    heater, cooler = expected["thermal_devices"]
    updated = api.patch(
        f"/api/thermal-devices/{heater['id']}",
        json={
            "name": "Fascia aggiornata",
            "base_url": "http://new-heating.local",
        },
    )
    updated.raise_for_status()
    assert updated.json()["device"]["id"] == heater["id"]
    assert updated.json()["device"]["last_confirmation"] is None
    assert api.delete(f"/api/thermal-devices/{cooler['id']}").status_code == 204
    expected["thermal_registry"] = api.get("/api/thermal-devices").json()["devices"]
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
    assert api.get("/api/thermal-devices").json()["devices"] == expected["thermal_registry"]
    removed_device = expected["thermal_devices"][1]
    assert api.post(f"/api/thermal-devices/{removed_device['id']}/check").status_code == 404
    assert api.delete(f"/api/thermal-devices/{removed_device['id']}").status_code == 404
    replacement = api.post(
        "/api/thermal-devices",
        json={
            "name": "Nuovo raffreddatore",
            "capability": "cooling",
            "base_url": removed_device["base_url"],
        },
    )
    assert replacement.status_code == 201
    assert replacement.json()["device"]["id"] != removed_device["id"]
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

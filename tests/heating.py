"""Public HTTP helpers for real heating-control scenarios."""

import time
from datetime import UTC, datetime
from typing import Any

import httpx

from tests.payloads import gateway_lettura


def start_heating(api: httpx.Client, simulator: httpx.Client) -> dict[str, Any]:
    device = api.post(
        "/api/thermal-devices",
        json={
            "name": "Fascia",
            "capability": "heating",
            "base_url": str(simulator.base_url),
        },
    ).json()["device"]
    pill = api.get("/api/pills").json()["pills"][0]
    response = api.post(
        "/api/fermentations",
        json={
            "name": "IPA riscaldata",
            "pill_id": pill["id"],
            "control_mode": "heating",
            "heater_id": device["id"],
            "temperature_min": 18,
            "temperature_max": 22,
            "hysteresis": 0.5,
        },
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()["fermentation"]
    return result


def temperature(api: httpx.Client, value: float, mac: str = "AA:BB:CC:DD:EE:FF") -> None:
    api.post(
        "/telemetry",
        json=gateway_lettura(
            temperature=value,
            timestamp=datetime.now(UTC).timestamp(),
            pill_mac=mac,
        ),
    ).raise_for_status()


def wait_regulation(api: httpx.Client, cycle: dict[str, Any], status: str) -> dict[str, Any]:
    deadline = time.monotonic() + 15
    observed: dict[str, Any] = {}
    while time.monotonic() < deadline:
        observed = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
        if observed["regulation"]["status"] == status:
            return observed
        time.sleep(0.05)
    raise AssertionError(f"Regulation did not reach {status}: {observed}")

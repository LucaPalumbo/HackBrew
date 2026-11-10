"""Arrange thermal cycles exclusively through public HTTP contracts."""

import time
from collections.abc import Callable
from typing import Any

import httpx


def register_thermal(api: httpx.Client, simulator: httpx.Client, capability: str) -> dict[str, Any]:
    response = api.post(
        "/api/thermal-devices",
        json={
            "name": f"Dispositivo {capability}",
            "capability": capability,
            "base_url": str(simulator.base_url),
        },
    )
    response.raise_for_status()
    device: dict[str, Any] = response.json()["device"]
    return device


def thermal_cycle(
    api: httpx.Client, mode: str, devices: dict[str, dict[str, Any]], pill_id: str | None = None
) -> dict[str, Any]:
    if pill_id is None:
        pill_id = api.get("/api/pills").json()["pills"][0]["id"]
    response = api.post(
        "/api/fermentations",
        json={
            "name": f"IPA {mode}",
            "pill_id": pill_id,
            "control_mode": mode,
            "temperature_min": 18,
            "temperature_max": 22,
            "hysteresis": 0.5,
            **{role + "_id": device["id"] for role, device in devices.items()},
        },
    )
    response.raise_for_status()
    cycle: dict[str, Any] = response.json()["fermentation"]
    return cycle


def wait_cycle(
    api: httpx.Client, cycle: dict[str, Any], predicate: Callable[[dict[str, Any]], bool]
) -> dict[str, Any]:
    deadline = time.monotonic() + 15
    snapshot: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = api.get(f"/api/fermentations/{cycle['id']}")
        response.raise_for_status()
        snapshot = response.json()["fermentation"]
        if predicate(snapshot):
            return snapshot
        time.sleep(0.05)
    raise AssertionError(f"Cycle did not reach the expected state: {snapshot}")

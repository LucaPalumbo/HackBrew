"""Actual Docker server crashes coordinated outside the application under test."""

import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import httpx
from playwright.sync_api import Page

from tests.database import arrange_heating_v16, reset_test_database
from tests.heating import start_heating, temperature, wait_regulation
from tests.payloads import register_test_pill
from tests.thermal import thermal_simulator


def wait_device(
    simulator: httpx.Client, predicate: Callable[[dict[str, Any]], bool]
) -> dict[str, Any]:
    deadline = time.monotonic() + 20
    state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = simulator.get("/api/v1/state")
        response.raise_for_status()
        state = response.json()
        if predicate(state):
            return state
        time.sleep(0.05)
    raise AssertionError(f"Device did not reach the expected state: {state}")


def verify_heating_recovery(
    api: httpx.Client,
    page: Page,
    phase: Callable[[str, str, Page], None],
) -> None:
    reset_test_database()
    register_test_pill(api)
    with thermal_simulator("heating") as simulator:
        api.patch("/api/settings", json={"communication_timeout_seconds": 20}).raise_for_status()
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        temperature(api, 18.25)
        before = simulator.get("/api/v1/state").json()["accepted_command"]
        arrange_heating_v16(cycle["id"], cycle["heater_id"])
        phase("restart-heating-hysteresis", "heating-hysteresis-up", page)
        continued = wait_device(
            simulator,
            lambda s: (
                s["actual_mode"] == "heating"
                and s["accepted_command"]["sequence"] > before["sequence"]
            ),
        )
        assert continued["accepted_command"]["ownership_id"] == cycle["id"]
        assert wait_regulation(api, cycle, "heating")["hysteresis"] == 0.5

        temperature(api, 17)
        api.patch("/api/settings", json={"communication_timeout_seconds": 2}).raise_for_status()
        wait_device(
            simulator,
            lambda s: (
                s["actual_mode"] == "heating"
                and s["applied_timeout_seconds"] == 2
                and s["accepted_command"]["timeout_seconds"] == 2
            ),
        )
        phase("stop-heating-server", "heating-server-down", page)
        expired = wait_device(
            simulator,
            lambda s: s["actual_mode"] == "off" and s["application_status"] == "timed_out",
        )
        assert expired["accepted_command"]["mode"] == "heating"
        with suppress(httpx.HTTPError):
            assert api.get("/api/health", timeout=2).status_code >= 500
        phase("restart-heating-server", "heating-server-up", page)
        wait_regulation(api, cycle, "suspended")
        wait_device(
            simulator,
            lambda s: s["actual_mode"] == "off" and s["accepted_command"]["mode"] == "off",
        )

        api.patch("/api/settings", json={"communication_timeout_seconds": 10}).raise_for_status()
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        old_on = simulator.get("/api/v1/state").json()["accepted_command"]
        simulator.patch(
            "/__simulation", json={"state_http_status": 503, "control_http_status": 503}
        ).raise_for_status()
        wait_regulation(api, cycle, "suspended")
        ended = api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]
        assert ended["heater_reserved"] is True
        phase("restart-pending-off", "pending-off-restarted", page)
        preserved = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
        assert preserved["status"] == "concluded"
        assert preserved["ended_at"] == ended["ended_at"]
        assert preserved["heater_reserved"] is True
        assert preserved["regulation"]["desired_mode"] == "off"
        simulator.patch(
            "/__simulation",
            json={
                "state_http_status": 200,
                "control_http_status": 200,
                "confirmation_available": False,
            },
        ).raise_for_status()
        time.sleep(0.3)
        assert (
            api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]["heater_reserved"]
            is True
        )
        simulator.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        stopped = wait_regulation(api, cycle, "stopped")
        assert stopped["heater_reserved"] is False
        assert stopped["ended_at"] == ended["ended_at"]
        temperature(api, 16)
        assert simulator.put("/api/v1/control", json=old_on).status_code == 409
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        assert (
            api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]["ended_at"]
            == ended["ended_at"]
        )
    print(
        "Heating recovery: isteresi riconciliata, watchdog con server fermo, "
        "conclusione e OFF pendente preservati.",
        flush=True,
    )

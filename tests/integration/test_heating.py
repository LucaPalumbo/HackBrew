"""Heating regulation observed through HTTP with real actuators and MongoDB."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from tests.heating import start_heating, temperature, wait_regulation
from tests.thermal import thermal_simulator


def test_heater_and_pill_are_reserved_together_under_concurrent_starts(api: httpx.Client) -> None:
    with thermal_simulator("heating") as simulator:
        device = api.post(
            "/api/thermal-devices",
            json={"name": "Fascia", "capability": "heating", "base_url": str(simulator.base_url)},
        ).json()["device"]
        pills = api.get("/api/pills").json()["pills"]
        other = api.post("/api/pills", json={"name": "Altra", "mac": "11:22:33:44:55:66"}).json()[
            "pill"
        ]
        payload = {
            "name": "IPA riscaldata",
            "control_mode": "heating",
            "heater_id": device["id"],
            "temperature_min": 18,
            "temperature_max": 22,
            "hysteresis": 0.5,
        }
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(
                pool.map(
                    lambda pill: api.post(
                        "/api/fermentations", json={**payload, "pill_id": pill["id"]}
                    ),
                    [pills[0], other] * 4,
                )
            )
        assert [r.status_code for r in responses].count(201) == 1
        assert [r.status_code for r in responses].count(409) == 7
        cycle = next(r.json()["fermentation"] for r in responses if r.status_code == 201)
        assert cycle["control_mode"] == "heating"
        assert cycle["heater_id"] == device["id"]
        assert cycle["temperature_min"] == 18
        assert cycle["hysteresis"] == 0.5
        available = api.get("/api/thermal-devices").json()["devices"][0]
        assert available["available"] is False
        assert available["reserved_fermentation_id"] == cycle["id"]
        free = next(p for p in api.get("/api/pills").json()["pills"] if p["available"])
        assert (
            api.post(
                "/api/fermentations", json={"name": "Monitor", "pill_id": free["id"]}
            ).status_code
            == 201
        )


def test_heating_threshold_equalities_and_hysteresis_without_a_browser(api: httpx.Client) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        waiting = wait_regulation(api, cycle, "waiting")
        assert waiting["regulation"]["desired_mode"] == "off"
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        for value, expected in [
            (18, "heating"),
            (18.25, "heating"),
            (18.5, "idle"),
            (18.25, "idle"),
            (17, "heating"),
            (22, "idle"),
        ]:
            temperature(api, value)
            state = wait_regulation(api, cycle, expected)
            mode = "heating" if expected == "heating" else "off"
            assert state["regulation"]["desired_mode"] == mode
            assert state["regulation"]["actual_mode"] == mode
            assert simulator.get("/api/v1/state").json()["actual_mode"] == mode
        ended = api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]
        assert ended["status"] == "concluded"
        assert wait_regulation(api, cycle, "stopped")["heater_reserved"] is False


def test_end_during_outage_remains_final_and_blocks_reuse_until_confirmed_off(
    api: httpx.Client,
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        old_on = simulator.get("/api/v1/state").json()["accepted_command"]
        simulator.patch(
            "/__simulation", json={"state_http_status": 503, "control_http_status": 503}
        ).raise_for_status()
        failed = wait_regulation(api, cycle, "suspended")
        assert failed["regulation"]["actual_mode"] is None
        ended = api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]
        assert ended["status"] == "concluded"
        assert ended["regulation"]["desired_mode"] == "off"
        assert ended["heater_reserved"] is True
        other = api.post("/api/pills", json={"name": "Altra", "mac": "11:22:33:44:55:66"}).json()[
            "pill"
        ]
        candidate = {
            "name": "Riuso",
            "pill_id": other["id"],
            "control_mode": "heating",
            "heater_id": cycle["heater_id"],
            "temperature_min": 18,
            "temperature_max": 22,
            "hysteresis": 0.5,
        }
        assert api.post("/api/fermentations", json=candidate).status_code == 409
        assert (
            next(p for p in api.get("/api/pills").json()["pills"] if p["id"] == other["id"])[
                "available"
            ]
            is True
        )
        temperature(api, 16)
        # GET remains broken. A successful control response is sufficient physical proof.
        simulator.patch("/__simulation", json={"control_http_status": 200}).raise_for_status()
        stopped = wait_regulation(api, cycle, "stopped")
        assert stopped["heater_reserved"] is False
        assert stopped["ended_at"] == ended["ended_at"]
        assert simulator.put("/api/v1/control", json=old_on).status_code == 409
        assert (
            api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]["ended_at"]
            == ended["ended_at"]
        )
        simulator.patch("/__simulation", json={"state_http_status": 200}).raise_for_status()
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        reused = api.post("/api/fermentations", json=candidate)
        assert reused.status_code == 201
        temperature(api, 17, other["mac"])
        wait_regulation(api, reused.json()["fermentation"], "heating")
        assert simulator.put("/api/v1/control", json=old_on).status_code == 409
        api.post(f"/api/fermentations/{reused.json()['fermentation']['id']}/end").raise_for_status()


def test_renewals_and_pill_timeout_are_independent_of_other_traffic(api: httpx.Client) -> None:
    with thermal_simulator("heating") as simulator:
        api.patch("/api/settings", json={"communication_timeout_seconds": 2.4}).raise_for_status()
        cycle = start_heating(api, simulator)
        api.post(
            "/api/pills", json={"name": "Altra", "mac": "11:22:33:44:55:66"}
        ).raise_for_status()
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        first = simulator.get("/api/v1/state").json()["accepted_command"]
        time.sleep(1)
        renewed = simulator.get("/api/v1/state").json()
        assert renewed["actual_mode"] == "heating"
        assert renewed["accepted_command"]["sequence"] > first["sequence"]
        assert renewed["applied_timeout_seconds"] == 2.4
        deadline = time.monotonic() + 1.7
        while time.monotonic() < deadline:
            temperature(api, 17, "11:22:33:44:55:66")
            api.get("/api/bridge/pills").raise_for_status()
            assert api.post("/telemetry", json={"temperature": "bad"}).status_code == 422
            time.sleep(0.1)
        suspended = wait_regulation(api, cycle, "suspended")
        assert suspended["status"] == "active"
        assert suspended["regulation"]["desired_mode"] == "off"
        assert "Timeout" in suspended["regulation"]["reason"]
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        received = api.get("/api/readings/latest", params={"pill_id": cycle["pill_id"]}).json()[
            "last_received_at"
        ]
        api.patch("/api/settings", json={"communication_timeout_seconds": 0.01}).raise_for_status()
        wait_regulation(api, cycle, "suspended")
        assert (
            api.get("/api/readings/latest", params={"pill_id": cycle["pill_id"]}).json()[
                "last_received_at"
            ]
            == received
        )
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()


def test_missing_physical_off_confirmation_keeps_the_reservation(api: httpx.Client) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        simulator.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
        time.sleep(0.4)
        state = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
        assert state["status"] == "concluded"
        assert state["heater_reserved"] is True
        assert state["regulation"]["status"] == "stopping"
        assert state["regulation"]["actual_mode"] is None
        assert api.get("/api/thermal-devices").json()["devices"][0]["available"] is False
        simulator.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        assert wait_regulation(api, cycle, "stopped")["heater_reserved"] is False


def test_recovery_after_the_actuator_lease_expires_while_off(api: httpx.Client) -> None:
    with thermal_simulator("heating") as simulator:
        api.patch("/api/settings", json={"communication_timeout_seconds": 0.6}).raise_for_status()
        cycle = start_heating(api, simulator)
        temperature(api, 19)
        wait_regulation(api, cycle, "idle")
        simulator.patch(
            "/__simulation", json={"state_http_status": 503, "control_http_status": 503}
        ).raise_for_status()
        wait_regulation(api, cycle, "suspended")
        time.sleep(0.8)
        simulator.patch(
            "/__simulation", json={"state_http_status": 200, "control_http_status": 200}
        ).raise_for_status()
        temperature(api, 17)
        resumed = wait_regulation(api, cycle, "heating")
        assert resumed["status"] == "active"
        assert resumed["regulation"]["actual_mode"] == "heating"
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()


def test_slow_heater_does_not_block_renewals_of_another_fermentation(api: httpx.Client) -> None:
    with thermal_simulator("heating") as fast, thermal_simulator("heating-secondary") as slow:
        api.patch("/api/settings", json={"communication_timeout_seconds": 1.5}).raise_for_status()
        first = start_heating(api, fast)
        temperature(api, 17)
        wait_regulation(api, first, "heating")
        other = api.post("/api/pills", json={"name": "Seconda", "mac": "11:22:33:44:55:66"}).json()[
            "pill"
        ]
        heater = api.post(
            "/api/thermal-devices",
            json={"name": "Lento", "capability": "heating", "base_url": str(slow.base_url)},
        ).json()["device"]
        slow.patch(
            "/__simulation", json={"state_delay_seconds": 3, "control_http_status": 503}
        ).raise_for_status()
        second = api.post(
            "/api/fermentations",
            json={
                "name": "Seconda",
                "pill_id": other["id"],
                "control_mode": "heating",
                "heater_id": heater["id"],
                "temperature_min": 18,
                "temperature_max": 22,
                "hysteresis": 0.5,
            },
        ).json()["fermentation"]
        deadline = time.monotonic() + 3.5
        while time.monotonic() < deadline:
            temperature(api, 17)
            assert fast.get("/api/v1/state").json()["actual_mode"] == "heating"
            time.sleep(0.15)
        assert (
            api.get(f"/api/fermentations/{first['id']}").json()["fermentation"]["status"]
            == "active"
        )
        api.post(f"/api/fermentations/{first['id']}/end").raise_for_status()
        api.post(f"/api/fermentations/{second['id']}/end").raise_for_status()


@pytest.mark.parametrize(
    "change",
    [
        {"temperature_min": 22},
        {"temperature_max": 17},
        {"hysteresis": 0},
        {"hysteresis": -1},
        {"hysteresis": 5},
        {"temperature_min": None},
        {"temperature_max": float("inf")},
        {"hysteresis": float("nan")},
        {"heater_id": None},
        {"control_mode": "cooling"},
        {"cooler_id": "unused"},
        {"control_mode": "monitor_only"},
    ],
)
def test_invalid_thermal_settings_do_not_reserve_equipment(
    api: httpx.Client, change: dict[str, object]
) -> None:
    heater = api.post(
        "/api/thermal-devices",
        json={"name": "Fascia", "capability": "heating", "base_url": "http://thermal-heating:8000"},
    ).json()["device"]
    pill = api.get("/api/pills").json()["pills"][0]
    response = api.post(
        "/api/fermentations",
        content=json.dumps(
            {
                "name": "Non valida",
                "pill_id": pill["id"],
                "control_mode": "heating",
                "heater_id": heater["id"],
                "temperature_min": 18,
                "temperature_max": 22,
                "hysteresis": 0.5,
                **change,
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert api.get("/api/fermentations/active").json()["fermentations"] == []
    assert api.get("/api/thermal-devices").json()["devices"][0]["available"] is True
    assert api.get("/api/pills").json()["pills"][0]["available"] is True

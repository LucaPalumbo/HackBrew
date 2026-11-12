"""Thermal settings edits through public HTTP, including persistent revision history."""

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime

import httpx
import pytest

from tests.heating import start_heating, temperature, wait_regulation
from tests.heating_recovery import wait_device
from tests.thermal import thermal_simulator
from tests.thermal_regulation import register_thermal, thermal_cycle


def test_settings_edit_recalculates_control_and_keeps_original_assignment(
    api: httpx.Client,
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        received = api.get("/api/readings/latest").json()["last_received_at"]
        readings = api.get(f"/api/fermentations/{cycle['id']}/readings").json()
        response = api.patch(
            f"/api/fermentations/{cycle['id']}/thermal-settings",
            json={
                "expected_revision": 0,
                "temperature_min": 16,
                "temperature_max": 21,
                "hysteresis": 1,
            },
        )
        assert response.status_code == 200
        saved = response.json()["fermentation"]
        assert saved["thermal_settings_revision"] == 1
        for key in ("id", "pill_id", "devices", "name", "started_at", "ended_at", "control_mode"):
            assert saved[key] == cycle[key]
        idle = wait_regulation(api, cycle, "idle")
        assert idle["temperature_min"] == 16
        assert idle["temperature_max"] == 21
        assert idle["hysteresis"] == 1
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        assert api.get("/api/readings/latest").json()["last_received_at"] == received
        assert api.get(f"/api/fermentations/{cycle['id']}/readings").json() == readings
        history = api.get(f"/api/fermentations/{cycle['id']}/thermal-settings/history").json()[
            "history"
        ]
        assert [
            (row["revision"], row["temperature_min"], row["temperature_max"], row["hysteresis"])
            for row in history
        ] == [(0, 18, 22, 0.5), (1, 16, 21, 1)]
        assert datetime.fromisoformat(history[0]["changed_at"]) == datetime.fromisoformat(
            cycle["started_at"]
        )
        assert datetime.fromisoformat(history[1]["changed_at"]) >= datetime.fromisoformat(
            history[0]["changed_at"]
        )
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()


@pytest.mark.parametrize(
    "change",
    [
        {"temperature_min": 22},
        {"temperature_max": 17},
        {"hysteresis": 0},
        {"hysteresis": -1},
        {"hysteresis": 5},
        {"temperature_min": -274},
        {"temperature_min": None},
        {"temperature_max": float("inf")},
        {"hysteresis": float("nan")},
        {"expected_revision": -1},
        {"expected_revision": True},
        {"name": "Sostituito"},
        {"pill_id": "altra"},
        {"heater_id": "altro"},
    ],
)
def test_invalid_edit_does_not_partially_save_values_or_history(
    api: httpx.Client, change: dict[str, object]
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        path = f"/api/fermentations/{cycle['id']}/thermal-settings"
        before = api.get(path + "/history").json()["history"]
        response = api.patch(
            path,
            content=json.dumps(
                {
                    "expected_revision": 0,
                    "temperature_min": 18,
                    "temperature_max": 22,
                    "hysteresis": 0.5,
                    **change,
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
        after = api.get(path + "/history").json()
        assert after["history"] == before
        assert after["fermentation"]["temperature_min"] == 18
        assert after["fermentation"]["temperature_max"] == 22
        assert after["fermentation"]["hysteresis"] == 0.5
        assert after["fermentation"]["thermal_settings_revision"] == 0


def test_concurrent_edits_report_conflict_and_record_only_the_winner(api: httpx.Client) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        path = f"/api/fermentations/{cycle['id']}/thermal-settings"
        candidates = [
            {
                "expected_revision": 0,
                "temperature_min": low,
                "temperature_max": 25,
                "hysteresis": 0.5,
            }
            for low in range(10, 18)
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda payload: api.patch(path, json=payload), candidates))
        assert [r.status_code for r in responses].count(200) == 1
        assert [r.status_code for r in responses].count(409) == 7
        winner = next(r.json()["fermentation"] for r in responses if r.status_code == 200)
        observed = api.get(path + "/history").json()
        assert observed["fermentation"]["thermal_settings_revision"] == 1
        assert len(observed["history"]) == 2
        assert observed["history"][-1]["temperature_min"] == winner["temperature_min"]
        # A stale retry must not append another change.
        assert api.patch(path, json=candidates[0]).status_code == 409
        assert api.get(path + "/history").json()["history"] == observed["history"]


@pytest.mark.parametrize(
    "mode,roles",
    [
        ("heating", {"heater": "heating"}),
        ("cooling", {"cooler": "cooling"}),
        ("heating_cooling", {"heater": "heating", "cooler": "cooling"}),
        ("combined", {"combined": "both"}),
    ],
)
def test_edits_recalculate_each_mode_and_preserve_off_interlocks(
    api: httpx.Client, mode: str, roles: dict[str, str]
) -> None:
    with ExitStack() as stack:
        simulators = {
            role: stack.enter_context(thermal_simulator(capability))
            for role, capability in roles.items()
        }
        devices = {
            role: register_thermal(api, simulators[role], capability)
            for role, capability in roles.items()
        }
        cycle = thermal_cycle(api, mode, devices)
        path = f"/api/fermentations/{cycle['id']}/thermal-settings"
        temperature(api, 17 if mode == "heating" else 23)
        wait_regulation(api, cycle, "heating" if mode == "heating" else "cooling")
        response = api.patch(
            path,
            json={
                "expected_revision": 0,
                "temperature_min": 16,
                "temperature_max": 25,
                "hysteresis": 0.75,
            },
        )
        response.raise_for_status()
        wait_regulation(api, cycle, "idle")
        assert all(
            s.get("/api/v1/state").json()["actual_mode"] == "off" for s in simulators.values()
        )
        if mode in {"combined", "heating_cooling"}:
            # The last temperature now requires heating, after the cooler has stopped.
            api.patch(
                path,
                json={
                    "expected_revision": 1,
                    "temperature_min": 24,
                    "temperature_max": 27,
                    "hysteresis": 1,
                },
            ).raise_for_status()
            wait_regulation(api, cycle, "heating")
            if "cooler" in simulators:
                assert simulators["cooler"].get("/api/v1/state").json()["actual_mode"] == "off"
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
        wait_regulation(api, cycle, "stopped")


def test_edit_without_data_or_after_timeout_cannot_start_or_reset_contact(
    api: httpx.Client,
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        path = f"/api/fermentations/{cycle['id']}/thermal-settings"
        api.patch(
            path,
            json={
                "expected_revision": 0,
                "temperature_min": 20,
                "temperature_max": 25,
                "hysteresis": 1,
            },
        ).raise_for_status()
        wait_regulation(api, cycle, "waiting")
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        received = api.get("/api/readings/latest").json()["last_received_at"]
        api.patch("/api/settings", json={"communication_timeout_seconds": 0.1}).raise_for_status()
        wait_regulation(api, cycle, "suspended")
        api.patch(
            path,
            json={
                "expected_revision": 1,
                "temperature_min": 21,
                "temperature_max": 26,
                "hysteresis": 1,
            },
        ).raise_for_status()
        wait_regulation(api, cycle, "suspended")
        assert api.get("/api/readings/latest").json()["last_received_at"] == received
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"


def test_late_commands_and_unconfirmed_devices_cannot_claim_new_settings_are_applied(
    api: httpx.Client,
) -> None:
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        path = f"/api/fermentations/{cycle['id']}/thermal-settings"
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        old_on = simulator.get("/api/v1/state").json()["accepted_command"]
        simulator.patch("/__simulation", json={"apply_delay_seconds": 0.7}).raise_for_status()
        api.patch(
            path,
            json={
                "expected_revision": 0,
                "temperature_min": 16,
                "temperature_max": 22,
                "hysteresis": 0.5,
            },
        ).raise_for_status()
        wait_device(simulator, lambda s: s["accepted_command"]["mode"] == "off")
        pending = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
        assert pending["regulation"]["status"] in {"pending", "suspended"}
        assert pending["regulation"]["desired_mode"] == "off"
        assert pending["regulation"]["actual_mode"] == "heating"
        api.patch(
            path,
            json={
                "expected_revision": 1,
                "temperature_min": 20,
                "temperature_max": 25,
                "hysteresis": 1,
            },
        ).raise_for_status()
        api.patch(
            path,
            json={
                "expected_revision": 2,
                "temperature_min": 15,
                "temperature_max": 22,
                "hysteresis": 1,
            },
        ).raise_for_status()
        final = wait_regulation(api, cycle, "idle")
        assert final["thermal_settings_revision"] == 3
        assert final["temperature_min"] == 15
        assert simulator.put("/api/v1/control", json=old_on).status_code == 409
        simulator.patch(
            "/__simulation", json={"state_http_status": 503, "control_http_status": 503}
        ).raise_for_status()
        wait_regulation(api, cycle, "suspended")
        api.patch(
            path,
            json={
                "expected_revision": 3,
                "temperature_min": 21,
                "temperature_max": 26,
                "hysteresis": 1,
            },
        ).raise_for_status()
        suspended = wait_regulation(api, cycle, "suspended")
        assert suspended["regulation"]["actual_mode"] is None
        assert suspended["regulation"]["desired_mode"] == "off"
        assert suspended["regulation"]["error"]
        simulator.patch(
            "/__simulation",
            json={"state_http_status": 200, "control_http_status": 200, "apply_delay_seconds": 0},
        ).raise_for_status()
        wait_regulation(api, cycle, "heating")


def test_monitor_only_rejects_settings_and_end_wins_over_concurrent_edit(api: httpx.Client) -> None:
    pill = api.get("/api/pills").json()["pills"][0]
    monitor = api.post(
        "/api/fermentations", json={"name": "Monitor", "pill_id": pill["id"]}
    ).json()["fermentation"]
    payload = {
        "expected_revision": 0,
        "temperature_min": 20,
        "temperature_max": 25,
        "hysteresis": 1,
    }
    assert (
        api.patch(f"/api/fermentations/{monitor['id']}/thermal-settings", json=payload).status_code
        == 422
    )
    assert (
        api.get(f"/api/fermentations/{monitor['id']}/thermal-settings/history").json()["history"]
        == []
    )
    api.post(f"/api/fermentations/{monitor['id']}/end").raise_for_status()
    assert api.patch("/api/fermentations/missing/thermal-settings", json=payload).status_code == 404
    with thermal_simulator("heating") as simulator:
        cycle = start_heating(api, simulator)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        path = f"/api/fermentations/{cycle['id']}"
        with ThreadPoolExecutor(max_workers=2) as pool:
            edit = pool.submit(api.patch, path + "/thermal-settings", json=payload)
            end = pool.submit(api.post, path + "/end")
            assert edit.result().status_code in {200, 409}
            ended = end.result().json()["fermentation"]
        stopped = wait_regulation(api, cycle, "stopped")
        assert stopped["status"] == "concluded"
        assert stopped["ended_at"] == ended["ended_at"]
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        revision = stopped["thermal_settings_revision"]
        assert (
            api.patch(
                path + "/thermal-settings", json={**payload, "expected_revision": revision}
            ).status_code
            == 409
        )
        assert len(api.get(path + "/thermal-settings/history").json()["history"]) == revision + 1

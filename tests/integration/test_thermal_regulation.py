"""Cooling and coordinated equipment observed through public HTTP interfaces."""

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import httpx
import pytest

from tests.heating import temperature, wait_regulation
from tests.heating_recovery import wait_device
from tests.thermal import thermal_simulator
from tests.thermal_regulation import register_thermal, thermal_cycle, wait_cycle


def test_overlapping_device_sets_are_reserved_atomically(api: httpx.Client) -> None:
    with thermal_simulator("heating") as heater, thermal_simulator("cooling") as cooler:
        heating = api.post(
            "/api/thermal-devices",
            json={"name": "Fascia", "capability": "heating", "base_url": str(heater.base_url)},
        ).json()["device"]
        cooling = api.post(
            "/api/thermal-devices",
            json={"name": "Frigo", "capability": "cooling", "base_url": str(cooler.base_url)},
        ).json()["device"]
        pill = api.get("/api/pills").json()["pills"][0]
        other = api.post("/api/pills", json={"name": "Seconda", "mac": "11:22:33:44:55:66"}).json()[
            "pill"
        ]
        settings = {"name": "IPA", "temperature_min": 18, "temperature_max": 22, "hysteresis": 0.5}
        paired = {
            **settings,
            "pill_id": pill["id"],
            "control_mode": "heating_cooling",
            "heater_id": heating["id"],
            "cooler_id": cooling["id"],
        }
        single = {
            **settings,
            "pill_id": other["id"],
            "control_mode": "cooling",
            "cooler_id": cooling["id"],
        }
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(
                pool.map(
                    lambda body: api.post("/api/fermentations", json=body), [paired, single] * 4
                )
            )
        assert [r.status_code for r in responses].count(201) == 1
        assert [r.status_code for r in responses].count(409) == 7
        winner = next(r.json()["fermentation"] for r in responses if r.status_code == 201)
        registry = {
            device["id"]: device for device in api.get("/api/thermal-devices").json()["devices"]
        }
        assert registry[cooling["id"]]["reserved_fermentation_id"] == winner["id"]
        assert registry[heating["id"]]["available"] == (winner["control_mode"] == "cooling")
        expected = (
            {cooling["id"]}
            if winner["control_mode"] == "cooling"
            else {cooling["id"], heating["id"]}
        )
        assert {device["id"] for device in winner["devices"]} == expected
        assert len(api.get("/api/fermentations/active").json()["fermentations"]) == 1


@pytest.mark.parametrize(
    "mode,roles",
    [
        ("cooling", {"cooler": "cooling"}),
        ("heating_cooling", {"heater": "heating", "cooler": "cooling"}),
        ("combined", {"combined": "both"}),
    ],
)
def test_thermal_thresholds_and_hysteresis_for_each_configuration(
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
        sequence = [
            (22, "cooling"),
            (21.75, "cooling"),
            (21.5, "idle"),
            (21.75, "idle"),
            (23, "cooling"),
        ]
        if mode != "cooling":
            sequence += [(18, "heating"), (18.25, "heating"), (18.5, "idle"), (22, "cooling")]
        else:
            sequence += [(18, "idle")]
        for value, expected in sequence:
            temperature(api, value)
            observed = wait_regulation(api, cycle, expected)
            actual = "off" if expected == "idle" else expected
            assert observed["regulation"]["desired_mode"] == actual
            assert observed["regulation"]["actual_mode"] == actual
            active = [
                simulator.get("/api/v1/state").json()["actual_mode"]
                for simulator in simulators.values()
            ]
            assert len([state for state in active if state != "off"]) <= 1
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
        stopped = wait_regulation(api, cycle, "stopped")
        assert stopped["reserved_device_ids"] == []
        assert all(
            simulator.get("/api/v1/state").json()["actual_mode"] == "off"
            for simulator in simulators.values()
        )


@pytest.mark.parametrize("mode", ["heating_cooling", "combined"])
@pytest.mark.parametrize("initial,target", [("heating", "cooling"), ("cooling", "heating")])
def test_opposite_function_waits_for_physical_off_confirmation(
    api: httpx.Client, mode: str, initial: str, target: str
) -> None:
    roles = (
        {"heater": "heating", "cooler": "cooling"}
        if mode == "heating_cooling"
        else {"combined": "both"}
    )
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
        temperature(api, 17 if initial == "heating" else 23)
        wait_regulation(api, cycle, initial)
        previous = simulators[
            "combined" if mode == "combined" else "heater" if initial == "heating" else "cooler"
        ]
        old_on = previous.get("/api/v1/state").json()["accepted_command"]
        previous.patch("/__simulation", json={"apply_delay_seconds": 0.5}).raise_for_status()
        temperature(api, 17 if target == "heating" else 23)
        pending = wait_device(
            previous, lambda state: state["accepted_command"]["mode"] in {"off", target}
        )
        assert pending["accepted_command"]["mode"] == "off", (
            "An opposite ON arrived before a confirmed OFF"
        )
        assert pending["actual_mode"] == initial
        previous.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        wait_regulation(api, cycle, "suspended")
        time.sleep(0.65)
        for simulator in simulators.values():
            assert simulator.get("/api/v1/state").json()["accepted_command"]["mode"] == "off"
        previous.patch(
            "/__simulation", json={"confirmation_available": True, "apply_delay_seconds": 0}
        ).raise_for_status()
        wait_regulation(api, cycle, target)
        assert previous.put("/api/v1/control", json=old_on).status_code == 409
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
        wait_regulation(api, cycle, "stopped")


def test_partial_shutdown_releases_only_confirmed_devices_and_cannot_affect_reuse(
    api: httpx.Client,
) -> None:
    with thermal_simulator("heating") as heater, thermal_simulator("cooling") as cooler:
        devices = {
            "heater": register_thermal(api, heater, "heating"),
            "cooler": register_thermal(api, cooler, "cooling"),
        }
        cycle = thermal_cycle(api, "heating_cooling", devices)
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        old_on = heater.get("/api/v1/state").json()["accepted_command"]
        cooler.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        ended = api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]
        partial = wait_cycle(
            api,
            cycle,
            lambda snapshot: snapshot["reserved_device_ids"] == [devices["cooler"]["id"]],
        )
        assert partial["status"] == "concluded"
        assert partial["regulation"]["status"] == "stopping"
        assert partial["regulation"]["devices"][devices["cooler"]["id"]]["actual_mode"] is None
        registry = {
            device["id"]: device for device in api.get("/api/thermal-devices").json()["devices"]
        }
        assert registry[devices["heater"]["id"]]["available"] is True
        assert registry[devices["cooler"]["id"]]["available"] is False
        other = api.post("/api/pills", json={"name": "Altra", "mac": "11:22:33:44:55:66"}).json()[
            "pill"
        ]
        reused = thermal_cycle(api, "heating", {"heater": devices["heater"]}, other["id"])
        temperature(api, 17, other["mac"])
        wait_regulation(api, reused, "heating")
        cooler.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        stopped = wait_regulation(api, cycle, "stopped")
        assert stopped["ended_at"] == ended["ended_at"]
        assert stopped["reserved_device_ids"] == []
        assert heater.get("/api/v1/state").json()["actual_mode"] == "heating"
        assert (
            heater.get("/api/v1/state").json()["accepted_command"]["ownership_id"] == reused["id"]
        )
        assert heater.put("/api/v1/control", json=old_on).status_code == 409
        temperature(api, 16)
        assert (
            api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]["ended_at"]
            == ended["ended_at"]
        )
        api.post(f"/api/fermentations/{reused['id']}/end").raise_for_status()
        wait_regulation(api, reused, "stopped")


def test_one_failed_device_suspends_both_and_timeout_stops_the_full_set(api: httpx.Client) -> None:
    with thermal_simulator("heating") as heater, thermal_simulator("cooling") as cooler:
        devices = {
            "heater": register_thermal(api, heater, "heating"),
            "cooler": register_thermal(api, cooler, "cooling"),
        }
        cycle = thermal_cycle(api, "heating_cooling", devices)
        temperature(api, 23)
        wait_regulation(api, cycle, "cooling")
        heater.patch(
            "/__simulation", json={"state_http_status": 503, "control_http_status": 503}
        ).raise_for_status()
        failed = wait_cycle(
            api,
            cycle,
            lambda snapshot: (
                snapshot["regulation"]["status"] == "suspended"
                and snapshot["regulation"]["devices"][devices["heater"]["id"]]["actual_mode"]
                is None
                and snapshot["regulation"]["devices"][devices["cooler"]["id"]]["actual_mode"]
                == "off"
            ),
        )
        assert failed["status"] == "active"
        assert failed["regulation"]["desired_mode"] == "off"
        assert failed["regulation"]["devices"][devices["heater"]["id"]]["error"]
        for _ in range(4):
            temperature(api, 17)
            assert cooler.get("/api/v1/state").json()["accepted_command"]["mode"] == "off"
            time.sleep(0.1)
        heater.patch(
            "/__simulation", json={"state_http_status": 200, "control_http_status": 200}
        ).raise_for_status()
        wait_regulation(api, cycle, "heating")
        api.patch("/api/settings", json={"communication_timeout_seconds": 0.7}).raise_for_status()
        temperature(api, 17)
        wait_regulation(api, cycle, "heating")
        expired = wait_cycle(
            api,
            cycle,
            lambda snapshot: (
                snapshot["regulation"]["status"] == "suspended"
                and "Timeout" in (snapshot["regulation"]["reason"] or "")
                and snapshot["regulation"]["actual_mode"] == "off"
            ),
        )
        assert set(expired["reserved_device_ids"]) == {device["id"] for device in devices.values()}
        for simulator in (heater, cooler):
            assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
        wait_regulation(api, cycle, "stopped")


@pytest.mark.parametrize("mode", ["heating_cooling", "combined"])
def test_delayed_state_response_cannot_override_a_definitive_end(
    api: httpx.Client, mode: str
) -> None:
    roles = (
        {"heater": "heating", "cooler": "cooling"}
        if mode == "heating_cooling"
        else {"combined": "both"}
    )
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
        temperature(api, 23)
        wait_regulation(api, cycle, "cooling")
        active = simulators["cooler" if mode == "heating_cooling" else "combined"]
        old_on = active.get("/api/v1/state").json()["accepted_command"]
        active.patch("/__simulation", json={"state_delay_seconds": 1}).raise_for_status()
        time.sleep(0.15)
        ended = api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]
        assert all(
            control["desired_mode"] == "off" for control in ended["regulation"]["devices"].values()
        )
        temperature(api, 23)
        until = time.monotonic() + 1.3
        while time.monotonic() < until:
            current = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
            assert current["status"] == "concluded"
            assert current["regulation"]["desired_mode"] == "off"
            assert current["ended_at"] == ended["ended_at"]
            time.sleep(0.05)
        active.patch("/__simulation", json={"state_delay_seconds": 0}).raise_for_status()
        stopped = wait_regulation(api, cycle, "stopped")
        assert stopped["reserved_device_ids"] == []
        assert active.put("/api/v1/control", json=old_on).status_code == 409


@pytest.mark.parametrize(
    "mode,selection",
    [
        ("heating", {"heater": "cooler"}),
        ("cooling", {"cooler": "heater"}),
        ("combined", {"combined": "cooler"}),
        ("combined", {"combined": "combined", "heater": "heater"}),
        ("heating_cooling", {"heater": "heater"}),
        ("heating_cooling", {"heater": "combined", "cooler": "cooler"}),
        ("heating_cooling", {"heater": "heater", "cooler": "heater"}),
        ("cooling", {"cooler": "cooler", "combined": "combined"}),
    ],
)
def test_incompatible_equipment_selection_does_not_reserve_any_device(
    api: httpx.Client, mode: str, selection: dict[str, str]
) -> None:
    devices = {}
    for role, capability in {"heater": "heating", "cooler": "cooling", "combined": "both"}.items():
        devices[role] = api.post(
            "/api/thermal-devices",
            json={
                "name": role,
                "capability": capability,
                "base_url": f"http://thermal-{capability}:8000",
            },
        ).json()["device"]
    pill = api.get("/api/pills").json()["pills"][0]
    response = api.post(
        "/api/fermentations",
        json={
            "name": "Non valida",
            "pill_id": pill["id"],
            "control_mode": mode,
            "temperature_min": 18,
            "temperature_max": 22,
            "hysteresis": 0.5,
            **{role + "_id": devices[source]["id"] for role, source in selection.items()},
        },
    )
    assert response.status_code == 422
    assert api.get("/api/fermentations/active").json()["fermentations"] == []
    assert all(device["available"] for device in api.get("/api/thermal-devices").json()["devices"])
    assert api.get("/api/pills").json()["pills"][0]["available"] is True

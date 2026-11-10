"""Observe two-device ownership and control across actual application crashes."""

from collections.abc import Callable

import httpx
from playwright.sync_api import Page

from tests.database import reset_test_database
from tests.heating import temperature, wait_regulation
from tests.heating_recovery import wait_device
from tests.payloads import register_test_pill
from tests.thermal import thermal_simulator
from tests.thermal_regulation import register_thermal, thermal_cycle, wait_cycle


def verify_thermal_recovery(
    api: httpx.Client, page: Page, phase: Callable[[str, str, Page], None]
) -> None:
    reset_test_database()
    register_test_pill(api)
    with thermal_simulator("heating") as heater, thermal_simulator("cooling") as cooler:
        api.patch("/api/settings", json={"communication_timeout_seconds": 20}).raise_for_status()
        devices = {
            "heater": register_thermal(api, heater, "heating"),
            "cooler": register_thermal(api, cooler, "cooling"),
        }
        cycle = thermal_cycle(api, "heating_cooling", devices)
        temperature(api, 23)
        wait_regulation(api, cycle, "cooling")
        temperature(api, 21.75)
        previous = cooler.get("/api/v1/state").json()["accepted_command"]
        phase("restart-pair-regulation", "pair-regulation-up", page)
        current = wait_device(
            cooler,
            lambda s: (
                s["actual_mode"] == "cooling"
                and s["accepted_command"]["sequence"] > previous["sequence"]
            ),
        )
        assert current["accepted_command"]["ownership_id"] == cycle["id"]
        preserved = wait_regulation(api, cycle, "cooling")
        assert set(preserved["reserved_device_ids"]) == {d["id"] for d in devices.values()}
        assert {d["role"] for d in preserved["devices"]} == {"heater", "cooler"}
        assert heater.get("/api/v1/state").json()["actual_mode"] == "off"
        assert all(not d["available"] for d in api.get("/api/thermal-devices").json()["devices"])
        cooler.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        wait_regulation(api, cycle, "suspended")
        ended = api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]
        wait_cycle(api, cycle, lambda s: s["reserved_device_ids"] == [devices["cooler"]["id"]])
        phase("restart-pair-shutdown", "pair-shutdown-up", page)
        pending = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
        assert pending["status"] == "concluded"
        assert pending["ended_at"] == ended["ended_at"]
        assert pending["reserved_device_ids"] == [devices["cooler"]["id"]]
        registry = {d["id"]: d for d in api.get("/api/thermal-devices").json()["devices"]}
        assert registry[devices["heater"]["id"]]["available"] is True
        assert registry[devices["cooler"]["id"]]["available"] is False
        other = api.post(
            "/api/pills", json={"name": "Nuova IPA", "mac": "11:22:33:44:55:66"}
        ).json()["pill"]
        reused = thermal_cycle(api, "heating", {"heater": devices["heater"]}, other["id"])
        temperature(api, 17, other["mac"])
        wait_regulation(api, reused, "heating")
        cooler.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        stopped = wait_regulation(api, cycle, "stopped")
        assert stopped["reserved_device_ids"] == []
        assert stopped["ended_at"] == ended["ended_at"]
        assert cooler.put("/api/v1/control", json=previous).status_code == 409
        assert heater.get("/api/v1/state").json()["actual_mode"] == "heating"
        assert (
            heater.get("/api/v1/state").json()["accepted_command"]["ownership_id"] == reused["id"]
        )
        api.post(f"/api/fermentations/{reused['id']}/end").raise_for_status()
        wait_regulation(api, reused, "stopped")
    print(
        "Thermal recovery: coppia e isteresi preservate; "
        "OFF pendente e riuso separato riconciliati.",
        flush=True,
    )

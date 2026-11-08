"""Global timeout configuration through the public HTTP API."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from tests.payloads import gateway_lettura
from tests.settings import wait_for_sync
from tests.thermal import claim_command, discordant_configuration_device, thermal_simulator


def test_timeout_starts_at_three_hours_and_changes_while_monitoring(api: httpx.Client) -> None:
    response = api.get("/api/settings")
    assert response.status_code == 200
    initial = response.json()
    assert initial["communication_timeout_seconds"] == 10800
    assert initial["revision"] == 0
    assert initial["devices"] == []
    pill = api.get("/api/pills").json()["pills"][0]
    cycle = api.post("/api/fermentations", json={"name": "IPA", "pill_id": pill["id"]}).json()[
        "fermentation"
    ]
    changed = api.patch("/api/settings", json={"communication_timeout_seconds": 0.5})
    assert changed.status_code == 200
    assert changed.json()["communication_timeout_seconds"] == 0.5
    assert changed.json()["revision"] == 1
    assert api.get("/api/settings").json() == changed.json()
    repeated = api.patch("/api/settings", json={"communication_timeout_seconds": 0.5})
    assert repeated.json()["revision"] == 1
    assert api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"] == cycle


def test_saved_timeout_is_physically_confirmed_without_control_mode_commands(
    api: httpx.Client,
) -> None:
    with thermal_simulator() as simulator:
        device = api.post(
            "/api/thermal-devices",
            json={"name": "Frigo", "capability": "both", "base_url": str(simulator.base_url)},
        ).json()["device"]
        saved = api.patch("/api/settings", json={"communication_timeout_seconds": 1.25}).json()
        assert saved["revision"] == 1
        deadline = time.monotonic() + 10
        observed = None
        while time.monotonic() < deadline:
            observed = api.get("/api/settings").json()["devices"][0]
            if observed["status"] == "confirmed":
                break
            time.sleep(0.1)
        assert observed is not None and observed["status"] == "confirmed"
        assert observed["id"] == device["id"]
        assert observed["applied_revision"] == 1
        assert observed["applied_timeout_seconds"] == 1.25
        state = simulator.get("/api/v1/state").json()
        assert state["applied_timeout_seconds"] == 1.25
        assert state["applied_config_revision"] == 1
        assert state["actual_mode"] == "off"
        assert state["accepted_command"] is None
        assert state["last_command_at"] is None


def test_communication_timeout_uses_last_receipt_and_settings_polling_does_not_renew_it(
    api: httpx.Client,
) -> None:

    api.post("/telemetry", json=gateway_lettura(timestamp=1700000000)).raise_for_status()
    snapshot = api.get("/api/readings/latest").json()
    assert snapshot["communication_timeout_seconds"] == 10800
    assert "freshness_seconds" not in snapshot
    assert snapshot["pills"][0]["communication_status"] == "receiving"
    contact = snapshot["last_received_at"]
    api.patch("/api/settings", json={"communication_timeout_seconds": 0.15}).raise_for_status()
    for _ in range(3):
        api.get("/api/settings").raise_for_status()
        api.get("/api/bridge/pills").raise_for_status()
        time.sleep(0.1)
    expired = api.get("/api/readings/latest").json()
    assert expired["communication_timeout_seconds"] == 0.15
    assert expired["last_received_at"] == contact
    assert expired["pills"][0]["communication_status"] == "timed_out"


@pytest.mark.parametrize(
    "value", [0, -1, None, True, "10", "nan", {}, [], float("nan"), float("inf"), float("-inf")]
)
def test_invalid_timeout_does_not_change_persisted_configuration(
    api: httpx.Client, value: object
) -> None:
    original = api.get("/api/settings").json()
    response = api.patch(
        "/api/settings",
        content=json.dumps({"communication_timeout_seconds": value}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert api.get("/api/settings").json() == original


def test_unreachable_and_delayed_device_recovers_the_current_revision(api: httpx.Client) -> None:
    with thermal_simulator() as simulator:
        simulator.patch("/__simulation", json={"state_http_status": 503}).raise_for_status()
        device = api.post(
            "/api/thermal-devices",
            json={"name": "Frigo", "capability": "both", "base_url": str(simulator.base_url)},
        ).json()["device"]
        api.patch("/api/settings", json={"communication_timeout_seconds": 2.5}).raise_for_status()
        failed = wait_for_sync(api, device["id"], "error")
        assert failed["applied_revision"] != 1
        simulator.patch(
            "/__simulation", json={"state_http_status": 200, "apply_delay_seconds": 0.8}
        ).raise_for_status()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = simulator.get("/api/v1/state").json()
            if state["configuration_command"] is not None:
                break
            time.sleep(0.05)
        pending = api.get("/api/settings").json()["devices"][0]
        assert pending["status"] != "confirmed"
        assert pending["applied_revision"] != 1
        wait_for_sync(api, device["id"], revision=1)
        old_boot = simulator.get("/api/v1/state").json()["boot_id"]
        simulator.post("/__simulation/reset").raise_for_status()
        assert simulator.get("/api/v1/state").json()["boot_id"] != old_boot
        wait_for_sync(api, device["id"], revision=1)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if simulator.get("/api/v1/state").json()["applied_config_revision"] == 1:
                break
            time.sleep(0.05)
        assert simulator.get("/api/v1/state").json()["applied_timeout_seconds"] == 2.5


def test_new_setting_supersedes_pending_application_without_old_confirmation_winning(
    api: httpx.Client,
) -> None:
    with thermal_simulator() as simulator:
        simulator.patch("/__simulation", json={"apply_delay_seconds": 1}).raise_for_status()
        device = api.post(
            "/api/thermal-devices",
            json={"name": "Frigo", "capability": "both", "base_url": str(simulator.base_url)},
        ).json()["device"]
        api.patch("/api/settings", json={"communication_timeout_seconds": 2}).raise_for_status()
        deadline = time.monotonic() + 10
        original = None
        while time.monotonic() < deadline:
            original = simulator.get("/api/v1/state").json()["configuration_command"]
            if original is not None and original["config_revision"] == 1:
                break
            time.sleep(0.05)
        assert original is not None
        changed = api.patch("/api/settings", json={"communication_timeout_seconds": 4}).json()
        assert changed["revision"] == 2
        assert changed["devices"][0]["status"] != "confirmed"
        confirmed = wait_for_sync(api, device["id"], revision=2)
        assert confirmed["applied_timeout_seconds"] == 4
        assert simulator.put("/api/v1/configuration", json=original).status_code == 409
        state = simulator.get("/api/v1/state").json()
        assert state["applied_config_revision"] == 2
        assert state["accepted_command"] is None


def test_configuration_changes_do_not_switch_an_existing_mode_or_renew_its_timer(
    api: httpx.Client,
) -> None:
    with thermal_simulator() as simulator:
        claim = claim_command(simulator)
        simulator.put("/api/v1/control", json=claim).raise_for_status()
        heating = {**claim, "command_id": "heating", "sequence": 2, "mode": "heating"}
        before = simulator.put("/api/v1/control", json=heating).json()
        device = api.post(
            "/api/thermal-devices",
            json={
                "name": "Riscaldatore",
                "capability": "both",
                "base_url": str(simulator.base_url),
            },
        ).json()["device"]
        api.patch("/api/settings", json={"communication_timeout_seconds": 120}).raise_for_status()
        wait_for_sync(api, device["id"], revision=1)
        state = simulator.get("/api/v1/state").json()
        assert state["actual_mode"] == "heating"
        assert state["last_command_at"] == before["last_command_at"]
        api.patch("/api/settings", json={"communication_timeout_seconds": 0.05}).raise_for_status()
        wait_for_sync(api, device["id"], revision=2)
        time.sleep(0.1)
        state = simulator.get("/api/v1/state").json()
        assert state["actual_mode"] == "off"
        assert state["last_command_at"] == before["last_command_at"]
        assert state["accepted_command"]["command_id"] == "heating"


def test_concurrent_saves_have_monotonic_revisions(api: httpx.Client) -> None:
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(
                lambda value: api.patch(
                    "/api/settings", json={"communication_timeout_seconds": value}
                ),
                [1, 2, 3, 4],
            )
        )
    assert all(response.status_code == 200 for response in responses)
    settings = api.get("/api/settings").json()
    assert settings["revision"] == 4
    assert settings["communication_timeout_seconds"] in {1, 2, 3, 4}


def test_an_acknowledgement_from_another_boot_is_not_current_confirmation(
    api: httpx.Client,
) -> None:
    with (
        thermal_simulator() as simulator,
        discordant_configuration_device(simulator) as (url, fault),
    ):
        device = api.post(
            "/api/thermal-devices", json={"name": "Frigo", "capability": "both", "base_url": url}
        ).json()["device"]
        api.patch("/api/settings", json={"communication_timeout_seconds": 3}).raise_for_status()
        deadline = time.monotonic() + 10
        observed = None
        while time.monotonic() < deadline:
            observed = api.get("/api/settings").json()["devices"][0]
            if observed["status"] in {"confirmed", "error"}:
                break
            time.sleep(0.05)
        assert observed is not None and observed["status"] == "error"
        assert observed["applied_revision"] != 1
        fault.clear()
        wait_for_sync(api, device["id"], revision=1)

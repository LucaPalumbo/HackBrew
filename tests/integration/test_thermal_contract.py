"""External HTTP conformance checks against the standalone actuator simulator."""

import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from tests.thermal import claim_command, thermal_simulator


@pytest.fixture(autouse=True)
def isolated_registry(empty_api: httpx.Client) -> None:
    """No registered application device may configure these standalone contract fixtures."""


def test_absolute_commands_are_idempotent_and_ordered() -> None:
    with thermal_simulator() as simulator:
        response = simulator.get("/api/v1/state")
        assert response.status_code == 200
        initial = response.json()
        assert initial["actual_mode"] == "off"
        assert initial["applied_timeout_seconds"] == 10800
        command = {
            "boot_id": initial["boot_id"],
            "command_id": "claim",
            "ownership_epoch": 1,
            "ownership_id": "fermentation-ipa",
            "sequence": 1,
            "mode": "off",
            "config_revision": 0,
        }
        claimed = simulator.put("/api/v1/control", json=command)
        assert claimed.status_code == 200
        heating = {**command, "command_id": "heat", "sequence": 2, "mode": "heating"}
        response = simulator.put("/api/v1/control", json=heating)
        assert response.status_code == 200
        state = response.json()
        assert state["actual_mode"] == "heating"
        assert state["applied_command_id"] == "heat"
        assert state["application_status"] == "applied"
        assert simulator.put("/api/v1/control", json=heating).json() == state
        assert simulator.get("/api/v1/state").json() == state
        off = {**command, "command_id": "off", "sequence": 3}
        assert simulator.put("/api/v1/control", json=off).json()["actual_mode"] == "off"
        assert simulator.put("/api/v1/control", json=heating).status_code == 409
        assert simulator.get("/api/v1/state").json()["applied_command_id"] == "off"


def test_autonomous_timeout_is_not_renewed_by_state_reads_or_retries() -> None:
    with thermal_simulator() as simulator:
        command = claim_command(simulator, timeout_seconds=0.8, config_revision=1)
        simulator.put("/api/v1/control", json=command).raise_for_status()
        heating = {**command, "command_id": "heat", "sequence": 2, "mode": "heating"}
        response = simulator.put("/api/v1/control", json=heating)
        assert response.status_code == 200
        deadline = response.json()["lease_expires_at"]
        for _ in range(3):
            time.sleep(0.1)
            state = simulator.get("/api/v1/state").json()
            assert state["actual_mode"] == "heating"
            assert state["lease_expires_at"] == deadline
        time.sleep(0.7)
        expired = simulator.get("/api/v1/state").json()
        assert expired["actual_mode"] == "off"
        assert expired["application_status"] == "timed_out"
        assert simulator.put("/api/v1/control", json=heating).json() == expired
        renewed = {**heating, "command_id": "renewed", "sequence": 3}
        assert simulator.put("/api/v1/control", json=renewed).json()["actual_mode"] == "heating"
        # No status request during this entire lease; the independent watchdog must act.
        time.sleep(0.95)
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"


def test_accepted_command_waits_for_physical_application_and_old_pending_on_is_cancelled() -> None:
    with thermal_simulator() as simulator:
        claim = claim_command(simulator)
        simulator.put("/api/v1/control", json=claim).raise_for_status()
        configured = simulator.patch("/__simulation", json={"apply_delay_seconds": 0.2})
        assert configured.status_code == 200
        heating = {**claim, "command_id": "delayed-on", "sequence": 2, "mode": "heating"}
        pending = simulator.put("/api/v1/control", json=heating).json()
        assert pending["desired_mode"] == "heating"
        assert pending["actual_mode"] == "off"
        assert pending["application_status"] == "pending"
        assert pending["applied_command_id"] == claim["command_id"]
        off = {**claim, "command_id": "newer-off", "sequence": 3}
        simulator.put("/api/v1/control", json=off).raise_for_status()
        time.sleep(0.3)
        state = simulator.get("/api/v1/state").json()
        assert state["actual_mode"] == "off"
        assert state["applied_command_id"] == "newer-off"
        assert state["application_status"] == "applied"
        simulator.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        unknown = simulator.get("/api/v1/state").json()
        assert unknown["actual_mode"] is None
        assert unknown["confirmed_at"] is None
        assert unknown["application_status"] == "unknown"


def test_delayed_old_commands_and_superseded_ownership_cannot_override_off() -> None:
    with thermal_simulator() as simulator, ThreadPoolExecutor(max_workers=1) as pool:
        claim = claim_command(simulator)
        simulator.put("/api/v1/control", json=claim).raise_for_status()
        simulator.patch("/__simulation", json={"control_delay_seconds": 0.4}).raise_for_status()
        heating = {**claim, "command_id": "late-on", "sequence": 2, "mode": "heating"}
        late = pool.submit(simulator.put, "/api/v1/control", json=heating)
        time.sleep(0.15)
        simulator.patch("/__simulation", json={"control_delay_seconds": 0}).raise_for_status()
        off = {**claim, "command_id": "new-off", "sequence": 3}
        simulator.put("/api/v1/control", json=off).raise_for_status()
        assert late.result().status_code == 409
        newer = {**claim, "command_id": "new-owner", "ownership_epoch": 2, "ownership_id": "stout"}
        simulator.put("/api/v1/control", json=newer).raise_for_status()
        stale = {**heating, "command_id": "old-owner", "sequence": 999}
        assert simulator.put("/api/v1/control", json=stale).status_code == 409
        conflict = {**newer, "command_id": "wrong-owner", "sequence": 2, "ownership_id": "other"}
        assert simulator.put("/api/v1/control", json=conflict).status_code == 409
        reused = {**newer, "sequence": 2}
        assert simulator.put("/api/v1/control", json=reused).status_code == 409
        assert simulator.get("/api/v1/state").json()["applied_command_id"] == "new-owner"
        simulator.post("/__simulation/reset").raise_for_status()
        assert simulator.put("/api/v1/control", json=newer).status_code == 409
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"


@pytest.mark.parametrize(
    "capability,unsupported", [("heating", "cooling"), ("cooling", "heating"), ("both", "both")]
)
def test_device_rejects_unsupported_and_simultaneous_modes(
    capability: str, unsupported: str
) -> None:
    with thermal_simulator(capability) as simulator:
        claim = claim_command(simulator)
        simulator.put("/api/v1/control", json=claim).raise_for_status()
        rejected = {**claim, "command_id": "unsupported", "sequence": 2, "mode": unsupported}
        assert simulator.put("/api/v1/control", json=rejected).status_code == 422
        assert simulator.get("/api/v1/state").json()["actual_mode"] == "off"


def test_rejected_commands_do_not_renew_or_reconfigure_the_device() -> None:
    with thermal_simulator() as simulator:
        claim = claim_command(simulator, timeout_seconds=1, config_revision=1)
        accepted = simulator.put("/api/v1/control", json=claim).json()
        for changes in (
            {"timeout_seconds": 0},
            {"timeout_seconds": -1},
            {"timeout_seconds": "3"},
            {"timeout_seconds": True},
            {"config_revision": -1},
            {"sequence": True},
        ):
            assert simulator.put("/api/v1/control", json={**claim, **changes}).status_code == 422
        outdated = {**claim, "command_id": "old-config", "sequence": 2, "config_revision": 0}
        assert simulator.put("/api/v1/control", json=outdated).status_code == 409
        conflict = {**claim, "command_id": "same-revision", "sequence": 2, "timeout_seconds": 2}
        assert simulator.put("/api/v1/control", json=conflict).status_code == 409
        assert simulator.get("/api/v1/state").json() == accepted
        simulator.patch("/__simulation", json={"control_http_status": 503}).raise_for_status()
        assert (
            simulator.put(
                "/api/v1/control", json={**claim, "sequence": 2, "command_id": "failed"}
            ).status_code
            == 503
        )
        assert simulator.get("/api/v1/state").json() == accepted

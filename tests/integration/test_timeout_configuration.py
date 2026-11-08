"""Configuration-only actuator commands preserve mode and communication origin."""

import time

import httpx
import pytest

from tests.thermal import claim_command, thermal_simulator


@pytest.fixture(autouse=True)
def isolated_registry(empty_api: httpx.Client) -> None:
    """The contract fixture is separate from the application's registry."""


def test_timeout_configuration_preserves_mode_and_does_not_renew_control_contact() -> None:
    with thermal_simulator() as simulator:
        claim = claim_command(simulator)
        simulator.put("/api/v1/control", json=claim).raise_for_status()
        heat = {**claim, "sequence": 2, "command_id": "heat", "mode": "heating"}
        before = simulator.put("/api/v1/control", json=heat).json()
        command = {
            "boot_id": before["boot_id"],
            "command_id": "configuration-one",
            "config_revision": 1,
            "timeout_seconds": 120,
            "expected_control_id": "heat",
        }
        response = simulator.put("/api/v1/configuration", json=command)
        assert response.status_code == 200
        state = response.json()
        assert state["actual_mode"] == "heating"
        assert state["desired_mode"] == "heating"
        assert state["accepted_command"] == before["accepted_command"]
        assert state["last_command_at"] == before["last_command_at"]
        assert state["applied_config_revision"] == 1
        assert state["applied_timeout_seconds"] == 120
        assert state["applied_configuration"]["command_id"] == "configuration-one"
        assert simulator.put("/api/v1/configuration", json=command).json() == state
        newer = {
            **command,
            "command_id": "configuration-two",
            "config_revision": 2,
            "timeout_seconds": 180,
        }
        simulator.put("/api/v1/configuration", json=newer).raise_for_status()
        assert simulator.put("/api/v1/configuration", json=command).status_code == 409
        current = simulator.get("/api/v1/state").json()
        assert current["applied_config_revision"] == 2
        assert current["actual_mode"] == "heating"


def test_configuration_rejects_changed_control_and_old_boot() -> None:
    with thermal_simulator() as simulator:
        claim = claim_command(simulator)
        simulator.put("/api/v1/control", json=claim).raise_for_status()
        command = {
            "boot_id": claim["boot_id"],
            "command_id": "stale-configuration",
            "expected_control_id": claim["command_id"],
            "config_revision": 1,
            "timeout_seconds": 4,
        }
        newer = {**claim, "command_id": "new-control", "sequence": 2}
        current = simulator.put("/api/v1/control", json=newer).json()
        assert simulator.put("/api/v1/configuration", json=command).status_code == 409
        assert simulator.get("/api/v1/state").json() == current
        restarted = simulator.post("/__simulation/reset").json()
        assert simulator.put("/api/v1/configuration", json=command).status_code == 409
        assert simulator.get("/api/v1/state").json() == restarted


def test_new_control_supersedes_delayed_configuration_without_rollback() -> None:
    with thermal_simulator() as simulator:
        claim = claim_command(simulator)
        simulator.put("/api/v1/control", json=claim).raise_for_status()
        simulator.patch("/__simulation", json={"apply_delay_seconds": 0.2}).raise_for_status()
        command = {
            "boot_id": claim["boot_id"],
            "command_id": "delayed-configuration",
            "expected_control_id": claim["command_id"],
            "config_revision": 1,
            "timeout_seconds": 4,
        }
        accepted = simulator.put("/api/v1/configuration", json=command).json()
        assert accepted["applied_config_revision"] == 0
        simulator.patch("/__simulation", json={"apply_delay_seconds": 0}).raise_for_status()
        control = {
            **claim,
            "sequence": 2,
            "command_id": "new-control",
            "config_revision": 2,
            "timeout_seconds": 8,
        }
        current = simulator.put("/api/v1/control", json=control).json()
        time.sleep(0.3)
        assert simulator.get("/api/v1/state").json() == current
        assert current["applied_config_revision"] == 2
        assert simulator.put("/api/v1/configuration", json=command).status_code == 409

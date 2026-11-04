"""Registration and observation through the public application HTTP API."""

import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from tests.thermal import malformed_http_device, thermal_simulator


def test_register_thermal_devices_without_claiming_a_physical_state(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    assert api.get("/api/thermal-devices").status_code == 200
    assert api.get("/api/thermal-devices").json() == {"devices": []}
    registered = []
    for capability in ("heating", "cooling", "both"):
        response = api.post(
            "/api/thermal-devices",
            json={
                "name": f"  {capability}  ",
                "capability": capability,
                "base_url": f"http://thermal-{capability}:8000/",
            },
        )
        assert response.status_code == 201
        device = response.json()["device"]
        assert device["id"]
        assert device["name"] == capability
        assert device["capability"] == capability
        assert device["base_url"] == f"http://thermal-{capability}:8000"
        assert device["verification_status"] == "unverified"
        assert device["actual_mode"] is None
        assert device["confirmed_at"] is None
        registered.append(device)
    assert {item["id"] for item in registered} == {
        item["id"] for item in api.get("/api/thermal-devices").json()["devices"]
    }
    duplicate = api.post(
        "/api/thermal-devices",
        json={"name": "Duplicato", "capability": "both", "base_url": "http://THERMAL-both:8000"},
    )
    assert duplicate.status_code == 409


def test_check_confirms_actual_state_without_issuing_a_control_command(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    with thermal_simulator("heating") as simulator:
        response = api.post(
            "/api/thermal-devices",
            json={
                "name": "Riscaldatore",
                "capability": "heating",
                "base_url": "http://thermal-heating:8000",
            },
        )
        device = response.json()["device"]
        checked = api.post(f"/api/thermal-devices/{device['id']}/check")
        assert checked.status_code == 200
        confirmed = checked.json()["device"]
        assert confirmed["verification_status"] == "confirmed"
        assert confirmed["actual_mode"] == "off"
        assert confirmed["reported_capability"] == "heating"
        assert confirmed["confirmed_at"]
        assert confirmed["applied_timeout_seconds"] == 10800
        assert confirmed["applied_config_revision"] == 0
        assert confirmed["last_confirmation"]["accepted_command"] is None
        assert simulator.get("/api/v1/state").json()["last_command_at"] is None
        assert api.get("/api/thermal-devices").json()["devices"] == [confirmed]
        assert api.post("/api/thermal-devices/unknown/check").status_code == 404
        assert api.post(
            f"/api/thermal-devices/{device['id']}/control", json={"mode": "heating"}
        ).status_code in {404, 405}
        assert api.post("/__simulation/reset").status_code in {404, 405}


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"name": 4},
        {"capability": "heating/cooling"},
        {"base_url": "ftp://device"},
        {"base_url": "not a url"},
        {"base_url": "http://device:99999"},
        {"base_url": "http://user:password@device"},
        {"base_url": "http://device/?mode=heating"},
        {"base_url": "http://device/#state"},
        {"base_url": True},
        {"actual_mode": "off"},
    ],
)
def test_invalid_thermal_registration_does_not_create_a_device(
    empty_api: httpx.Client, changes: dict[str, object]
) -> None:
    response = empty_api.post(
        "/api/thermal-devices",
        json={
            "name": "Frigo",
            "capability": "both",
            "base_url": "http://thermal-both:8000",
            **changes,
        },
    )
    assert response.status_code == 422
    assert empty_api.get("/api/thermal-devices").json()["devices"] == []


def test_concurrent_equivalent_thermal_addresses_register_one_device(
    empty_api: httpx.Client,
) -> None:
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(
                lambda url: empty_api.post(
                    "/api/thermal-devices",
                    json={
                        "name": "Frigo",
                        "capability": "both",
                        "base_url": url,
                    },
                ),
                ["http://THERMAL-both:80/", "http://thermal-both", "http://thermal-both/"] * 2,
            )
        )
    assert sum(response.status_code == 201 for response in responses) == 1
    assert sum(response.status_code == 409 for response in responses) == 5
    assert len(empty_api.get("/api/thermal-devices").json()["devices"]) == 1


def test_failed_or_unconfirmed_check_never_claims_off_and_can_recover(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    with thermal_simulator() as simulator:
        device = api.post(
            "/api/thermal-devices",
            json={
                "name": "Frigo",
                "capability": "both",
                "base_url": str(simulator.base_url),
            },
        ).json()["device"]
        path = f"/api/thermal-devices/{device['id']}/check"
        confirmed = api.post(path).json()["device"]
        assert confirmed["verification_status"] == "confirmed"
        simulator.patch("/__simulation", json={"state_http_status": 503}).raise_for_status()
        failed = api.post(path).json()["device"]
        assert failed["verification_status"] == "error"
        assert failed["actual_mode"] is None
        assert failed["confirmed_at"] is None
        assert failed["last_confirmation"] == confirmed["last_confirmation"]
        simulator.patch(
            "/__simulation", json={"state_http_status": 200, "confirmation_available": False}
        ).raise_for_status()
        unconfirmed = api.post(path).json()["device"]
        assert unconfirmed["verification_status"] == "pending"
        assert unconfirmed["actual_mode"] is None
        assert unconfirmed["last_confirmation"] == confirmed["last_confirmation"]
        simulator.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        assert api.post(path).json()["device"]["verification_status"] == "confirmed"
        simulator.patch("/__simulation", json={"state_delay_seconds": 2.5}).raise_for_status()
        timed_out = api.post(path).json()["device"]
        assert timed_out["verification_status"] == "error"
        assert timed_out["actual_mode"] is None


def test_unreachable_device_and_capability_mismatch_are_explicit_errors(
    empty_api: httpx.Client,
) -> None:
    with thermal_simulator("heating"):
        for url in ("http://thermal-heating:1", "http://thermal-heating:8000"):
            device = empty_api.post(
                "/api/thermal-devices",
                json={
                    "name": "Frigo",
                    "capability": "cooling",
                    "base_url": url,
                },
            ).json()["device"]
            checked = empty_api.post(f"/api/thermal-devices/{device['id']}/check").json()["device"]
            assert checked["verification_status"] == "error"
            assert checked["actual_mode"] is None
            assert checked["communication_error"]
            assert checked["last_confirmation"] is None


def test_a_slow_old_check_cannot_overwrite_a_newer_failure(empty_api: httpx.Client) -> None:
    api = empty_api
    with thermal_simulator() as simulator, ThreadPoolExecutor(max_workers=1) as pool:
        device = api.post(
            "/api/thermal-devices",
            json={
                "name": "Frigo",
                "capability": "both",
                "base_url": str(simulator.base_url),
            },
        ).json()["device"]
        path = f"/api/thermal-devices/{device['id']}/check"
        simulator.patch("/__simulation", json={"state_delay_seconds": 0.5}).raise_for_status()
        old = pool.submit(api.post, path)
        time.sleep(0.15)
        simulator.patch(
            "/__simulation", json={"state_delay_seconds": 0, "state_http_status": 503}
        ).raise_for_status()
        latest = api.post(path).json()["device"]
        assert latest["verification_status"] == "error"
        assert old.result().json()["device"] == latest
        assert api.get("/api/thermal-devices").json()["devices"] == [latest]


def test_malformed_http_success_is_not_physical_confirmation(empty_api: httpx.Client) -> None:
    with thermal_simulator() as simulator:
        simulator.patch("/__simulation", json={"malformed_state": True}).raise_for_status()
        device = empty_api.post(
            "/api/thermal-devices",
            json={
                "name": "Frigo",
                "capability": "both",
                "base_url": str(simulator.base_url),
            },
        ).json()["device"]
        checked = empty_api.post(f"/api/thermal-devices/{device['id']}/check").json()["device"]
        assert checked["verification_status"] == "error"
        assert checked["actual_mode"] is None
        assert checked["last_confirmation"] is None
        assert "protocollo" in checked["communication_error"]


def test_broken_http_framing_clears_current_confirmation_after_a_success(
    empty_api: httpx.Client,
) -> None:
    with thermal_simulator() as simulator:
        state = simulator.get("/api/v1/state").json()
        with malformed_http_device(state) as (url, external):
            device = empty_api.post(
                "/api/thermal-devices",
                json={
                    "name": "Frigo",
                    "capability": "both",
                    "base_url": url,
                },
            ).json()["device"]
            path = f"/api/thermal-devices/{device['id']}/check"
            confirmed = empty_api.post(path).json()["device"]
            assert confirmed["verification_status"] == "confirmed"
            external.set()
            response = empty_api.post(path)
            assert response.status_code == 200
            failed = response.json()["device"]
            assert failed["verification_status"] == "error"
            assert failed["actual_mode"] is None
            assert failed["confirmed_at"] is None
            assert failed["last_confirmation"] == confirmed["last_confirmation"]
            assert empty_api.get("/api/thermal-devices").json()["devices"] == [failed]

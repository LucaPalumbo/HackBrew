"""Thermal registry lifecycle through HTTP and real external actuators."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest

from tests.thermal import held_state_actuator, thermal_simulator
from tests.thermal_regulation import register_thermal, thermal_cycle, wait_cycle


def test_rename_and_change_address_preserve_identity_without_borrowed_confirmation(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    with thermal_simulator("heating") as simulator:
        device = register_thermal(api, simulator, "heating")
        path = f"/api/thermal-devices/{device['id']}"
        confirmed = api.post(path + "/check").json()["device"]
        assert confirmed["actual_mode"] == "off"
        renamed = api.patch(path, json={"name": "  Fascia nuova  "})
        assert renamed.status_code == 200
        assert renamed.json()["device"]["name"] == "Fascia nuova"
        assert renamed.json()["device"]["last_confirmation"] == confirmed["last_confirmation"]
        changed = api.patch(path, json={"base_url": "http://THERMAL-heating:1/"})
        assert changed.status_code == 200
        current = changed.json()["device"]
        assert current["id"] == device["id"]
        assert current["base_url"] == "http://thermal-heating:1"
        assert current["verification_status"] == "unverified"
        for field in ("actual_mode", "confirmed_at", "last_confirmation", "checked_at"):
            assert current[field] is None
        assert simulator.get("/api/v1/state").json()["last_command_at"] is None
        settings = api.get("/api/settings").json()["devices"][0]
        assert settings["status"] != "confirmed"
        assert settings["applied_revision"] is None
        assert api.get("/api/thermal-devices").json()["devices"] == [current]


def test_removal_waits_for_off_and_keeps_the_cycle_device_snapshot(api: httpx.Client) -> None:
    with thermal_simulator("heating") as simulator:
        device = register_thermal(api, simulator, "heating")
        path = f"/api/thermal-devices/{device['id']}"
        cycle = thermal_cycle(api, "heating", {"heater": device})
        wait_cycle(api, cycle, lambda current: current["regulation"]["actual_mode"] == "off")
        assert api.patch(path, json={"name": "Impossibile"}).status_code == 409
        assert api.patch(path, json={"base_url": "http://other.local"}).status_code == 409
        assert api.delete(path).status_code == 409
        simulator.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
        assert api.delete(path).status_code == 409
        assert api.patch(path, json={"name": "Ancora riservato"}).status_code == 409
        simulator.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        concluded = wait_cycle(api, cycle, lambda current: not current["thermal_reserved"])
        assert concluded["devices"][0]["base_url"] == str(simulator.base_url)
        renamed = api.patch(path, json={"name": "Nuovo nome", "base_url": "http://altro.local"})
        assert renamed.status_code == 200
        assert api.delete(path).status_code == 204
        assert api.get("/api/thermal-devices").json()["devices"] == []
        assert api.get("/api/settings").json()["devices"] == []
        assert api.post(path + "/check").status_code == 404
        assert api.patch(path, json={"name": "Scomparso"}).status_code == 404
        assert api.delete(path).status_code == 404
        assert api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"] == concluded
        replacement = api.post(
            "/api/thermal-devices",
            json={
                "name": "Sostituto",
                "capability": "heating",
                "base_url": "http://altro.local/",
            },
        )
        assert replacement.status_code == 201
        assert replacement.json()["device"]["id"] != device["id"]


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"name": " "},
        {"name": None},
        {"name": 3},
        {"name": "x" * 201},
        {"base_url": None},
        {"base_url": ""},
        {"base_url": "ftp://device"},
        {"base_url": "http://user:pass@device"},
        {"base_url": "http://device/?key=x"},
        {"base_url": "http://device/#fragment"},
        {"capability": "cooling"},
        {"actual_mode": "off"},
        {"archived": False},
    ],
)
def test_invalid_edits_leave_the_registry_unchanged(
    empty_api: httpx.Client,
    changes: dict[str, object],
) -> None:
    device = empty_api.post(
        "/api/thermal-devices",
        json={
            "name": "Fascia",
            "capability": "heating",
            "base_url": "http://fascia.local",
        },
    ).json()["device"]
    assert empty_api.patch(f"/api/thermal-devices/{device['id']}", json=changes).status_code == 422
    assert empty_api.get("/api/thermal-devices").json()["devices"] == [device]


def test_duplicate_address_edit_is_atomic_and_normalization_preserves_confirmation(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    with thermal_simulator("heating") as simulator:
        first = register_thermal(api, simulator, "heating")
        second = api.post(
            "/api/thermal-devices",
            json={
                "name": "Secondo",
                "capability": "heating",
                "base_url": "http://secondo.local",
            },
        ).json()["device"]
        path = f"/api/thermal-devices/{first['id']}"
        confirmed = api.post(path + "/check").json()["device"]
        equivalent = api.patch(path, json={"base_url": "http://THERMAL-heating:8000/"})
        assert equivalent.status_code == 200
        assert equivalent.json()["device"] == confirmed
        duplicate = api.patch(path, json={"name": "Non salvato", "base_url": second["base_url"]})
        assert duplicate.status_code == 409
        assert (
            next(
                d
                for d in api.get("/api/thermal-devices").json()["devices"]
                if d["id"] == first["id"]
            )
            == confirmed
        )
        assert (
            api.patch("/api/thermal-devices/missing", json={"name": "Assente"}).status_code == 404
        )


@pytest.mark.parametrize("remove", [False, True])
def test_inflight_verification_and_sync_cannot_publish_an_old_connection(
    empty_api: httpx.Client,
    remove: bool,
) -> None:
    api = empty_api
    with thermal_simulator("heating") as old, thermal_simulator("heating-secondary") as new:
        new.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        with (
            held_state_actuator(old) as (url, entered, release),
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            device = api.post(
                "/api/thermal-devices",
                json={
                    "name": "Fascia",
                    "capability": "heating",
                    "base_url": url,
                },
            ).json()["device"]
            path = f"/api/thermal-devices/{device['id']}"
            verification = pool.submit(api.post, path + "/check")
            # The configuration worker and explicit verification each entered the old HTTP endpoint.
            entered.get(timeout=5)
            entered.get(timeout=5)
            if remove:
                assert api.delete(path).status_code == 204
            else:
                changed = api.patch(path, json={"base_url": str(new.base_url)})
                assert changed.status_code == 200
                assert changed.json()["device"]["last_confirmation"] is None
            release.set()
            result = verification.result(timeout=5)
            if remove:
                assert result.status_code == 404
                assert api.get("/api/thermal-devices").json()["devices"] == []
                assert api.get("/api/settings").json()["devices"] == []
            else:
                assert result.status_code == 200
                assert result.json()["device"]["base_url"] == str(new.base_url)
                assert result.json()["device"]["last_confirmation"] is None
                current = api.get("/api/settings").json()["devices"][0]
                assert current["status"] != "confirmed"
                assert current["applied_revision"] is None
            assert old.get("/api/v1/state").json()["last_command_at"] is None


@pytest.mark.parametrize("operation", ["rename", "address", "remove"])
def test_start_and_registry_change_are_serialized(api: httpx.Client, operation: str) -> None:
    pill = api.get("/api/pills").json()["pills"][0]

    def send(
        gate: Barrier, method: str, target: str, body: dict[str, object] | None
    ) -> httpx.Response:
        gate.wait(timeout=5)
        return api.request(method, target, json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        for index in range(8):
            original = f"http://fascia-{index}.local"
            device = api.post(
                "/api/thermal-devices",
                json={
                    "name": "Nome originale",
                    "capability": "heating",
                    "base_url": original,
                },
            ).json()["device"]
            path = f"/api/thermal-devices/{device['id']}"
            gate = Barrier(2)

            start = pool.submit(
                send,
                gate,
                "POST",
                "/api/fermentations",
                {
                    "name": "Gara",
                    "pill_id": pill["id"],
                    "control_mode": "heating",
                    "heater_id": device["id"],
                    "temperature_min": 18,
                    "temperature_max": 22,
                    "hysteresis": 0.5,
                },
            )
            change = (
                pool.submit(send, gate, "DELETE", path, None)
                if operation == "remove"
                else pool.submit(
                    send,
                    gate,
                    "PATCH",
                    path,
                    {"name": "Nome nuovo"}
                    if operation == "rename"
                    else {"base_url": f"http://nuovo-{index}.local"},
                )
            )
            started, changed = start.result(), change.result()
            if operation == "remove" and changed.status_code == 204:
                assert started.status_code == 404
                continue
            assert started.status_code == 201
            cycle = started.json()["fermentation"]
            assert changed.status_code in {200, 409}
            snapshot = cycle["devices"][0]
            assert snapshot["id"] == device["id"]
            if changed.status_code == 200:
                assert snapshot["name"] == (
                    "Nome nuovo" if operation == "rename" else "Nome originale"
                )
                assert snapshot["base_url"] == (
                    f"http://nuovo-{index}.local" if operation == "address" else original
                )
            else:
                assert snapshot["name"] == "Nome originale"
                assert snapshot["base_url"] == original
            api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()

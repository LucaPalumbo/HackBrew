"""The bridge reads its source registry through the public HTTP contract."""

from pathlib import Path

import httpx

from tests.bridge_process import BridgeProcess, advertisement_fixture
from tests.bridge_proxy import BridgeProxy


def test_bridge_registry_revision_tracks_only_registered_identities(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    response = api.get("/api/bridge/pills")
    assert response.status_code == 200
    empty = response.json()
    assert empty["pills"] == []
    assert empty["revision"]
    assert api.get("/api/bridge/pills").json() == empty
    created = api.post("/api/pills", json={"name": "IPA", "mac": "aa-bb-cc-dd-ee-ff"})
    assert created.status_code == 201
    pill = created.json()["pill"]
    registry = api.get("/api/bridge/pills").json()
    assert registry["pills"] == [{"id": pill["id"], "name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}]
    assert registry["revision"] != empty["revision"]
    api.post("/api/fermentations", json={"name": "IPA", "pill_id": pill["id"]}).raise_for_status()
    assert api.get("/api/bridge/pills").json() == registry
    assert api.get("/api/readings/latest").json()["pills"][0]["last_received_at"] is None
    assert api.post("/api/pills", json={"name": "Duplicata", "mac": pill["mac"]}).status_code == 409
    assert api.get("/api/bridge/pills").json() == registry
    api.post("/api/pills", json={"name": "Stout", "mac": "112233445566"}).raise_for_status()
    updated = api.get("/api/bridge/pills").json()
    assert len(updated["pills"]) == 2
    assert updated["revision"] != registry["revision"]
    assert registry["pills"][0] in updated["pills"]


def test_real_bridge_decodes_and_forwards_separate_registered_sources(
    empty_api: httpx.Client, tmp_path: Path
) -> None:
    api = empty_api
    first = api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).json()["pill"]
    second = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    bridge = BridgeProcess(tmp_path, str(api.base_url).rstrip("/"))
    try:
        bridge.wait_message("registry_synced")
        # Public rapt-ble v2 fixture (manufacturer ID 0x4152 removed).
        payload = advertisement_fixture("valid")
        for pill in (first, second):
            bridge.advertise(pill["mac"].lower(), payload)
            bridge.wait_message("reading_forwarded")
        snapshot = api.get("/api/readings/latest").json()
        readings = {pill["id"]: pill["reading"] for pill in snapshot["pills"]}
        for pill in (first, second):
            reading = readings[pill["id"]]
            assert reading["pill_mac"] == pill["mac"]
            assert reading["valid"] is True
            assert reading["gravity_velocity"] == -14.821796417236328
            assert abs(reading["specific_gravity"] - 1.0213) < 0.00005
            assert abs(reading["temperature"] - 19.69) < 0.005
            assert reading["battery"] == 63.2734375
            assert (reading["accel_x"], reading["accel_y"], reading["accel_z"]) == (
                796.5625,
                34.8125,
                665.4375,
            )
            assert reading["timestamp"] > 0
    finally:
        bridge.stop()


def test_real_receiver_isolates_duplicates_and_keeps_invalid_velocity_and_signed_axes(
    empty_api: httpx.Client, tmp_path: Path
) -> None:
    api = empty_api
    pills = [
        api.post("/api/pills", json={"name": name, "mac": mac}).json()["pill"]
        for name, mac in (("IPA", "AA:BB:CC:DD:EE:FF"), ("Stout", "11:22:33:44:55:66"))
    ]
    cycles = [
        api.post("/api/fermentations", json={"name": pill["name"], "pill_id": pill["id"]}).json()[
            "fermentation"
        ]
        for pill in pills
    ]
    bridge = BridgeProcess(tmp_path, str(api.base_url).rstrip("/"))
    try:
        bridge.wait_message("registry_synced")
        for pill in pills:
            bridge.advertise(pill["mac"], advertisement_fixture("valid"))
            bridge.wait_message("reading_forwarded")
        before = api.get("/api/readings/latest").json()["pills"]
        for pill in pills:
            bridge.advertise(pill["mac"], advertisement_fixture("valid"))
            bridge.wait_message("advertisement_duplicate")
        assert api.get("/api/readings/latest").json()["pills"] == before
        bridge.advertise("77:88:99:AA:BB:CC", advertisement_fixture("valid"))
        bridge.wait_message("reason=unregistered")
        # A truncated frame, firmware/HW metadata and unknown data never reuse a previous reading.
        bridge.advertise(pills[0]["mac"], "50540200")
        bridge.wait_message("advertisement_rejected")
        bridge.send_frame({"address": pills[0]["mac"], "manufacturer_data": {"17739": "47313233"}})
        bridge.advertise(pills[0]["mac"], "50546450696c6c4731")
        bridge.advertise(pills[0]["mac"], advertisement_fixture("signed_accelerations"))
        bridge.wait_message("reading_forwarded")
        history = api.get(f"/api/fermentations/{cycles[0]['id']}/readings").json()["readings"]
        assert len(history) == 2
        reading = history[-1]
        assert reading["valid"] is False
        assert reading["gravity_velocity"] == -14.821796417236328
        assert (reading["accel_x"], reading["accel_y"], reading["accel_z"]) == (-1, -2, 3)
        assert abs(reading["temperature"] - 19.69) < 0.005
        assert abs(reading["specific_gravity"] - 1.0213) < 0.00005
        other = api.get(f"/api/fermentations/{cycles[1]['id']}/readings").json()["readings"]
        assert len(other) == 1
        assert other[0]["pill_mac"] == pills[1]["mac"]
        assert len(api.get("/api/pills").json()["pills"]) == 2
    finally:
        bridge.stop()


def test_bridge_registry_failure_is_visible_and_recovers_without_partial_replacement(
    empty_api: httpx.Client, tmp_path: Path
) -> None:
    api = empty_api
    first = api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).json()["pill"]
    proxy = BridgeProxy(str(api.base_url).rstrip("/"))
    proxy.registry_status = 503
    bridge = BridgeProcess(tmp_path, proxy.url)
    try:
        assert "revision=unavailable" in bridge.wait_message("registry_sync_failed")
        bridge.advertise(first["mac"], advertisement_fixture("valid"))
        bridge.wait_message("reason=unregistered")
        assert api.get("/api/readings/latest").json()["reading"] is None
        proxy.registry_status = 200
        bridge.wait_message("registry_synced")
        bridge.advertise(first["mac"], advertisement_fixture("valid"))
        bridge.wait_message("reading_forwarded")
        # A malformed later snapshot must not replace the known-good registry, even partially.
        proxy.registry_response = (
            b'{"revision":"bad","pills":[{"id":"x","name":"New","mac":"112233445566"},{}]}'
        )
        bridge.wait_message("registry_sync_failed")
        second = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
            "pill"
        ]
        bridge.advertise(second["mac"], advertisement_fixture("valid"))
        bridge.wait_message("reason=unregistered")
        bridge.advertise(first["mac"], advertisement_fixture("signed_accelerations"))
        bridge.wait_message("reading_forwarded")
        assert (
            api.get("/api/readings/latest", params={"pill_id": second["id"]}).json()["reading"]
            is None
        )
        assert (
            api.get("/api/readings/latest", params={"pill_id": first["id"]}).json()["reading"][
                "accel_x"
            ]
            == -1
        )
        proxy.registry_response = None
        revision = api.get("/api/bridge/pills").json()["revision"]
        bridge.wait_message(f"registry_synced revision={revision}")
        bridge.advertise(second["mac"], advertisement_fixture("valid"))
        bridge.wait_message("reading_forwarded")
        assert (
            api.get("/api/readings/latest", params={"pill_id": second["id"]}).json()["reading"][
                "pill_mac"
            ]
            == second["mac"]
        )
    finally:
        bridge.stop()
        proxy.stop()


def test_failed_bridge_delivery_is_not_confirmed_or_retried(
    empty_api: httpx.Client, tmp_path: Path
) -> None:
    api = empty_api
    pill = api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).json()["pill"]
    cycle = api.post("/api/fermentations", json={"name": "IPA", "pill_id": pill["id"]}).json()[
        "fermentation"
    ]
    path = f"/api/fermentations/{cycle['id']}/readings"
    proxy = BridgeProxy(str(api.base_url).rstrip("/"))
    bridge = BridgeProcess(tmp_path, proxy.url)
    try:
        bridge.wait_message("registry_synced")
        proxy.telemetry_status = 503
        bridge.advertise(pill["mac"], advertisement_fixture("valid"))
        bridge.wait_message("reading_delivery_failed")
        assert api.get(path).json()["readings"] == []
        assert api.get("/api/readings/latest").json()["reading"] is None
        proxy.telemetry_status = 200
        proxy.telemetry_delay = 1.3
        bridge.advertise(pill["mac"], advertisement_fixture("signed_accelerations"))
        bridge.wait_message("reading_delivery_failed")
        assert api.get(path).json()["readings"] == []
        proxy.telemetry_delay = 0
        bridge.advertise(pill["mac"], advertisement_fixture("invalid_velocity"))
        bridge.wait_message("reading_forwarded")
        history = api.get(path).json()["readings"]
        assert len(history) == 1
        assert history[0]["valid"] is False
        assert history[0]["gravity_velocity"] == 0
        assert abs(history[0]["specific_gravity"] - 1.0109) < 0.00005
        assert len(proxy.deliveries) == 3
        # Finishing the replay drains only queued sends; it does not resend failures.
        assert bridge.process.stdin is not None
        bridge.process.stdin.close()
        assert bridge.process.wait(timeout=5) == 0
        assert len(proxy.deliveries) == 3
        assert len(api.get(path).json()["readings"]) == 1
    finally:
        bridge.stop()
        proxy.stop()

"""Manage the operational registry without rewriting a pillola's history."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import httpx
import pytest

from tests.bridge_process import BridgeProcess, advertisement_fixture
from tests.bridge_proxy import BridgeProxy
from tests.payloads import gateway_lettura


def test_rename_free_pill_updates_registry_and_bridge_but_preserves_history(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    pill = api.post(
        "/api/pills", json={"name": "Pillola originale", "mac": "aa-bb-cc-dd-ee-ff"}
    ).json()["pill"]
    cycle = api.post(
        "/api/fermentations", json={"name": "Prima IPA", "pill_id": pill["id"]}
    ).json()["fermentation"]
    api.post(
        "/telemetry", json=gateway_lettura(timestamp=datetime.now(UTC).timestamp())
    ).raise_for_status()
    readings = api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"]
    assert len(readings) == 1
    diagnostic = api.get("/api/readings/latest").json()["reading"]
    api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
    before = api.get("/api/bridge/pills").json()

    response = api.patch(f"/api/pills/{pill['id']}", json={"name": "  Pillola rinominata  "})

    assert response.status_code == 200
    renamed = response.json()["pill"]
    assert renamed == {**pill, "name": "Pillola rinominata"}
    assert api.get("/api/pills").json()["pills"] == [renamed]
    bridge = api.get("/api/bridge/pills").json()
    assert bridge["revision"] != before["revision"]
    assert bridge["pills"] == [
        {"id": pill["id"], "name": "Pillola rinominata", "mac": "AA:BB:CC:DD:EE:FF"}
    ]
    assert api.get("/api/bridge/pills").json() == bridge
    assert api.get("/api/readings/latest").json()["reading"] == diagnostic
    previous = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
    assert previous["pill_name"] == "Pillola originale"
    assert previous["pill_mac"] == "AA:BB:CC:DD:EE:FF"
    assert api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"] == readings
    next_cycle = api.post("/api/fermentations", json={"name": "Seconda IPA", "pill_id": pill["id"]})
    assert next_cycle.status_code == 201
    assert next_cycle.json()["fermentation"]["pill_name"] == "Pillola rinominata"


def test_remove_free_pill_hides_only_operational_identity_and_rejects_stale_bridge(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    pill = api.post(
        "/api/pills", json={"name": "Pillola storica", "mac": "AA:BB:CC:DD:EE:FF"}
    ).json()["pill"]
    cycle = api.post(
        "/api/fermentations", json={"name": "IPA conservata", "pill_id": pill["id"]}
    ).json()["fermentation"]
    sample = gateway_lettura(timestamp=datetime.now(UTC).timestamp())
    api.post("/telemetry", json=sample).raise_for_status()
    ended = api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"]
    readings = api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"]
    assert len(readings) == 1
    registry = api.get("/api/bridge/pills").json()

    assert api.delete(f"/api/pills/{pill['id']}").status_code == 204

    assert api.get("/api/pills").json() == {"pills": []}
    snapshot = api.get("/api/readings/latest").json()
    assert snapshot["pills"] == []
    assert snapshot["reading"] is None
    assert api.get("/api/readings/latest", params={"pill_id": pill["id"]}).status_code == 404
    updated = api.get("/api/bridge/pills").json()
    assert updated["pills"] == []
    assert updated["revision"] != registry["revision"]
    assert api.post("/telemetry", json={**sample, "specific_gravity": 1080}).status_code == 404
    assert api.get("/api/bridge/pills").json() == updated
    assert api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"] == ended
    assert api.post(f"/api/fermentations/{cycle['id']}/end").json()["fermentation"] == ended
    assert api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"] == readings
    archived = api.get("/api/fermentations", params={"status": "concluded"}).json()
    assert archived["fermentations"][0]["pill_name"] == "Pillola storica"
    assert archived["fermentations"][0]["pill_mac"] == pill["mac"]
    assert (
        api.post("/api/fermentations", json={"name": "Vietata", "pill_id": pill["id"]}).status_code
        == 404
    )
    assert api.delete(f"/api/pills/{pill['id']}").status_code == 404
    assert api.patch(f"/api/pills/{pill['id']}", json={"name": "Vietata"}).status_code == 404
    assert api.get("/api/fermentations/active").json()["fermentations"] == []


def test_explicit_reregistration_restores_one_identity_and_never_reassigns_history(
    empty_api: httpx.Client,
) -> None:
    api = empty_api
    pill = api.post(
        "/api/pills", json={"name": "Etichetta originale", "mac": "AA:BB:CC:DD:EE:FF"}
    ).json()["pill"]
    cycle = api.post(
        "/api/fermentations", json={"name": "Storico prima della rimozione", "pill_id": pill["id"]}
    ).json()["fermentation"]
    api.post(
        "/telemetry", json=gateway_lettura(timestamp=datetime.now(UTC).timestamp())
    ).raise_for_status()
    api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
    readings = api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"]
    assert len(readings) == 1
    diagnostic = api.get("/api/readings/latest").json()["reading"]
    api.delete(f"/api/pills/{pill['id']}").raise_for_status()

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(
                lambda mac: api.post("/api/pills", json={"name": "Nuova etichetta", "mac": mac}),
                ["AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff", "aabbccddeeff"] * 2,
            )
        )
    assert [response.status_code for response in responses].count(201) == 1
    assert [response.status_code for response in responses].count(409) == 5
    restored = next(response for response in responses if response.status_code == 201).json()[
        "pill"
    ]
    assert restored == {**pill, "name": "Nuova etichetta"}
    assert api.get("/api/pills").json()["pills"] == [restored]
    assert api.get("/api/readings/latest").json()["reading"] == diagnostic
    historical = api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"]
    assert historical["pill_id"] == restored["id"]
    assert historical["pill_name"] == "Etichetta originale"
    assert api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"] == readings
    current = api.post(
        "/api/fermentations", json={"name": "Nuovo ciclo", "pill_id": restored["id"]}
    )
    assert current.status_code == 201
    created = current.json()["fermentation"]
    assert created["pill_name"] == "Nuova etichetta"
    assert api.get(f"/api/fermentations/{created['id']}/readings").json()["readings"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": 42},
        {"name": None},
        {"name": "Nuova", "mac": "11:22:33:44:55:66"},
        {"name": "Nuova", "archived": False},
    ],
)
def test_invalid_rename_never_changes_identity_or_bridge(
    api: httpx.Client, payload: dict[str, object]
) -> None:
    before = api.get("/api/pills").json()
    pill = before["pills"][0]
    bridge = api.get("/api/bridge/pills").json()
    assert api.patch(f"/api/pills/{pill['id']}", json=payload).status_code == 422
    assert api.get("/api/pills").json() == before
    assert api.get("/api/bridge/pills").json() == bridge


def test_busy_pill_rejects_registry_changes_until_cycle_ends(api: httpx.Client) -> None:
    pill = api.get("/api/pills").json()["pills"][0]
    cycle = api.post(
        "/api/fermentations", json={"name": "IPA attiva", "pill_id": pill["id"]}
    ).json()["fermentation"]
    bridge = api.get("/api/bridge/pills").json()
    for response in (
        api.patch(f"/api/pills/{pill['id']}", json={"name": "Vietata"}),
        api.delete(f"/api/pills/{pill['id']}"),
    ):
        assert response.status_code == 409
        assert "fermentazione attiva" in response.json()["detail"]
    assert api.get("/api/pills").json()["pills"] == [
        {**pill, "available": False, "active_fermentation_id": cycle["id"]}
    ]
    assert api.get("/api/bridge/pills").json() == bridge
    assert api.get(f"/api/fermentations/{cycle['id']}").json()["fermentation"] == cycle
    api.post(
        "/telemetry", json=gateway_lettura(timestamp=datetime.now(UTC).timestamp())
    ).raise_for_status()
    assert len(api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"]) == 1
    api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()
    assert api.patch(f"/api/pills/{pill['id']}", json={"name": "Ora libera"}).status_code == 200
    assert api.delete(f"/api/pills/{pill['id']}").status_code == 204
    assert api.patch("/api/pills/unknown", json={"name": "Assente"}).status_code == 404
    assert api.delete("/api/pills/unknown").status_code == 404


@pytest.mark.parametrize("change", ["rename", "remove"])
def test_registry_changes_and_start_serialize_without_losing_a_source(
    empty_api: httpx.Client, change: str
) -> None:
    api = empty_api
    for attempt in range(12):
        pill = api.post(
            "/api/pills", json={"name": "Nome originale", "mac": f"02:00:00:00:00:{attempt:02X}"}
        ).json()["pill"]
        barrier = Barrier(2)

        def start(identifier: str, gate: Barrier) -> httpx.Response:
            gate.wait(timeout=10)
            return api.post(
                "/api/fermentations", json={"name": "IPA concorrente", "pill_id": identifier}
            )

        def mutate(identifier: str, gate: Barrier) -> httpx.Response:
            gate.wait(timeout=10)
            if change == "rename":
                return api.patch(f"/api/pills/{identifier}", json={"name": "Nome aggiornato"})
            return api.delete(f"/api/pills/{identifier}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            starting, changing = (
                pool.submit(start, pill["id"], barrier),
                pool.submit(mutate, pill["id"], barrier),
            )
            created, changed = starting.result(timeout=15), changing.result(timeout=15)
        registry = api.get("/api/pills").json()["pills"]
        current = next((entry for entry in registry if entry["id"] == pill["id"]), None)
        if change == "remove" and changed.status_code == 204:
            assert created.status_code == 404
            assert current is None
            assert all(
                cycle["pill_id"] != pill["id"]
                for cycle in api.get("/api/fermentations/active").json()["fermentations"]
            )
            assert (
                api.post("/telemetry", json=gateway_lettura(pill_mac=pill["mac"])).status_code
                == 404
            )
        else:
            assert created.status_code == 201
            cycle = created.json()["fermentation"]
            assert current is not None
            assert current["available"] is False
            assert current["active_fermentation_id"] == cycle["id"]
            if change == "rename" and changed.status_code == 200:
                assert cycle["pill_name"] == "Nome aggiornato"
                assert current["name"] == "Nome aggiornato"
            else:
                assert changed.status_code == 409
                assert cycle["pill_name"] == "Nome originale"
                assert current["name"] == "Nome originale"
            assert cycle["pill_mac"] == pill["mac"]
            api.post(
                "/telemetry",
                json=gateway_lettura(pill_mac=pill["mac"], timestamp=datetime.now(UTC).timestamp()),
            ).raise_for_status()
            assert (
                len(api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"]) == 1
            )
            api.post(f"/api/fermentations/{cycle['id']}/end").raise_for_status()


def test_real_bridge_updates_names_and_cannot_revive_a_removed_cached_source(
    empty_api: httpx.Client, tmp_path: Path
) -> None:
    api = empty_api
    pill = api.post(
        "/api/pills", json={"name": "Nome iniziale", "mac": "AA:BB:CC:DD:EE:FF"}
    ).json()["pill"]
    initial = api.get("/api/bridge/pills").json()
    proxy = BridgeProxy(str(api.base_url).rstrip("/"))
    bridge = BridgeProcess(tmp_path, proxy.url)
    try:
        bridge.wait_message(f"registry_synced revision={initial['revision']}")
        api.patch(f"/api/pills/{pill['id']}", json={"name": "Nome aggiornato"}).raise_for_status()
        renamed = api.get("/api/bridge/pills").json()
        assert renamed["pills"] == [
            {"id": pill["id"], "name": "Nome aggiornato", "mac": pill["mac"]}
        ]
        assert renamed["revision"] != initial["revision"]
        bridge.wait_message(f"registry_synced revision={renamed['revision']}")
        # A failed completed poll proves that the real bridge keeps its old list.
        proxy.registry_status = 503
        bridge.wait_message("registry_sync_failed")
        assert api.delete(f"/api/pills/{pill['id']}").status_code == 204
        bridge.advertise(pill["mac"], advertisement_fixture("valid"))
        bridge.wait_message("reading_delivery_failed")
        assert api.get("/api/pills").json()["pills"] == []
        assert api.get("/api/readings/latest").json()["reading"] is None
        removed = api.get("/api/bridge/pills").json()
        assert removed["pills"] == []
        proxy.registry_status = 200
        bridge.wait_message(f"registry_synced revision={removed['revision']}")
        bridge.advertise(pill["mac"], advertisement_fixture("signed_accelerations"))
        bridge.wait_message("reason=unregistered")
        assert api.get("/api/bridge/pills").json() == removed
    finally:
        bridge.stop()
        proxy.stop()

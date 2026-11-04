from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
import pytest

from tests.integration.test_live_readings import next_snapshot
from tests.payloads import gateway_lettura


@pytest.fixture
def api(empty_api: httpx.Client) -> httpx.Client:
    return empty_api


def test_register_pillola_and_reject_equivalent_bluetooth_mac(api: httpx.Client) -> None:
    assert api.get("/api/pills").json() == {"pills": []}
    response = api.post("/api/pills", json={"name": "  Pillola IPA  ", "mac": "aa-bb-cc-dd-ee-ff"})
    assert response.status_code == 201
    pill = response.json()["pill"]
    assert pill["id"]
    assert pill["name"] == "Pillola IPA"
    assert pill["mac"] == "AA:BB:CC:DD:EE:FF"
    assert api.get("/api/pills").json() == {"pills": [pill]}
    duplicate = api.post("/api/pills", json={"name": "Duplicata", "mac": "aabbccddeeff"})
    assert duplicate.status_code == 409
    assert api.get("/api/pills").json() == {"pills": [pill]}


def test_each_pillola_keeps_its_measurements_and_latest_contact(api: httpx.Client) -> None:
    first = api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).json()["pill"]
    second = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    payload = gateway_lettura(
        pill_mac="aa-bb-cc-dd-ee-ff",
        valid=False,
        gravity_velocity=-2.5,
        accel_x=-0.25,
        accel_y=1.5,
        accel_z=0.75,
    )
    submitted = api.post("/telemetry", json=payload)
    assert submitted.status_code == 200
    reading = submitted.json()["reading"]
    assert reading["pill_id"] == first["id"]
    assert reading["pill_mac"] == first["mac"]
    assert reading["specific_gravity"] == 1.050125
    assert reading["valid"] is False
    assert reading["gravity_velocity"] == -2.5
    assert (reading["accel_x"], reading["accel_y"], reading["accel_z"]) == (-0.25, 1.5, 0.75)
    other = api.post("/telemetry", json={**payload, "pill_mac": second["mac"]})
    assert other.status_code == 200
    assert other.json()["reading"]["pill_id"] == second["id"]
    snapshot = api.get("/api/readings/latest", params={"pill_id": first["id"]}).json()
    assert snapshot["reading"] == reading
    first_contact = snapshot["pills"][0]["last_received_at"]
    assert api.post("/telemetry", json=payload).json()["reading"] == reading
    updated = api.get("/api/readings/latest", params={"pill_id": first["id"]}).json()
    assert updated["pills"][0]["last_received_at"] > first_contact
    assert updated["reading"]["received_at"] == reading["received_at"]


def test_fermentazione_requires_a_pillola_and_keeps_its_complete_samples(
    api: httpx.Client,
) -> None:
    assert api.post("/api/fermentations", json={"name": "Senza pillola"}).status_code == 422
    first = api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).json()["pill"]
    other = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    created = api.post("/api/fermentations", json={"name": "IPA", "pill_id": first["id"]})
    assert created.status_code == 201
    fermentation = created.json()["fermentation"]
    assert fermentation["pill_id"] == first["id"]
    timestamp = datetime.fromisoformat(fermentation["started_at"]).timestamp() + 0.000123
    path = f"/api/fermentations/{fermentation['id']}/readings"
    foreign = gateway_lettura(timestamp=timestamp, pill_mac=other["mac"])
    assert api.post("/telemetry", json=foreign).status_code == 200
    assert api.get(path).json()["readings"] == []
    sample = gateway_lettura(timestamp=timestamp, pill_mac=first["mac"])
    assert api.post("/telemetry", json=sample).status_code == 200
    changed = {**sample, "accel_x": -0.75, "gravity_velocity": -1.25, "valid": True}
    for _ in range(3):
        assert api.post("/telemetry", json=changed).status_code == 200
    history = api.get(path).json()["readings"]
    assert len(history) == 2
    assert history[1]["accel_x"] == -0.75
    assert history[1]["gravity_velocity"] == -1.25
    assert history[1]["valid"] is True
    assert all(reading["pill_id"] == first["id"] for reading in history)


@pytest.mark.parametrize(
    "registration",
    [
        {"name": "", "mac": "AA:BB:CC:DD:EE:FF"},
        {"name": "   ", "mac": "AA:BB:CC:DD:EE:FF"},
        {"name": 42, "mac": "AA:BB:CC:DD:EE:FF"},
        {"name": "IPA", "mac": "AA:BB-CC:DD:EE:FF"},
        {"name": "IPA", "mac": "AA:BB:CC:DD:EE"},
        {"name": "IPA", "mac": "GG:BB:CC:DD:EE:FF"},
        {"name": "IPA", "mac": True},
        {"name": "IPA"},
    ],
)
def test_invalid_registration_does_not_create_a_pillola(
    api: httpx.Client, registration: dict[str, object]
) -> None:
    assert api.post("/api/pills", json=registration).status_code == 422
    assert api.get("/api/pills").json()["pills"] == []


def test_concurrent_equivalent_registration_creates_one_pillola(api: httpx.Client) -> None:
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(
                lambda mac: api.post("/api/pills", json={"name": "IPA", "mac": mac}),
                ["AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff", "aabbccddeeff"] * 2,
            )
        )
    assert [response.status_code for response in responses].count(201) == 1
    assert [response.status_code for response in responses].count(409) == 5
    assert len(api.get("/api/pills").json()["pills"]) == 1


@pytest.mark.parametrize("source", [None, "unknown", "11:22:33:44:55:66", True])
def test_rejected_source_does_not_renew_contact_or_modify_readings(
    api: httpx.Client, source: object
) -> None:
    api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).raise_for_status()
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
    before = api.get("/api/readings/latest").json()["pills"]
    payload = gateway_lettura(pill_mac=source)
    if source is None:
        del payload["pill_mac"]
    response = api.post("/telemetry", json=payload)
    assert response.status_code == (404 if source == "11:22:33:44:55:66" else 422)
    assert api.get("/api/readings/latest").json()["pills"] == before
    assert api.get("/api/readings/latest", params={"pill_id": "unknown"}).status_code == 404


def test_live_stream_updates_other_pillola_without_replacing_selected_one(
    api: httpx.Client,
) -> None:
    first = api.post("/api/pills", json={"name": "IPA", "mac": "AA:BB:CC:DD:EE:FF"}).json()["pill"]
    other = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    with api.stream("GET", "/api/readings/events") as response:
        events = response.iter_lines()
        assert len(next_snapshot(events)["pills"]) == 2
        assert (
            api.post("/telemetry", json=gateway_lettura(pill_mac=first["mac"])).status_code == 200
        )
        original = next_snapshot(events)
        assert (
            api.post("/telemetry", json=gateway_lettura(pill_mac=other["mac"])).status_code == 200
        )
        updated = next_snapshot(events)
        assert updated["reading"] == original["reading"]
        assert updated["pills"][1]["reading"]["pill_id"] == other["id"]


def test_unknown_pillola_cannot_start_a_fermentazione(api: httpx.Client) -> None:
    response = api.post("/api/fermentations", json={"name": "IPA", "pill_id": "unknown"})
    assert response.status_code == 404
    assert api.get("/api/fermentations/active").json()["fermentation"] is None

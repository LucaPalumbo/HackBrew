from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
import pytest

from tests.payloads import fermentation_payload, gateway_lettura


def test_identical_delivery_keeps_one_original_lettura(api: httpx.Client) -> None:
    fermentation = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA affidabile")
    ).json()["fermentation"]
    timestamp = datetime.fromisoformat(fermentation["started_at"]).timestamp() + 0.000123
    payload = gateway_lettura(timestamp=timestamp)
    first = api.post("/telemetry", json=payload)
    assert first.status_code == 200
    path = f"/api/fermentations/{fermentation['id']}/readings"
    original = api.get(path).json()["readings"]
    assert len(original) == 1

    for _ in range(3):
        response = api.post("/telemetry", json=payload)
        assert response.status_code == 200
        assert response.json() == first.json()
    assert api.get(path).json()["readings"] == original


def test_concurrent_duplicate_deliveries_persist_one_sample(api: httpx.Client) -> None:
    fermentation = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA concorrente")
    ).json()["fermentation"]
    timestamp = datetime.fromisoformat(fermentation["started_at"]).timestamp() + 0.000123
    payload = gateway_lettura(timestamp=timestamp)
    with ThreadPoolExecutor(max_workers=12) as pool:
        responses = list(pool.map(lambda _: api.post("/telemetry", json=payload), range(24)))
    assert all(response.status_code == 200 for response in responses)
    history = api.get(f"/api/fermentations/{fermentation['id']}/readings").json()["readings"]
    assert len(history) == 1
    assert history[0]["timestamp"] == timestamp
    assert history[0]["specific_gravity"] == 1.050125
    assert api.get("/api/readings/latest").json()["reading"]["timestamp"] == timestamp


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("specific_gravity", 1050.126, 1.050126),
        ("temperature", 19.6875001, 19.6875001),
        ("battery", 63.2734381, 63.2734381),
        ("gravity_velocity", -2.5, -2.5),
        ("accel_x", -0.5, -0.5),
        ("accel_y", 0.25, 0.25),
        ("accel_z", 0.75, 0.75),
        ("valid", True, True),
    ],
)
def test_distinct_measurements_at_same_acquisition_are_not_merged(
    api: httpx.Client, field: str, value: object, expected: object
) -> None:
    fermentation = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA precisa")
    ).json()["fermentation"]
    timestamp = datetime.fromisoformat(fermentation["started_at"]).timestamp() + 0.000123
    assert api.post("/telemetry", json=gateway_lettura(timestamp=timestamp)).status_code == 200
    changed = gateway_lettura(timestamp=timestamp, **{field: value})
    assert api.post("/telemetry", json=changed).status_code == 200
    history = api.get(f"/api/fermentations/{fermentation['id']}/readings").json()["readings"]
    assert len(history) == 2
    assert history[-1][field] == expected
    assert api.get("/api/readings/latest").json()["fermentation_reading"] == history[-1]
    assert api.post("/telemetry", json=changed).status_code == 200
    assert (
        api.get(f"/api/fermentations/{fermentation['id']}/readings").json()["readings"] == history
    )


def test_delayed_letture_and_boundaries_keep_successive_fermentazioni_separate(
    api: httpx.Client,
) -> None:
    first = api.post("/api/fermentations", json=fermentation_payload(api, "Prima IPA")).json()[
        "fermentation"
    ]
    first_start = datetime.fromisoformat(first["started_at"]).timestamp()
    ended = api.post(f"/api/fermentations/{first['id']}/end").json()["fermentation"]
    first_end = datetime.fromisoformat(ended["ended_at"]).timestamp()
    second = api.post("/api/fermentations", json=fermentation_payload(api, "Seconda IPA")).json()[
        "fermentation"
    ]
    second_start = datetime.fromisoformat(second["started_at"]).timestamp()
    assert first_start + 0.000123 < first_end < second_start
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=second_start + 0.000123, specific_gravity=1040),
        ).status_code
        == 200
    )
    latest = api.get("/api/readings/latest").json()["reading"]

    for timestamp, gravity in [
        (first_start + 0.000123, 1070),
        (first_start, 1060),
        (first_end, 1080),
        (first_start - 0.000001, 1090),
    ]:
        for _ in range(2):
            assert (
                api.post(
                    "/telemetry",
                    json=gateway_lettura(timestamp=timestamp, specific_gravity=gravity),
                ).status_code
                == 200
            )
    first_path = f"/api/fermentations/{first['id']}/readings"
    second_path = f"/api/fermentations/{second['id']}/readings"
    history = api.get(first_path).json()["readings"]
    assert [reading["specific_gravity"] for reading in history] == [1.060, 1.070]
    assert len(api.get(second_path).json()["readings"]) == 1
    assert api.get("/api/readings/latest").json()["reading"] == latest
    assert (
        api.get("/api/readings/latest").json()["fermentation_reading"]["specific_gravity"] == 1.040
    )

    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=second_start, specific_gravity=1050)
        ).status_code
        == 200
    )
    second_history = api.get(second_path).json()["readings"]
    assert [reading["specific_gravity"] for reading in second_history] == [1.050, 1.040]
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=second_start + 0.000124, battery=101)
        ).status_code
        == 422
    )
    assert api.get(second_path).json()["readings"] == second_history
    assert api.get("/api/readings/latest").json()["reading"] == latest

    ended = api.post(f"/api/fermentations/{second['id']}/end").json()["fermentation"]
    second_end = datetime.fromisoformat(ended["ended_at"]).timestamp()
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=second_end, specific_gravity=1030)
        ).status_code
        == 200
    )
    assert api.get("/api/readings/latest").json()["reading"]["specific_gravity"] == 1.030
    assert api.get(first_path).json()["readings"] == history
    assert api.get(second_path).json()["readings"] == second_history

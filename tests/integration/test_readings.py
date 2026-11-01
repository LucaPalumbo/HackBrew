import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tests.payloads import gateway_lettura


def test_no_lettura_is_reported_explicitly_before_first_message(api: httpx.Client) -> None:
    response = api.get("/api/readings/latest")

    assert response.status_code == 200
    assert response.json() == {"reading": None}


def test_gateway_lettura_is_retrievable_in_agreed_units_with_fractional_timestamp(
    api: httpx.Client,
) -> None:
    before = datetime.now(UTC)
    submitted = api.post("/telemetry", json=gateway_lettura())

    assert submitted.status_code == 200
    fetched = api.get("/api/readings/latest")
    assert fetched.status_code == 200
    reading = fetched.json()["reading"]
    assert reading["specific_gravity"] == 1.050125
    assert reading["temperature"] == 19.6875
    assert reading["battery"] == 63.2734375
    assert reading["timestamp"] == 1700000000.123456
    assert reading["received_at"]
    received_at = datetime.fromisoformat(reading["received_at"])
    assert before - timedelta(seconds=1) <= received_at <= datetime.now(UTC)
    assert submitted.json()["reading"] == reading


@pytest.mark.parametrize(
    "changes",
    [
        {"battery": -1},
        {"battery": 101},
        {"temperature": "warm"},
        {"temperature": float("nan")},
        {"specific_gravity": float("inf")},
        {"timestamp": float("-inf")},
        {"timestamp": 1e300},
        {"timestamp": -1},
        {"temperature": True},
        {"battery": "63.0"},
        {"specific_gravity": 0},
        {"temperature": -300},
        {"accel_x": float("nan")},
    ],
)
def test_invalid_lettura_does_not_replace_good_measurements(
    api: httpx.Client, changes: dict[str, object]
) -> None:
    baseline = api.post("/telemetry", json=gateway_lettura()).json()

    response = api.post(
        "/telemetry",
        content=json.dumps(gateway_lettura(**changes)),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]
    assert api.get("/api/readings/latest").json() == baseline


@pytest.mark.parametrize("timestamp", [1700000000.123455, 1700000000.123456])
def test_older_or_repeated_lettura_cannot_replace_latest(
    api: httpx.Client, timestamp: float
) -> None:
    baseline = api.post("/telemetry", json=gateway_lettura()).json()

    response = api.post(
        "/telemetry", json=gateway_lettura(timestamp=timestamp, specific_gravity=1090)
    )

    assert response.status_code == 200
    assert response.json() == baseline
    assert api.get("/api/readings/latest").json() == baseline


def test_concurrent_letture_leave_the_newest_measurement_visible(api: httpx.Client) -> None:
    payloads = [
        gateway_lettura(timestamp=1700000000.123456 + order, specific_gravity=1050 + order)
        for order in [4, 1, 3, 0, 2]
    ]
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(lambda payload: api.post("/telemetry", json=payload), payloads))

    assert all(response.status_code == 200 for response in responses)
    reading = api.get("/api/readings/latest").json()["reading"]
    assert reading["timestamp"] == 1700000004.123456
    assert reading["specific_gravity"] == 1.054


@pytest.mark.parametrize("field", ["temperature", "specific_gravity", "battery", "timestamp"])
def test_missing_required_measurement_is_rejected(api: httpx.Client, field: str) -> None:
    payload = gateway_lettura()
    del payload[field]

    response = api.post("/telemetry", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]
    assert api.get("/api/readings/latest").json() == {"reading": None}


@pytest.mark.parametrize("body", ["{broken", "null", "[]"])
def test_malformed_or_non_object_message_is_rejected(api: httpx.Client, body: str) -> None:
    response = api.post("/telemetry", content=body, headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    assert response.json()["detail"]
    assert api.get("/api/readings/latest").json() == {"reading": None}

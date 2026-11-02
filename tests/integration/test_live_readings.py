import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from tests.payloads import gateway_lettura


def next_snapshot(lines: Iterator[str]) -> dict[str, Any]:
    for line in lines:
        if line.startswith("data:"):
            return cast(dict[str, Any], json.loads(line.removeprefix("data:").strip()))
    raise AssertionError("The event stream ended without a snapshot")


def test_live_stream_starts_with_persisted_state_and_delivers_new_letture(
    api: httpx.Client,
) -> None:
    with api.stream("GET", "/api/readings/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = response.iter_lines()
        assert next_snapshot(lines)["reading"] is None

        assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
        event = next_snapshot(lines)
        assert event["reading"]["specific_gravity"] == 1.050125
        assert event["reading"]["timestamp"] == 1700000000.123456
        saved = api.get("/api/readings/latest").json()["reading"]
        assert datetime.fromisoformat(saved.pop("received_at")) == datetime.fromisoformat(
            event["reading"].pop("received_at")
        )
        assert saved == event["reading"]


def test_snapshot_includes_configured_freshness_and_server_time(api: httpx.Client) -> None:
    before = datetime.now(UTC).timestamp()
    with api.stream("GET", "/api/readings/events") as response:
        snapshot = next_snapshot(response.iter_lines())
        assert snapshot["freshness_seconds"] == 60
        assert before <= snapshot["server_time"] <= datetime.now(UTC).timestamp()


def test_reconnected_stream_sends_current_saved_lettura_even_with_last_event_id(
    api: httpx.Client,
) -> None:
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
    with api.stream("GET", "/api/readings/events") as response:
        assert next_snapshot(response.iter_lines())["reading"]["specific_gravity"] == 1.050125

    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(timestamp=1700000001.123456, specific_gravity=1040.125),
        ).status_code
        == 200
    )
    with api.stream(
        "GET", "/api/readings/events", headers={"Last-Event-ID": "missed-notification"}
    ) as response:
        snapshot = next_snapshot(response.iter_lines())
        assert snapshot["reading"]["specific_gravity"] == 1.040125
        assert snapshot["reading"]["timestamp"] == 1700000001.123456

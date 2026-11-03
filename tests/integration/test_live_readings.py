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


def test_late_sample_notifies_history_without_replacing_latest_values(api: httpx.Client) -> None:
    fermentation = api.post("/api/fermentations", json={"name": "IPA fuori ordine"}).json()[
        "fermentation"
    ]
    start = datetime.fromisoformat(fermentation["started_at"]).timestamp()
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=start + 0.000124, specific_gravity=1040)
        ).status_code
        == 200
    )
    with api.stream("GET", "/api/readings/events") as response:
        lines = response.iter_lines()
        original = next_snapshot(lines)
        assert original["fermentation_reading_count"] == 1
        assert (
            api.post(
                "/telemetry",
                json=gateway_lettura(timestamp=start + 0.000123, specific_gravity=1050),
            ).status_code
            == 200
        )
        updated = next_snapshot(lines)
        assert updated["fermentation_reading_count"] == 2
        assert updated["reading"] == original["reading"]
        assert updated["fermentation_reading"] == original["fermentation_reading"]


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


def test_live_snapshot_tracks_fermentazione_and_its_own_latest_lettura(api: httpx.Client) -> None:
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
    with api.stream("GET", "/api/readings/events") as response:
        lines = response.iter_lines()
        initial = next_snapshot(lines)
        assert initial["fermentation"] is None
        assert initial["fermentation_reading"] is None
        started = api.post("/api/fermentations", json={"name": "IPA live"}).json()["fermentation"]
        snapshot = next_snapshot(lines)
        assert snapshot["fermentation"]["id"] == started["id"]
        assert snapshot["fermentation"]["name"] == "IPA live"
        assert snapshot["fermentation_reading"] is None
        assert api.get("/api/readings/latest").json()["fermentation"]["id"] == started["id"]

        timestamp = datetime.fromisoformat(started["started_at"]).timestamp() + 0.000001
        assert (
            api.post(
                "/telemetry", json=gateway_lettura(timestamp=timestamp, specific_gravity=1040.125)
            ).status_code
            == 200
        )
        snapshot = next_snapshot(lines)
        assert snapshot["fermentation_reading"]["specific_gravity"] == 1.040125
        assert snapshot["fermentation_reading"]["timestamp"] == timestamp

        assert api.post(f"/api/fermentations/{started['id']}/end").status_code == 200
        snapshot = next_snapshot(lines)
        assert snapshot["fermentation"] is None
        assert snapshot["fermentation_reading"] is None
        assert snapshot["reading"]["specific_gravity"] == 1.040125

from datetime import datetime

import httpx
import pytest

from tests.payloads import fermentation_payload, gateway_lettura


def test_explicit_interval_filters_pages_without_losing_equal_timestamps(api: httpx.Client) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Intervallo")).json()[
        "fermentation"
    ]
    start = datetime.fromisoformat(cycle["started_at"]).timestamp()
    for offset in (1, 2, 3):
        api.post("/telemetry", json=gateway_lettura(timestamp=start + offset)).raise_for_status()
    path = f"/api/fermentations/{cycle['id']}/readings"
    response = api.get(path, params={"from_timestamp": start + 2, "to_timestamp": start + 3})
    assert [r["timestamp"] for r in response.json()["readings"]] == [start + 2, start + 3]
    api.post(
        "/telemetry", json=gateway_lettura(timestamp=start + 2, specific_gravity=1040.123456)
    ).raise_for_status()
    found = []
    cursor = None
    while True:
        query = {"from_timestamp": str(start + 2), "to_timestamp": str(start + 3), "limit": "1"}
        if cursor:
            query["before"] = cursor
        page = api.get(path, params=query).json()
        found.extend(page["readings"])
        cursor = page["next_before"]
        if cursor is None:
            break
    assert len(found) == 3
    assert sorted(r["specific_gravity"] for r in found) == pytest.approx(
        [1.040123456, 1.050125, 1.050125], rel=0, abs=1e-12
    )
    for params in (
        {"from_timestamp": start + 4, "to_timestamp": start},
        {"from_timestamp": "nan"},
        {"to_timestamp": -1},
    ):
        assert api.get(path, params=params).status_code == 422

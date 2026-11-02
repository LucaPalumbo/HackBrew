from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tests.fermentations import assert_single_concurrent_start
from tests.payloads import gateway_lettura


def test_named_fermentazione_starts_and_is_recovered_from_the_api(api: httpx.Client) -> None:
    assert api.get("/api/fermentations/active").json() == {"fermentation": None}
    before = datetime.now(UTC)
    response = api.post("/api/fermentations", json={"name": "  Prima IPA  "})

    assert response.status_code == 201
    fermentation = response.json()["fermentation"]
    assert fermentation["id"]
    assert fermentation["name"] == "Prima IPA"
    assert fermentation["status"] == "active"
    assert fermentation["ended_at"] is None
    assert (
        before - timedelta(milliseconds=1)
        <= datetime.fromisoformat(fermentation["started_at"])
        <= datetime.now(UTC)
    )
    assert api.get("/api/fermentations/active").json()["fermentation"] == fermentation


def test_concurrent_starts_preserve_exactly_one_active_fermentazione(api: httpx.Client) -> None:
    winner = assert_single_concurrent_start(api)
    repeated = api.post("/api/fermentations", json={"name": "Un'altra IPA"})
    assert repeated.status_code == 409
    assert "attiva" in repeated.json()["detail"]
    assert api.get("/api/fermentations/active").json()["fermentation"] == winner


def test_ending_preserves_fermentazione_and_frees_the_active_slot(api: httpx.Client) -> None:
    first = api.post("/api/fermentations", json={"name": "Prima IPA"}).json()["fermentation"]
    response = api.post(f"/api/fermentations/{first['id']}/end")

    assert response.status_code == 200
    ended = response.json()["fermentation"]
    assert ended["id"] == first["id"]
    assert ended["name"] == "Prima IPA"
    assert ended["started_at"] == first["started_at"]
    assert ended["status"] == "concluded"
    assert datetime.fromisoformat(ended["ended_at"]) >= datetime.fromisoformat(first["started_at"])
    assert api.get("/api/fermentations/active").json()["fermentation"] is None
    assert api.get(f"/api/fermentations/{first['id']}").json()["fermentation"] == ended
    assert api.post(f"/api/fermentations/{first['id']}/end").status_code == 409
    assert api.get(f"/api/fermentations/{first['id']}").json()["fermentation"] == ended

    response = api.post("/api/fermentations", json={"name": "Seconda IPA"})
    assert response.status_code == 201
    assert response.json()["fermentation"]["id"] != first["id"]


def test_letture_belong_only_to_their_monitoring_interval(api: httpx.Client) -> None:
    assert api.post("/telemetry", json=gateway_lettura()).status_code == 200
    first = api.post("/api/fermentations", json={"name": "Prima IPA"}).json()["fermentation"]
    path = f"/api/fermentations/{first['id']}/readings"
    assert api.get(path).json() == {"readings": []}
    started_at = datetime.fromisoformat(first["started_at"]).timestamp()
    assert (
        api.post("/telemetry", json=gateway_lettura(timestamp=started_at - 0.001)).status_code
        == 200
    )
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=started_at, specific_gravity=1040.125)
        ).status_code
        == 200
    )
    collected = api.get(path).json()["readings"]
    assert len(collected) == 1
    assert collected[0]["timestamp"] == started_at
    assert collected[0]["specific_gravity"] == 1.040125
    assert collected[0]["temperature"] == 19.6875
    assert collected[0]["battery"] == 63.2734375
    assert collected[0]["received_at"]

    ended = api.post(f"/api/fermentations/{first['id']}/end").json()["fermentation"]
    ended_at = datetime.fromisoformat(ended["ended_at"]).timestamp()
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=ended_at, specific_gravity=1030.125)
        ).status_code
        == 200
    )
    assert api.get(path).json()["readings"] == collected
    assert api.get("/api/readings/latest").json()["reading"]["specific_gravity"] == 1.030125

    second = api.post("/api/fermentations", json={"name": "Seconda IPA"}).json()["fermentation"]
    assert api.get(f"/api/fermentations/{second['id']}/readings").json() == {"readings": []}
    assert api.get(path).json()["readings"] == collected


@pytest.mark.parametrize("name", ["", "   ", None, 42])
def test_invalid_name_does_not_start_a_fermentazione(api: httpx.Client, name: object) -> None:
    response = api.post("/api/fermentations", json={"name": name})
    assert response.status_code == 422
    assert response.json()["detail"]
    assert api.get("/api/fermentations/active").json()["fermentation"] is None


def test_unknown_fermentazione_cannot_be_ended_or_read(api: httpx.Client) -> None:
    assert api.post("/api/fermentations/unknown/end").status_code == 404
    assert api.get("/api/fermentations/unknown").status_code == 404
    assert api.get("/api/fermentations/unknown/readings").status_code == 404

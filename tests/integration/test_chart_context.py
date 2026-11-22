"""Public chart context never changes ordinary historical pages."""

from datetime import UTC, datetime

import httpx

from tests.payloads import fermentation_payload, gateway_lettura


def test_context_finds_nearest_usable_original_per_series(api: httpx.Client) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Contesto")).json()[
        "fermentation"
    ]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp() + 1
    for offset in (0, 10, 20, 30, 40):
        payload = gateway_lettura(
            timestamp=base + offset, valid=True, gravity_velocity=-offset, accel_x=offset
        )
        if offset in (10, 30):
            payload.pop("accel_x")
            payload["valid"] = False
        api.post("/telemetry", json=payload).raise_for_status()
    path = f"/api/fermentations/{cycle['id']}"
    params = {"from_timestamp": base + 15, "to_timestamp": base + 25}
    ordinary = api.get(path + "/readings", params=params).json()
    response = api.get(path + "/chart-context", params=params)
    assert response.status_code == 200
    context = response.json()["context"]
    assert context["temperature"]["before"]["timestamp"] == base + 10
    assert context["temperature"]["after"]["timestamp"] == base + 30
    for key in ("accel_x", "gravity_velocity"):
        assert context[key]["before"]["timestamp"] == base
        assert context[key]["after"]["timestamp"] == base + 40
    assert context["gravity_velocity"]["after"]["gravity_velocity"] == -40
    assert api.get(path + "/readings", params=params).json() == ordinary
    assert len(ordinary["readings"]) == 1
    assert len(api.get(path + "/readings").json()["readings"]) == 5


def test_context_handles_equal_timestamps_and_empty_windows_without_changing_pages(
    api: httpx.Client,
) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Stesso istante")).json()[
        "fermentation"
    ]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp() + 1
    for offset, battery in ((10, 10), (10, 20), (20, 30), (30, 50), (30, 60)):
        payload = gateway_lettura(timestamp=base + offset, battery=battery)
        for field in ("accel_x", "accel_y", "accel_z", "gravity_velocity", "valid"):
            payload.pop(field)
        api.post("/telemetry", json=payload).raise_for_status()
    path = f"/api/fermentations/{cycle['id']}"
    history = api.get(path + "/readings").json()["readings"]
    params = {"from_timestamp": base + 20, "to_timestamp": base + 20}
    context = api.get(path + "/chart-context", params=params).json()["context"]
    assert context["battery"]["before"] == history[1]
    assert context["battery"]["before"]["battery"] == 20
    assert context["battery"]["after"] == history[3]
    assert context["battery"]["after"]["battery"] == 50
    assert context["accel_x"] == {"before": None, "after": None}
    assert context["gravity_velocity"] == {"before": None, "after": None}
    assert len(api.get(path + "/readings", params=params).json()["readings"]) == 1
    before = api.get(
        path + "/chart-context", params={"from_timestamp": 0, "to_timestamp": base}
    ).json()["context"]
    assert before["battery"]["before"] is None
    assert before["battery"]["after"] == history[0]
    after = api.get(
        path + "/chart-context", params={"from_timestamp": base + 40, "to_timestamp": base + 50}
    ).json()["context"]
    assert after["battery"]["before"] == history[-1]
    assert after["battery"]["after"] is None
    assert api.get(path + "/readings", params={"limit": 1}).json()["readings"] == [history[-1]]


def test_context_is_isolated_from_other_pills_and_later_cycles(api: httpx.Client) -> None:
    first = api.post("/api/fermentations", json=fermentation_payload(api, "Prima birra")).json()[
        "fermentation"
    ]
    timestamp = datetime.now(UTC).timestamp()
    api.post("/telemetry", json=gateway_lettura(timestamp=timestamp, accel_x=-2)).raise_for_status()
    api.post(f"/api/fermentations/{first['id']}/end").raise_for_status()
    second = api.post("/api/fermentations", json=fermentation_payload(api, "Seconda birra")).json()[
        "fermentation"
    ]
    second_time = datetime.fromisoformat(second["started_at"]).timestamp() + 1
    api.post(
        "/telemetry", json=gateway_lettura(timestamp=second_time, accel_x=999)
    ).raise_for_status()
    other = api.post("/api/pills", json={"name": "Altra", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    other_cycle = api.post(
        "/api/fermentations", json={"name": "Altra birra", "pill_id": other["id"]}
    ).json()["fermentation"]
    api.post(
        "/telemetry",
        json=gateway_lettura(pill_mac=other["mac"], timestamp=second_time, accel_x=888),
    ).raise_for_status()
    context = api.get(
        f"/api/fermentations/{first['id']}/chart-context",
        params={"from_timestamp": timestamp + 0.000001, "to_timestamp": second_time + 10},
    ).json()["context"]
    assert context["accel_x"]["before"]["accel_x"] == -2
    assert context["accel_x"]["after"] is None
    for cycle, value in ((second, 999), (other_cycle, 888)):
        context = api.get(
            f"/api/fermentations/{cycle['id']}/chart-context",
            params={"from_timestamp": 0, "to_timestamp": second_time - 0.1},
        ).json()["context"]
        assert context["accel_x"]["before"] is None
        assert context["accel_x"]["after"]["accel_x"] == value


def test_context_rejects_bad_ranges_and_unknown_cycles(api: httpx.Client) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Validazione")).json()[
        "fermentation"
    ]
    path = f"/api/fermentations/{cycle['id']}/chart-context"
    for params in (
        {},
        {"from_timestamp": 0},
        {"from_timestamp": -1, "to_timestamp": 1},
        {"from_timestamp": 2, "to_timestamp": 1},
        {"from_timestamp": "nan", "to_timestamp": 1},
        {"from_timestamp": 0, "to_timestamp": "inf"},
    ):
        assert (
            api.get(path, params={key: str(value) for key, value in params.items()}).status_code
            == 422
        )
    assert (
        api.get(
            "/api/fermentations/missing/chart-context",
            params={"from_timestamp": 0, "to_timestamp": 1},
        ).status_code
        == 404
    )
    empty = api.get(path, params={"from_timestamp": 0, "to_timestamp": 1}).json()["context"]
    assert len(empty) == 7
    assert all(edges == {"before": None, "after": None} for edges in empty.values())

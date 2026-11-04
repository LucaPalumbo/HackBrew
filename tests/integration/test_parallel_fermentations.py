from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx

from tests.payloads import fermentation_payload, gateway_lettura


def test_distinct_pillole_can_run_simultaneous_fermentazioni(api: httpx.Client) -> None:
    first = api.post("/api/fermentations", json=fermentation_payload(api, "IPA parallela"))
    assert first.status_code == 201
    pill = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()["pill"]
    second = api.post("/api/fermentations", json={"name": "Stout parallela", "pill_id": pill["id"]})
    assert second.status_code == 201
    active = api.get("/api/fermentations/active").json()
    assert {entry["id"] for entry in active["fermentations"]} == {
        first.json()["fermentation"]["id"],
        second.json()["fermentation"]["id"],
    }
    assert active["fermentation"] is None
    occupied = api.post("/api/fermentations", json={"name": "Conflitto", "pill_id": pill["id"]})
    assert occupied.status_code == 409


def test_ending_one_cycle_is_definitive_and_only_frees_its_pillola(api: httpx.Client) -> None:
    first = api.post("/api/fermentations", json=fermentation_payload(api, "IPA")).json()[
        "fermentation"
    ]
    other = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    second = api.post("/api/fermentations", json={"name": "Stout", "pill_id": other["id"]}).json()[
        "fermentation"
    ]
    pills = {pill["id"]: pill for pill in api.get("/api/pills").json()["pills"]}
    assert pills[first["pill_id"]]["available"] is False
    assert pills[other["id"]]["active_fermentation_id"] == second["id"]
    ended = api.post(f"/api/fermentations/{first['id']}/end")
    assert ended.status_code == 200
    assert api.post(f"/api/fermentations/{first['id']}/end").json() == ended.json()
    assert api.get(f"/api/fermentations/{second['id']}").json()["fermentation"] == second
    pills = {pill["id"]: pill for pill in api.get("/api/pills").json()["pills"]}
    assert pills[first["pill_id"]]["available"] is True
    assert pills[other["id"]]["available"] is False
    assert (
        api.post(
            "/api/fermentations", json={"name": "Nuova IPA", "pill_id": first["pill_id"]}
        ).status_code
        == 201
    )
    assert (
        api.patch(
            f"/api/fermentations/{second['id']}", json={"pill_id": first["pill_id"]}
        ).status_code
        == 405
    )


def test_cards_list_active_first_and_summarize_each_fermentazione(api: httpx.Client) -> None:
    closed = api.post("/api/fermentations", json=fermentation_payload(api, "Vecchia IPA")).json()[
        "fermentation"
    ]
    assert api.post(f"/api/fermentations/{closed['id']}/end").status_code == 200
    first = api.post("/api/fermentations", json=fermentation_payload(api, "Nuova IPA")).json()[
        "fermentation"
    ]
    pill = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()["pill"]
    second = api.post("/api/fermentations", json={"name": "Stout", "pill_id": pill["id"]}).json()[
        "fermentation"
    ]
    timestamp = datetime.fromisoformat(second["started_at"]).timestamp() + 0.000123
    for mac in (first["pill_mac"], second["pill_mac"]):
        assert (
            api.post(
                "/telemetry", json=gateway_lettura(pill_mac=mac, timestamp=timestamp)
            ).status_code
            == 200
        )
    page = api.get("/api/fermentations", params={"limit": 2}).json()
    assert [row["id"] for row in page["fermentations"]] == [second["id"], first["id"]]
    for entry in page["fermentations"]:
        assert entry["control_mode"] == "monitor_only"
        assert entry["latest_reading"]["pill_id"] == entry["pill_id"]
        assert entry["latest_reading"]["specific_gravity"] == 1.050125
        assert entry["reading_count"] == 1
    older = api.get("/api/fermentations", params={"offset": page["next_offset"], "limit": 2}).json()
    assert [row["id"] for row in older["fermentations"]] == [closed["id"]]
    assert older["fermentations"][0]["latest_reading"] is None
    assert older["next_offset"] is None
    found = api.get("/api/fermentations", params={"q": "ipa"}).json()["fermentations"]
    assert [row["id"] for row in found] == [first["id"], closed["id"]]
    concluded = api.get("/api/fermentations", params={"status": "concluded"}).json()[
        "fermentations"
    ]
    assert [row["id"] for row in concluded] == [closed["id"]]
    latest = api.get("/api/readings/latest", params={"pill_id": first["pill_id"]}).json()
    assert latest["fermentation"]["id"] == first["id"]
    assert {row["id"] for row in latest["active_fermentations"]} == {first["id"], second["id"]}


def test_concurrent_starts_have_one_winner_for_each_pillola(api: httpx.Client) -> None:
    first_id = api.get("/api/pills").json()["pills"][0]["id"]
    second_id = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]["id"]
    candidates = [first_id, second_id] * 6
    with ThreadPoolExecutor(max_workers=12) as pool:
        responses = list(
            pool.map(
                lambda pill_id: api.post(
                    "/api/fermentations", json={"name": "Avvio concorrente", "pill_id": pill_id}
                ),
                candidates,
            )
        )
    assert [response.status_code for response in responses].count(201) == 2
    assert [response.status_code for response in responses].count(409) == 10
    active = api.get("/api/fermentations/active").json()["fermentations"]
    assert {entry["pill_id"] for entry in active} == {first_id, second_id}
    assert len(active) == 2


def test_identical_and_delayed_samples_keep_parallel_and_successive_cycles_separate(
    api: httpx.Client,
) -> None:
    first = api.post("/api/fermentations", json=fermentation_payload(api, "Prima IPA")).json()[
        "fermentation"
    ]
    pill = api.post("/api/pills", json={"name": "Stout", "mac": "11:22:33:44:55:66"}).json()["pill"]
    second = api.post("/api/fermentations", json={"name": "Stout", "pill_id": pill["id"]}).json()[
        "fermentation"
    ]
    timestamp = datetime.fromisoformat(second["started_at"]).timestamp() + 0.000123
    for mac in (first["pill_mac"], pill["mac"]):
        assert (
            api.post(
                "/telemetry", json=gateway_lettura(pill_mac=mac, timestamp=timestamp)
            ).status_code
            == 200
        )
    ended = api.post(f"/api/fermentations/{first['id']}/end").json()["fermentation"]
    following = api.post(
        "/api/fermentations", json={"name": "Seconda IPA", "pill_id": first["pill_id"]}
    ).json()["fermentation"]
    boundary = datetime.fromisoformat(ended["ended_at"]).timestamp()
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=boundary, specific_gravity=1045)
        ).status_code
        == 200
    )
    assert api.get(f"/api/fermentations/{following['id']}/readings").json()["readings"] == []
    delayed = datetime.fromisoformat(first["started_at"]).timestamp() + 0.000123
    for _ in range(2):
        assert (
            api.post(
                "/telemetry", json=gateway_lettura(timestamp=delayed, specific_gravity=1060)
            ).status_code
            == 200
        )
    started = datetime.fromisoformat(following["started_at"]).timestamp()
    assert (
        api.post(
            "/telemetry", json=gateway_lettura(timestamp=started, specific_gravity=1030)
        ).status_code
        == 200
    )
    assert (
        api.post(
            "/telemetry",
            json=gateway_lettura(pill_mac=pill["mac"], timestamp=started, specific_gravity=1040),
        ).status_code
        == 200
    )
    original_history = api.get(f"/api/fermentations/{first['id']}/readings").json()["readings"]
    second_history = api.get(f"/api/fermentations/{second['id']}/readings").json()["readings"]
    following_history = api.get(f"/api/fermentations/{following['id']}/readings").json()["readings"]
    assert [row["specific_gravity"] for row in original_history] == [1.060, 1.050125]
    assert [row["specific_gravity"] for row in second_history] == [1.050125, 1.040]
    assert [row["specific_gravity"] for row in following_history] == [1.030]
    assert api.get(f"/api/fermentations/{first['id']}").json()["fermentation"] == ended

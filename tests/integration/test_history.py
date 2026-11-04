from datetime import datetime

import httpx
import pytest

from tests.payloads import fermentation_payload, gateway_lettura


def test_concluded_fermentazioni_can_be_found_by_name_without_listing_the_active_one(
    api: httpx.Client,
) -> None:
    first = api.post("/api/fermentations", json=fermentation_payload(api, "Prima IPA")).json()[
        "fermentation"
    ]
    assert api.post(f"/api/fermentations/{first['id']}/end").status_code == 200
    second = api.post("/api/fermentations", json=fermentation_payload(api, "Seconda stout")).json()[
        "fermentation"
    ]
    assert api.post(f"/api/fermentations/{second['id']}/end").status_code == 200
    assert (
        api.post("/api/fermentations", json=fermentation_payload(api, "Terza attiva")).status_code
        == 201
    )

    response = api.get("/api/fermentations", params={"limit": 1})
    assert response.status_code == 200
    page = response.json()
    assert [entry["id"] for entry in page["fermentations"]] == [second["id"]]
    assert page["next_offset"] == 1
    older = api.get("/api/fermentations", params={"limit": 1, "offset": 1}).json()
    assert [entry["id"] for entry in older["fermentations"]] == [first["id"]]
    assert older["next_offset"] is None
    found = api.get("/api/fermentations", params={"q": "prima ipa"}).json()
    assert [entry["id"] for entry in found["fermentations"]] == [first["id"]]
    assert api.get("/api/fermentations", params={"q": ".*"}).json()["fermentations"] == []


def test_history_pages_keep_original_samples_in_acquisition_order(api: httpx.Client) -> None:
    fermentation = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA paginata")
    ).json()["fermentation"]
    base = datetime.fromisoformat(fermentation["started_at"]).timestamp() + 0.000123
    for offset, gravity in [(3, 1040), (1, 1050), (2, 1045), (2, 1044), (0, 1060)]:
        assert (
            api.post(
                "/telemetry",
                json=gateway_lettura(timestamp=base + offset * 0.000001, specific_gravity=gravity),
            ).status_code
            == 200
        )
    path = f"/api/fermentations/{fermentation['id']}/readings"
    recent = api.get(path, params={"limit": 2}).json()
    assert [row["specific_gravity"] for row in recent["readings"]] == [1.044, 1.040]
    assert recent["next_before"]
    older = api.get(path, params={"limit": 2, "before": recent["next_before"]}).json()
    assert [row["specific_gravity"] for row in older["readings"]] == [1.050, 1.045]
    oldest = api.get(path, params={"limit": 2, "before": older["next_before"]}).json()
    assert [row["specific_gravity"] for row in oldest["readings"]] == [1.060]
    assert oldest["next_before"] is None
    assert oldest["readings"][0]["timestamp"] == base
    assert oldest["readings"][0]["battery"] == 63.2734375


def test_history_default_window_is_bounded_without_discarding_older_samples(
    api: httpx.Client,
) -> None:
    fermentation = api.post(
        "/api/fermentations", json=fermentation_payload(api, "IPA lunga")
    ).json()["fermentation"]
    base = datetime.fromisoformat(fermentation["started_at"]).timestamp() + 0.000123
    for number in range(205):
        assert (
            api.post(
                "/telemetry", json=gateway_lettura(timestamp=base + number * 0.000001)
            ).status_code
            == 200
        )
    path = f"/api/fermentations/{fermentation['id']}/readings"
    recent = api.get(path).json()
    assert len(recent["readings"]) == 200
    assert recent["readings"][-1]["timestamp"] == base + 204 * 0.000001
    older = api.get(path, params={"before": recent["next_before"]}).json()
    assert len(older["readings"]) == 5
    assert older["next_before"] is None
    assert older["readings"][0]["timestamp"] == base
    assert older["readings"][0]["specific_gravity"] == 1.050125


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 201},
        {"before": "bad"},
        {"before": "nan:000000000000000000000000"},
        {"before": "1:invalid"},
    ],
)
def test_invalid_history_page_is_rejected(api: httpx.Client, params: dict[str, str | int]) -> None:
    fermentation = api.post("/api/fermentations", json=fermentation_payload(api, "IPA")).json()[
        "fermentation"
    ]
    assert (
        api.get(f"/api/fermentations/{fermentation['id']}/readings", params=params).status_code
        == 422
    )

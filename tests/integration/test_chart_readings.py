"""Every original quantity remains available to the combined chart through HTTP."""

from datetime import datetime

import httpx

from tests.payloads import fermentation_payload, gateway_lettura


def test_chart_history_preserves_all_values_quality_and_acquisition_order(
    api: httpx.Client,
) -> None:
    cycle = api.post("/api/fermentations", json=fermentation_payload(api, "Sette misure")).json()[
        "fermentation"
    ]
    base = datetime.fromisoformat(cycle["started_at"]).timestamp() + 0.000123
    samples = [
        gateway_lettura(
            timestamp=base,
            valid=True,
            gravity_velocity=-2.125,
            accel_x=-1.25,
            accel_y=0.75,
            accel_z=2.5,
        ),
        gateway_lettura(
            timestamp=base + 129600,
            specific_gravity=1040.5,
            temperature=21.125,
            battery=70.25,
            valid=False,
            gravity_velocity=-99.5,
            accel_x=-0.75,
        ),
        gateway_lettura(
            timestamp=base + 129600,
            specific_gravity=1041.25,
            temperature=20.75,
            battery=71.5,
            valid=True,
            gravity_velocity=-3.25,
            accel_z=1.875,
        ),
    ]
    optional = gateway_lettura(timestamp=base + 259200, specific_gravity=1030.125)
    for field in ("valid", "gravity_velocity", "accel_x", "accel_y", "accel_z"):
        del optional[field]
    for payload in (optional, samples[1], samples[0], samples[2], samples[0]):
        api.post("/telemetry", json=payload).raise_for_status()
    other = api.post("/api/pills", json={"name": "Altra", "mac": "11:22:33:44:55:66"}).json()[
        "pill"
    ]
    api.post(
        "/telemetry", json=gateway_lettura(pill_mac=other["mac"], timestamp=base, accel_x=999)
    ).raise_for_status()
    history = api.get(f"/api/fermentations/{cycle['id']}/readings").json()["readings"]
    assert len(history) == 4
    assert [row["timestamp"] for row in history] == [
        base,
        base + 129600,
        base + 129600,
        base + 259200,
    ]
    assert [row["specific_gravity"] for row in history] == [1.050125, 1.0405, 1.04125, 1.030125]
    for row, source in zip(history[:3], samples, strict=True):
        for field in (
            "temperature",
            "battery",
            "gravity_velocity",
            "accel_x",
            "accel_y",
            "accel_z",
            "valid",
        ):
            assert row[field] == source[field]
    for field in ("valid", "gravity_velocity", "accel_x", "accel_y", "accel_z"):
        assert history[-1][field] is None

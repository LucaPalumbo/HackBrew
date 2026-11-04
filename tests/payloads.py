import httpx

TEST_MAC = "AA:BB:CC:DD:EE:FF"


def register_test_pill(api: httpx.Client) -> None:
    response = api.post("/api/pills", json={"name": "Pillola test", "mac": TEST_MAC})
    response.raise_for_status()


def fermentation_payload(api: httpx.Client, name: object) -> dict[str, object]:
    pills = api.get("/api/pills").json()["pills"]
    return {"name": name, "pill_id": pills[0]["id"]}


def gateway_lettura(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "pill_mac": TEST_MAC,
        "valid": False,
        "gravity_velocity": 0,
        "temperature": 19.6875,
        "specific_gravity": 1050.125,
        "accel_x": 0,
        "accel_y": 0,
        "accel_z": 0,
        "battery": 63.2734375,
        "timestamp": 1700000000.123456,
    }
    payload.update(changes)
    return payload

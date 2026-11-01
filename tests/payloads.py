def gateway_lettura(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
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

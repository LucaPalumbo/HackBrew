"""Verify persistence through the public API across an externally managed restart."""

import argparse
import os

import httpx
from pymongo import MongoClient

from tests.payloads import gateway_lettura


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["seed", "verify"])
    phase = parser.parse_args().phase
    database = os.environ["MONGODB_DATABASE"]
    if database != "hackbrew_test":
        raise RuntimeError("Restart checks require the isolated hackbrew_test database")

    with httpx.Client(base_url=os.environ["HACKBREW_BASE_URL"], timeout=10) as api:
        if phase == "seed":
            with MongoClient[dict[str, object]](os.environ["MONGODB_URI"]) as mongo:
                mongo.drop_database(database)
            response = api.post("/telemetry", json=gateway_lettura())
            response.raise_for_status()

        response = api.get("/api/readings/latest")
        response.raise_for_status()
        reading = response.json()["reading"]
        assert reading["specific_gravity"] == 1.050125
        assert reading["temperature"] == 19.6875
        assert reading["battery"] == 63.2734375
        assert reading["timestamp"] == 1700000000.123456
        assert reading["received_at"]
        print(f"Persistence {phase}: lettura recuperata dall'API con precisione preservata.")


if __name__ == "__main__":
    main()

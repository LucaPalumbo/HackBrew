import os
from collections.abc import Iterator

import httpx
import pytest
from pymongo import MongoClient


@pytest.fixture
def api() -> Iterator[httpx.Client]:
    database = os.environ["MONGODB_DATABASE"]
    if database != "hackbrew_test":
        raise RuntimeError("Tests require the isolated hackbrew_test database")
    with MongoClient[dict[str, object]](os.environ["MONGODB_URI"]) as mongo:
        mongo.drop_database(database)
    with httpx.Client(base_url=os.environ["HACKBREW_BASE_URL"], timeout=10) as client:
        yield client

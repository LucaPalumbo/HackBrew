"""Cleanup confined to the isolated test database, preserving application indexes."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database


@contextmanager
def isolated_database() -> Iterator[Database[dict[str, Any]]]:
    name = os.environ["MONGODB_DATABASE"]
    if name != "hackbrew_test":
        raise RuntimeError("Cleanup requires the isolated hackbrew_test database")
    with MongoClient[dict[str, Any]](os.environ["MONGODB_URI"]) as mongo:
        yield mongo[name]


def reset_test_database() -> None:
    with isolated_database() as db:
        for collection in db.list_collection_names():
            db[collection].delete_many({})


def seed_legacy_duplicates() -> None:
    """Arrange the pre-idempotency schema; verification uses only the public API."""
    with isolated_database() as db:
        collection = db.fermentation_readings
        collection.drop_index("unique_measurement")
        copies = list(collection.find({}, {"_id": False}))
        if copies:
            collection.insert_many(copies)

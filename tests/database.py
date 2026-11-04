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

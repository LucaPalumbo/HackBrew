"""Cleanup confined to the isolated test database, preserving application indexes."""

import os

from pymongo import MongoClient


def reset_test_database() -> None:
    name = os.environ["MONGODB_DATABASE"]
    if name != "hackbrew_test":
        raise RuntimeError("Cleanup requires the isolated hackbrew_test database")
    with MongoClient[dict[str, object]](os.environ["MONGODB_URI"]) as mongo:
        for collection in mongo[name].list_collection_names():
            mongo[name][collection].delete_many({})

"""Persist one historical sample per acquisition and measurement content."""

from typing import Any

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

MEASUREMENT_FIELDS = ("timestamp", "specific_gravity", "temperature", "battery")


def initialize_history(db: Database[dict[str, Any]]) -> None:
    db.fermentation_readings.create_index([("fermentation_id", 1), ("timestamp", 1), ("_id", 1)])
    collection = db.fermentation_readings
    if "unique_measurement" not in collection.index_information():
        duplicates = collection.aggregate(
            [
                {"$sort": {"received_at": 1, "_id": 1}},
                {
                    "$group": {
                        "_id": {field: f"${field}" for field in MEASUREMENT_FIELDS},
                        "keep": {"$first": "$_id"},
                        "count": {"$sum": 1},
                    }
                },
                {"$match": {"count": {"$gt": 1}}},
            ],
            allowDiskUse=True,
        )
        for duplicate in duplicates:
            collection.delete_many({**duplicate["_id"], "_id": {"$ne": duplicate["keep"]}})
    collection.create_index(
        [(field, 1) for field in MEASUREMENT_FIELDS], unique=True, name="unique_measurement"
    )


def record_reading(db: Database[dict[str, Any]], reading: dict[str, Any]) -> None:
    document = db.fermentations.find_one(
        {
            "started_at": {"$lte": reading["timestamp"]},
            "$or": [{"ended_at": None}, {"ended_at": {"$gt": reading["timestamp"]}}],
        },
        sort=[("started_at", -1), ("_id", -1)],
    )
    if document is None:
        return
    key = {field: reading[field] for field in MEASUREMENT_FIELDS}
    try:
        db.fermentation_readings.update_one(
            key, {"$setOnInsert": {**reading, "fermentation_id": document["_id"]}}, upsert=True
        )
    except DuplicateKeyError:
        if db.fermentation_readings.find_one(key) is None:
            raise

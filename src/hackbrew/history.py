"""Persist one historical sample per acquisition and measurement content."""

from typing import Any

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

MEASUREMENT_FIELDS = (
    "pill_id",
    "timestamp",
    "specific_gravity",
    "temperature",
    "battery",
    "valid",
    "gravity_velocity",
    "accel_x",
    "accel_y",
    "accel_z",
)


def initialize_history(db: Database[dict[str, Any]]) -> None:
    if "unique_measurement" in db.fermentation_readings.index_information():
        raise RuntimeError(
            "Dataset MVP precedente: eseguire il reset deliberato descritto nel README "
            "prima di avviare questa versione. Nessun dato è stato cancellato."
        )
    db.fermentation_readings.create_index([("fermentation_id", 1), ("timestamp", 1), ("_id", 1)])
    collection = db.fermentation_readings
    collection.create_index(
        [(field, 1) for field in MEASUREMENT_FIELDS], unique=True, name="unique_pill_measurement"
    )


def record_reading(db: Database[dict[str, Any]], reading: dict[str, Any]) -> dict[str, Any]:
    document = db.fermentations.find_one(
        {
            "pill_id": reading["pill_id"],
            "started_at": {"$lte": reading["timestamp"]},
            "$or": [{"ended_at": None}, {"ended_at": {"$gt": reading["timestamp"]}}],
        },
        sort=[("started_at", -1), ("_id", -1)],
    )
    if document is None:
        return reading
    key = {field: reading[field] for field in MEASUREMENT_FIELDS}
    try:
        persisted = db.fermentation_readings.find_one_and_update(
            key,
            {"$setOnInsert": {**reading, "fermentation_id": document["_id"]}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        persisted = db.fermentation_readings.find_one(key)
        if persisted is None:
            raise
    if persisted is None:
        raise RuntimeError("La lettura non è stata conservata.")
    return {key: value for key, value in persisted.items() if key not in {"_id", "fermentation_id"}}

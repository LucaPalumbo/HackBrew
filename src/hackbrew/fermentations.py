"""Fermentazione lifecycle and persisted monitoring intervals."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from hackbrew.models import FermentationName
from hackbrew.storage import database

router = APIRouter(prefix="/api/fermentations")


def initialize_fermentations(db: Database[dict[str, Any]]) -> None:
    db.fermentations.create_index(
        "status",
        name="one_active_fermentation",
        unique=True,
        partialFilterExpression={"status": "active"},
    )
    db.fermentation_readings.create_index([("fermentation_id", 1), ("timestamp", 1)])


def monitoring_time() -> float:
    return datetime.now(UTC).timestamp()


def public_fermentation(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document["_id"],
        "name": document["name"],
        "status": document["status"],
        "started_at": datetime.fromtimestamp(document["started_at"], UTC),
        "ended_at": datetime.fromtimestamp(document["ended_at"], UTC)
        if document["ended_at"] is not None
        else None,
    }


def active_fermentation(db: Database[dict[str, Any]]) -> dict[str, Any] | None:
    document = db.fermentations.find_one({"status": "active"})
    return public_fermentation(document) if document else None


@router.get("/active")
def get_active(request: Request) -> dict[str, object]:
    return {"fermentation": active_fermentation(database(request))}


@router.post("", status_code=201)
def start_fermentation(payload: FermentationName, request: Request) -> dict[str, object]:
    db = database(request)
    if active_fermentation(db):
        raise HTTPException(
            409, "C'è già una fermentazione attiva. Terminala prima di avviarne un'altra."
        )
    last = db.fermentations.find_one({"status": "concluded"}, sort=[("ended_at", -1)])
    started_at = monitoring_time()
    if last:
        started_at = max(started_at, last["ended_at"])
    document = {
        "_id": str(uuid4()),
        "name": payload.name,
        "started_at": started_at,
        "ended_at": None,
        "status": "active",
    }
    try:
        db.fermentations.insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(
            409, "C'è già una fermentazione attiva. Terminala prima di avviarne un'altra."
        ) from None
    return {"fermentation": public_fermentation(document)}


def require_fermentation(db: Database[dict[str, Any]], identifier: str) -> dict[str, Any]:
    document = db.fermentations.find_one({"_id": identifier})
    if document is None:
        raise HTTPException(404, "Fermentazione non trovata.")
    return document


@router.get("/{identifier}")
def get_fermentation(identifier: str, request: Request) -> dict[str, object]:
    return {
        "fermentation": public_fermentation(require_fermentation(database(request), identifier))
    }


@router.post("/{identifier}/end")
def end_fermentation(identifier: str, request: Request) -> dict[str, object]:
    db = database(request)
    document = db.fermentations.find_one_and_update(
        {"_id": identifier, "status": "active"},
        [
            {
                "$set": {
                    "status": "concluded",
                    "ended_at": {"$max": ["$started_at", monitoring_time()]},
                }
            }
        ],
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        require_fermentation(db, identifier)
        raise HTTPException(409, "Questa fermentazione è già conclusa.")
    return {"fermentation": public_fermentation(document)}


def reading_filter(document: dict[str, Any]) -> dict[str, Any]:
    bounds = {"$gte": document["started_at"]}
    if document["ended_at"] is not None:
        bounds["$lt"] = document["ended_at"]
    return {"fermentation_id": document["_id"], "timestamp": bounds}


def active_snapshot(db: Database[dict[str, Any]]) -> dict[str, object]:
    document = db.fermentations.find_one({"status": "active"})
    if document is None:
        return {"fermentation": None, "fermentation_reading": None}
    reading = db.fermentation_readings.find_one(
        reading_filter(document),
        {"_id": False, "fermentation_id": False},
        sort=[("timestamp", -1)],
    )
    return {"fermentation": public_fermentation(document), "fermentation_reading": reading}


@router.get("/{identifier}/readings")
def get_readings(identifier: str, request: Request) -> dict[str, object]:
    db = database(request)
    document = require_fermentation(db, identifier)
    readings = db.fermentation_readings.find(
        reading_filter(document), {"_id": False, "fermentation_id": False}
    ).sort("timestamp", 1)
    return {"readings": list(readings)}


def record_reading(db: Database[dict[str, Any]], reading: dict[str, Any]) -> None:
    document = db.fermentations.find_one(
        {
            "started_at": {"$lte": reading["timestamp"]},
            "$or": [{"ended_at": None}, {"ended_at": {"$gt": reading["timestamp"]}}],
        }
    )
    if document:
        db.fermentation_readings.insert_one({**reading, "fermentation_id": document["_id"]})

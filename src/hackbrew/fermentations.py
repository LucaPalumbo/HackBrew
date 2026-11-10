"""Fermentazione lifecycle and persisted monitoring intervals."""

import math
import re
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, Request
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from hackbrew.models import FermentationStart
from hackbrew.pills import require_pill
from hackbrew.storage import database

router = APIRouter(prefix="/api/fermentations")


def initialize_fermentations(db: Database[dict[str, Any]]) -> None:
    # Upgrade #16 records in place, retaining contact times, commands and pending OFF.
    for cycle in db.fermentations.find({"control_mode": "heating", "devices": {"$exists": False}}):
        device = {
            "id": cycle["heater_id"],
            "name": cycle["heater_name"],
            "capability": "heating",
            "role": "heater",
        }
        reserved = [device["id"]] if cycle["heater_reserved"] else []
        control = cycle["regulation"]
        db.fermentations.update_one(
            {"_id": cycle["_id"], "devices": {"$exists": False}},
            {
                "$set": {
                    "devices": [device],
                    "reserved_device_ids": reserved,
                    "thermal_reserved": bool(reserved),
                    "regulation": {
                        **control,
                        "devices": {device["id"]: {**control, "reserved": bool(reserved)}},
                    },
                },
                "$inc": {"control_revision": 1},
            },
        )
    db.fermentations.create_index(
        "reserved_device_ids",
        name="one_reservation_per_thermal_device",
        unique=True,
        partialFilterExpression={"thermal_reserved": True},
    )
    db.fermentations.create_index(
        "heater_id",
        name="one_reserved_fermentation_per_heater",
        unique=True,
        partialFilterExpression={"heater_reserved": True},
    )
    db.fermentations.create_index(
        "pill_id",
        name="one_active_fermentation_per_pill",
        unique=True,
        partialFilterExpression={"status": "active"},
    )
    if "one_active_fermentation" in db.fermentations.index_information():
        db.fermentations.drop_index("one_active_fermentation")


def monitoring_time() -> float:
    return datetime.now(UTC).timestamp()


def public_fermentation(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document["_id"],
        "name": document["name"],
        "pill_id": document["pill_id"],
        "pill_name": document["pill_name"],
        "pill_mac": document["pill_mac"],
        "status": document["status"],
        "started_at": datetime.fromtimestamp(document["started_at"], UTC),
        "ended_at": datetime.fromtimestamp(document["ended_at"], UTC)
        if document["ended_at"] is not None
        else None,
        "control_mode": document.get("control_mode", "monitor_only"),
        **(
            {
                key: document[key]
                for key in (
                    "temperature_min",
                    "temperature_max",
                    "hysteresis",
                    "regulation",
                    "devices",
                    "reserved_device_ids",
                    "thermal_reserved",
                )
            }
            | {
                key: document[key]
                for key in (
                    "heater_id",
                    "heater_name",
                    "heater_reserved",
                    "cooler_id",
                    "combined_id",
                )
                if key in document
            }
            if document.get("control_mode", "monitor_only") != "monitor_only"
            else {}
        ),
    }


def active_fermentations(db: Database[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        public_fermentation(document)
        for document in db.fermentations.find({"status": "active"}).sort(
            [("started_at", -1), ("_id", -1)]
        )
    ]


def fermentation_summary(db: Database[dict[str, Any]], document: dict[str, Any]) -> dict[str, Any]:
    query = reading_filter(document)
    reading = db.fermentation_readings.find_one(
        query,
        {"_id": False, "fermentation_id": False},
        sort=[("timestamp", -1), ("_id", -1)],
    )
    return {
        **public_fermentation(document),
        "latest_reading": reading,
        "reading_count": db.fermentation_readings.count_documents(query),
    }


@router.get("")
def list_fermentations(
    request: Request,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    status: Literal["active", "concluded"] | None = None,
) -> dict[str, object]:
    query: dict[str, Any] = {"status": status} if status else {}
    if q.strip():
        query["name"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    documents = list(
        database(request)
        .fermentations.find(query)
        .sort([("status", 1), ("ended_at", -1), ("started_at", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit + 1)
    )
    return {
        "fermentations": [
            fermentation_summary(database(request), document) for document in documents[:limit]
        ],
        "next_offset": offset + limit if len(documents) > limit else None,
    }


@router.get("/active")
def get_active(request: Request) -> dict[str, object]:
    fermentations = active_fermentations(database(request))
    return {
        "fermentations": fermentations,
        "fermentation": fermentations[0] if len(fermentations) == 1 else None,
    }


@router.post("", status_code=201)
def start_fermentation(payload: FermentationStart, request: Request) -> dict[str, object]:
    db = database(request)
    pill = require_pill(db, payload.pill_id)
    devices = []
    for role, capability in (("heater", "heating"), ("cooler", "cooling"), ("combined", "both")):
        identifier = getattr(payload, role + "_id")
        if identifier is None:
            continue
        device = db.thermal_devices.find_one({"_id": identifier})
        if device is None:
            raise HTTPException(404, "Dispositivo termico non trovato.")
        if device["capability"] != capability:
            raise HTTPException(
                422, "Le capacità del dispositivo non sono compatibili con la funzione scelta."
            )
        devices.append(
            {"id": device["_id"], "name": device["name"], "capability": capability, "role": role}
        )
    if db.fermentations.find_one({"status": "active", "pill_id": pill["_id"]}):
        raise HTTPException(
            409,
            "C'è già una fermentazione attiva per questa pillola. "
            "Terminala prima di riutilizzarla.",
        )
    last = db.fermentations.find_one(
        {"status": "concluded", "pill_id": pill["_id"]}, sort=[("ended_at", -1)]
    )
    started_at = monitoring_time()
    if last:
        started_at = max(started_at, last["ended_at"])
    document = {
        "_id": str(uuid4()),
        "name": payload.name,
        "pill_id": pill["_id"],
        "pill_name": pill["name"],
        "pill_mac": pill["mac"],
        "started_at": started_at,
        "ended_at": None,
        "status": "active",
    }
    if devices:
        document.update(
            {
                "control_mode": payload.control_mode,
                "heater_id": payload.heater_id,
                "heater_name": next(
                    (device["name"] for device in devices if device["role"] == "heater"), None
                ),
                "heater_reserved": payload.heater_id is not None,
                "cooler_id": payload.cooler_id,
                "combined_id": payload.combined_id,
                "devices": devices,
                "reserved_device_ids": [device["id"] for device in devices],
                "thermal_reserved": True,
                "temperature_min": payload.temperature_min,
                "temperature_max": payload.temperature_max,
                "hysteresis": payload.hysteresis,
                "control_revision": 0,
                "regulation": {
                    "status": "waiting",
                    "reason": "In attesa di temperatura utilizzabile.",
                    "desired_mode": "off",
                    "actual_mode": None,
                    "confirmed_at": None,
                    "command": None,
                    "last_sent_at": None,
                    "needs_off": True,
                    "error": None,
                },
            }
        )
    try:
        if devices:
            document["regulation"]["devices"] = {
                device["id"]: {
                    **{
                        key: value
                        for key, value in document["regulation"].items()
                        if key != "devices"
                    },
                    "reserved": True,
                }
                for device in devices
            }
        db.fermentations.insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(
            409,
            "Pillola o dispositivo termico già riservato. "
            "Attendi il termine e la conferma di spegnimento prima di riutilizzarlo.",
        ) from None
    return {"fermentation": public_fermentation(document)}


def require_fermentation(db: Database[dict[str, Any]], identifier: str) -> dict[str, Any]:
    document = db.fermentations.find_one({"_id": identifier})
    if document is None:
        raise HTTPException(404, "Fermentazione non trovata.")
    return document


@router.get("/{identifier}")
def get_fermentation(identifier: str, request: Request) -> dict[str, object]:
    db = database(request)
    document = require_fermentation(db, identifier)
    summary = fermentation_summary(db, document)
    return {
        "fermentation": public_fermentation(document),
        "latest_reading": summary["latest_reading"],
        "reading_count": summary["reading_count"],
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
                    "control_revision": {"$add": [{"$ifNull": ["$control_revision", 0]}, 1]},
                    "regulation": {
                        "$cond": [
                            {
                                "$ne": [
                                    {"$ifNull": ["$control_mode", "monitor_only"]},
                                    "monitor_only",
                                ]
                            },
                            {
                                "$mergeObjects": [
                                    "$regulation",
                                    {
                                        "desired_mode": "off",
                                        "status": "stopping",
                                        "needs_off": True,
                                        "devices": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$objectToArray": {
                                                            "$ifNull": ["$regulation.devices", {}]
                                                        }
                                                    },
                                                    "as": "device",
                                                    "in": {
                                                        "k": "$$device.k",
                                                        "v": {
                                                            "$mergeObjects": [
                                                                "$$device.v",
                                                                {"desired_mode": "off"},
                                                            ]
                                                        },
                                                    },
                                                }
                                            }
                                        },
                                    },
                                ]
                            },
                            "$$REMOVE",
                        ]
                    },
                }
            }
        ],
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        document = require_fermentation(db, identifier)
    return {"fermentation": public_fermentation(document)}


def reading_filter(document: dict[str, Any]) -> dict[str, Any]:
    bounds = {"$gte": document["started_at"]}
    if document["ended_at"] is not None:
        bounds["$lt"] = document["ended_at"]
    return {
        "fermentation_id": document["_id"],
        "pill_id": document["pill_id"],
        "timestamp": bounds,
    }


def active_snapshot(db: Database[dict[str, Any]], pill_id: str | None = None) -> dict[str, object]:
    documents = list(
        db.fermentations.find({"status": "active"}).sort([("started_at", -1), ("_id", -1)])
    )
    summaries = [fermentation_summary(db, document) for document in documents]
    selected = next((document for document in documents if document["pill_id"] == pill_id), None)
    if pill_id is None and len(documents) == 1:
        selected = documents[0]
    summary = next((row for row in summaries if selected and row["id"] == selected["_id"]), None)
    return {
        "active_fermentations": summaries,
        "fermentation": public_fermentation(selected) if selected else None,
        "fermentation_reading": summary["latest_reading"] if summary else None,
        "fermentation_reading_count": summary["reading_count"] if summary else 0,
    }


@router.get("/{identifier}/readings")
def get_readings(
    identifier: str,
    request: Request,
    limit: int = Query(default=200, ge=1, le=200),
    before: str | None = Query(default=None, max_length=100),
) -> dict[str, object]:
    db = database(request)
    document = require_fermentation(db, identifier)
    query = reading_filter(document)
    if before is not None:
        try:
            timestamp_text, cursor_identifier = before.split(":")
            timestamp = float(timestamp_text)
            if not math.isfinite(timestamp) or timestamp < 0:
                raise ValueError
            cursor_id = ObjectId(cursor_identifier)
        except (ValueError, InvalidId):
            raise HTTPException(422, "Cursore dello storico non valido.") from None
        query["$or"] = [
            {"timestamp": {"$lt": timestamp}},
            {"timestamp": timestamp, "_id": {"$lt": cursor_id}},
        ]
    documents = list(
        db.fermentation_readings.find(query, {"fermentation_id": False})
        .sort([("timestamp", -1), ("_id", -1)])
        .limit(limit + 1)
    )
    page = documents[:limit]
    next_before = f"{page[-1]['timestamp']}:{page[-1]['_id']}" if len(documents) > limit else None
    for reading in page:
        reading.pop("_id")
    return {"readings": list(reversed(page)), "next_before": next_before}

"""Registered pillole and their Bluetooth identities."""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from hackbrew.models import PillRegistration
from hackbrew.storage import database

router = APIRouter(prefix="/api/pills")


def initialize_pills(db: Database[dict[str, Any]]) -> None:
    db.pills.create_index("mac", unique=True)


def public_pill(document: dict[str, Any], active_identifier: str | None = None) -> dict[str, Any]:
    return {
        "id": document["_id"],
        "name": document["name"],
        "mac": document["mac"],
        "available": active_identifier is None,
        "active_fermentation_id": active_identifier,
    }


def registered_pills(db: Database[dict[str, Any]]) -> list[dict[str, Any]]:
    assignments = {
        entry["pill_id"]: entry["_id"] for entry in db.fermentations.find({"status": "active"})
    }
    return [
        public_pill(pill, assignments.get(pill["_id"]))
        for pill in db.pills.find().sort([("name", 1), ("_id", 1)])
    ]


def require_pill(db: Database[dict[str, Any]], identifier: str) -> dict[str, Any]:
    pill = db.pills.find_one({"_id": identifier})
    if pill is None:
        raise HTTPException(404, "Pillola non trovata.")
    return pill


def pill_snapshots(db: Database[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = {entry["_id"]: entry for entry in db.latest_reading.find()}
    return [
        {
            **pill,
            "reading": latest.get(pill["id"], {}).get("reading"),
            "last_received_at": latest.get(pill["id"], {}).get("last_received_at"),
        }
        for pill in registered_pills(db)
    ]


@router.get("")
def list_pills(request: Request) -> dict[str, object]:
    return {"pills": registered_pills(database(request))}


@router.post("", status_code=201)
def register_pill(payload: PillRegistration, request: Request) -> dict[str, object]:
    document = {"_id": str(uuid4()), "name": payload.name, "mac": payload.mac}
    try:
        database(request).pills.insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(409, "Questo MAC Bluetooth è già registrato.") from None
    return {"pill": public_pill(document)}

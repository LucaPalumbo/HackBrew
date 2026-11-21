"""Registered pillole and their Bluetooth identities."""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from hackbrew.models import PillRegistration, PillRename
from hackbrew.storage import database, registry_transaction

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
        for pill in db.pills.find({"archived": {"$ne": True}}).sort([("name", 1), ("_id", 1)])
    ]


def lock_pill(
    db: Database[dict[str, Any]], identifier: str, session: ClientSession
) -> dict[str, Any]:
    # A shared document write serializes lifecycle changes with cycle creation.
    # A transaction containing only availability reads would allow write skew.
    pill = db.pills.find_one_and_update(
        {"_id": identifier, "archived": {"$ne": True}},
        {"$inc": {"registry_revision": 1}},
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    if pill is None:
        raise HTTPException(404, "Pillola non trovata.")
    return pill


def lock_free_pill(
    db: Database[dict[str, Any]], identifier: str, session: ClientSession
) -> dict[str, Any]:
    pill = lock_pill(db, identifier, session)
    if db.fermentations.find_one({"pill_id": identifier, "status": "active"}, session=session):
        raise HTTPException(409, "La pillola è assegnata a una fermentazione attiva.")
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
    db = database(request)
    document = {
        "_id": str(uuid4()),
        "name": payload.name,
        "mac": payload.mac,
        "registry_revision": 1,
    }
    try:
        db.pills.insert_one(document)
    except DuplicateKeyError:
        restored = db.pills.find_one_and_update(
            {"mac": payload.mac, "archived": True},
            {
                "$set": {"name": payload.name, "archived": False},
                "$inc": {"registry_revision": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if restored is None:
            raise HTTPException(409, "Questo MAC Bluetooth è già registrato.") from None
        document = restored
    return {"pill": public_pill(document)}


@router.patch("/{identifier}")
def rename_pill(identifier: str, payload: PillRename, request: Request) -> dict[str, object]:
    db = database(request)

    def rename(session: ClientSession) -> dict[str, object]:
        pill = lock_free_pill(db, identifier, session)
        db.pills.update_one({"_id": identifier}, {"$set": {"name": payload.name}}, session=session)
        return {"pill": public_pill({**pill, "name": payload.name})}

    return registry_transaction(db, rename)


@router.delete("/{identifier}", status_code=204)
def remove_pill(identifier: str, request: Request) -> Response:
    db = database(request)

    def remove(session: ClientSession) -> None:
        lock_free_pill(db, identifier, session)
        db.pills.update_one({"_id": identifier}, {"$set": {"archived": True}}, session=session)

    registry_transaction(db, remove)
    return Response(status_code=204)

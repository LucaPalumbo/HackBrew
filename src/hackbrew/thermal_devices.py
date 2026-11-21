"""Registration and truthful observations of external thermal devices."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from hackbrew.storage import database, registry_transaction
from hackbrew.thermal_client import ActuatorError, ThermalDeviceClient
from hackbrew.thermal_contract import Capability

router = APIRouter(prefix="/api/thermal-devices")


class ThermalDeviceAddress(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True, extra="forbid")
    base_url: str

    @field_validator("base_url")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        url = HttpUrl(value)
        if url.username or url.password or url.query is not None or url.fragment is not None:
            raise ValueError("Usa un indirizzo HTTP(S) senza credenziali, query o frammenti.")
        return str(url).rstrip("/")


class ThermalDeviceRegistration(ThermalDeviceAddress):
    name: str = Field(min_length=1, max_length=200)
    capability: Capability


class ThermalDeviceUpdate(ThermalDeviceAddress):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str = Field(default="", validate_default=False)


def lock_thermal_device(
    db: Database[dict[str, Any]], identifier: str, session: ClientSession
) -> dict[str, Any]:
    device = db.thermal_devices.find_one_and_update(
        {"_id": identifier, "archived": {"$ne": True}},
        {"$inc": {"registry_revision": 1}},
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    if device is None:
        raise HTTPException(404, "Dispositivo termico non trovato.")
    return device


def lock_free_device(
    db: Database[dict[str, Any]], identifier: str, session: ClientSession
) -> dict[str, Any]:
    device = lock_thermal_device(db, identifier, session)
    if db.fermentations.find_one(
        {"reserved_device_ids": identifier, "thermal_reserved": True}, session=session
    ):
        raise HTTPException(
            409, "Dispositivo riservato: attendi il termine e lo spegnimento confermato."
        )
    return device


def unknown_observation() -> dict[str, Any]:
    return {
        "verification_status": "unverified",
        **dict.fromkeys(
            (
                "actual_mode",
                "desired_mode",
                "confirmed_at",
                "last_confirmation",
                "applied_timeout_seconds",
                "applied_config_revision",
                "communication_error",
                "checked_at",
                "reported_capability",
                "application_status",
            )
        ),
    }


def initialize_thermal_devices(db: Database[dict[str, Any]]) -> None:
    db.thermal_devices.update_many(
        {"connection_revision": {"$exists": False}}, {"$set": {"connection_revision": 0}}
    )
    db.thermal_devices.update_many({"archived": {"$exists": False}}, {"$set": {"archived": False}})
    # Install the new constraint before dropping the old, stricter index.
    db.thermal_devices.create_index(
        "base_url",
        unique=True,
        name="active_thermal_address",
        partialFilterExpression={"archived": False},
    )
    if "base_url_1" in db.thermal_devices.index_information():
        db.thermal_devices.drop_index("base_url_1")


def public_device(document: dict[str, Any], db: Database[dict[str, Any]]) -> dict[str, Any]:
    reservation = db.fermentations.find_one(
        {"reserved_device_ids": document["_id"], "thermal_reserved": True}
    )
    return {
        "id": document["_id"],
        "available": reservation is None,
        "reserved_fermentation_id": reservation["_id"] if reservation else None,
        "reserved_fermentation_name": reservation["name"] if reservation else None,
        **{
            key: value
            for key, value in document.items()
            if key
            not in {
                "_id",
                "check_revision",
                "registry_revision",
                "connection_revision",
                "archived",
            }
        },
    }


@router.get("")
def list_devices(request: Request) -> dict[str, object]:
    return {
        "devices": [
            public_device(device, database(request))
            for device in database(request)
            .thermal_devices.find({"archived": {"$ne": True}})
            .sort([("name", 1), ("_id", 1)])
        ]
    }


@router.post("", status_code=201)
def register_device(payload: ThermalDeviceRegistration, request: Request) -> dict[str, object]:
    document = {
        "_id": str(uuid4()),
        **payload.model_dump(),
        "connection_revision": 0,
        "archived": False,
        "verification_status": "unverified",
        "actual_mode": None,
        "desired_mode": None,
        "confirmed_at": None,
        "last_confirmation": None,
        "applied_timeout_seconds": None,
        "applied_config_revision": None,
        "communication_error": None,
        "checked_at": None,
        "reported_capability": None,
        "application_status": None,
    }
    try:
        database(request).thermal_devices.insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(409, "Questo indirizzo HTTP è già registrato.") from None
    return {"device": public_device(document, database(request))}


@router.patch("/{identifier}")
def update_device(
    identifier: str, payload: ThermalDeviceUpdate, request: Request
) -> dict[str, object]:
    db = database(request)
    changes = payload.model_dump(exclude_unset=True)
    if not changes or changes.get("name", "") is None:
        raise HTTPException(422, "Inserisci nome o indirizzo HTTP(S) del dispositivo.")

    def update(session: ClientSession) -> dict[str, Any]:
        device = lock_free_device(db, identifier, session)
        address_changed = "base_url" in changes and changes["base_url"] != device["base_url"]
        values = {**changes, **(unknown_observation() if address_changed else {})}
        mutation: dict[str, Any] = {"$set": values}
        if address_changed:
            mutation["$inc"] = {"check_revision": 1, "connection_revision": 1}
            db.device_timeout_sync.delete_one({"_id": identifier}, session=session)
        db.thermal_devices.update_one({"_id": identifier}, mutation, session=session)
        return {**device, **values}

    try:
        device = registry_transaction(db, update)
    except DuplicateKeyError:
        raise HTTPException(409, "Questo indirizzo HTTP è già registrato.") from None
    return {"device": public_device(device, db)}


@router.delete("/{identifier}", status_code=204)
def remove_device(identifier: str, request: Request) -> Response:
    db = database(request)

    def remove(session: ClientSession) -> None:
        lock_free_device(db, identifier, session)
        db.thermal_devices.update_one(
            {"_id": identifier},
            {"$set": {"archived": True}, "$inc": {"check_revision": 1, "connection_revision": 1}},
            session=session,
        )
        db.device_timeout_sync.delete_one({"_id": identifier}, session=session)

    registry_transaction(db, remove)
    return Response(status_code=204)


@router.post("/{identifier}/check")
def check_device(identifier: str, request: Request) -> dict[str, object]:
    collection = database(request).thermal_devices
    document = collection.find_one_and_update(
        {"_id": identifier, "archived": {"$ne": True}},
        {"$inc": {"check_revision": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        raise HTTPException(404, "Dispositivo termico non trovato.")
    try:
        state = ThermalDeviceClient(document["base_url"]).read_state()
        if state.capability != document["capability"]:
            raise ActuatorError(
                "Le funzioni dichiarate dal dispositivo non corrispondono al registro."
            )
        update: dict[str, Any] = {
            "verification_status": "confirmed"
            if state.application_status in {"applied", "timed_out"}
            else "pending",
            "actual_mode": state.actual_mode,
            "desired_mode": state.desired_mode,
            "confirmed_at": state.confirmed_at,
            "reported_capability": state.capability,
            "application_status": state.application_status,
            "applied_timeout_seconds": state.applied_timeout_seconds
            if state.actual_mode is not None
            else None,
            "applied_config_revision": state.applied_config_revision
            if state.actual_mode is not None
            else None,
            "communication_error": None,
        }
        if state.actual_mode is not None:
            update["last_confirmation"] = state.model_dump()
    except ActuatorError as error:
        update = {
            "verification_status": "error",
            "actual_mode": None,
            "desired_mode": None,
            "confirmed_at": None,
            "reported_capability": None,
            "application_status": None,
            "applied_timeout_seconds": None,
            "applied_config_revision": None,
            "communication_error": str(error),
        }
    update["checked_at"] = datetime.now(UTC)
    # A slow older verification must not overwrite a newer observation.
    collection.update_one(
        {
            "_id": identifier,
            "check_revision": document["check_revision"],
            "archived": {"$ne": True},
        },
        {"$set": update},
    )
    current = collection.find_one({"_id": identifier, "archived": {"$ne": True}})
    if current is None:
        raise HTTPException(404, "Dispositivo termico non trovato.")
    return {"device": public_device(current, database(request))}

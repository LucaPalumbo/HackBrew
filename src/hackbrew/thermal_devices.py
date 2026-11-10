"""Registration and truthful observations of external thermal devices."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from hackbrew.storage import database
from hackbrew.thermal_client import ActuatorError, ThermalDeviceClient
from hackbrew.thermal_contract import Capability

router = APIRouter(prefix="/api/thermal-devices")


class ThermalDeviceRegistration(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    capability: Capability
    base_url: str

    @field_validator("base_url")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        url = HttpUrl(value)
        if url.username or url.password or url.query is not None or url.fragment is not None:
            raise ValueError("Usa un indirizzo HTTP(S) senza credenziali, query o frammenti.")
        return str(url).rstrip("/")


def initialize_thermal_devices(db: Database[dict[str, Any]]) -> None:
    db.thermal_devices.create_index("base_url", unique=True)


def public_device(document: dict[str, Any], db: Database[dict[str, Any]]) -> dict[str, Any]:
    reservation = db.fermentations.find_one({"heater_id": document["_id"], "heater_reserved": True})
    return {
        "id": document["_id"],
        "available": reservation is None,
        "reserved_fermentation_id": reservation["_id"] if reservation else None,
        **{key: value for key, value in document.items() if key not in {"_id", "check_revision"}},
    }


@router.get("")
def list_devices(request: Request) -> dict[str, object]:
    return {
        "devices": [
            public_device(device, database(request))
            for device in database(request).thermal_devices.find().sort([("name", 1), ("_id", 1)])
        ]
    }


@router.post("", status_code=201)
def register_device(payload: ThermalDeviceRegistration, request: Request) -> dict[str, object]:
    document = {
        "_id": str(uuid4()),
        **payload.model_dump(),
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


@router.post("/{identifier}/check")
def check_device(identifier: str, request: Request) -> dict[str, object]:
    collection = database(request).thermal_devices
    document = collection.find_one_and_update(
        {"_id": identifier},
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
        {"_id": identifier, "check_revision": document["check_revision"]}, {"$set": update}
    )
    current = collection.find_one({"_id": identifier})
    assert current is not None
    return {"device": public_device(current, database(request))}

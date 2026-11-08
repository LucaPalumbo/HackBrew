"""Persisted global communication timeout and observable device synchronization."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from hackbrew.storage import database

router = APIRouter(prefix="/api/settings")


class TimeoutUpdate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    communication_timeout_seconds: FiniteFloat = Field(gt=0)


def timeout_configuration(db: Database[dict[str, Any]]) -> dict[str, Any]:
    try:
        document = db.settings.find_one_and_update(
            {"_id": "global"},
            {
                "$setOnInsert": {
                    "communication_timeout_seconds": 10800.0,
                    "revision": 0,
                    "updated_at": datetime.now(UTC),
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        document = db.settings.find_one({"_id": "global"})
    assert document is not None
    return document


def settings_snapshot(db: Database[dict[str, Any]]) -> dict[str, Any]:
    configuration = timeout_configuration(db)
    observed = {entry["_id"]: entry for entry in db.device_timeout_sync.find()}
    devices = []
    for device in db.thermal_devices.find().sort([("name", 1), ("_id", 1)]):
        sync = observed.get(device["_id"], {})
        current = sync.get("desired_revision") == configuration["revision"]
        status = "pending"
        if current and sync.get("status") == "error":
            status = "error"
        elif (
            current
            and sync.get("status") == "confirmed"
            and (
                sync.get("applied_revision") == configuration["revision"]
                and sync.get("applied_timeout_seconds")
                == configuration["communication_timeout_seconds"]
            )
        ):
            status = "confirmed"
        devices.append(
            {
                "id": device["_id"],
                "name": device["name"],
                "capability": device["capability"],
                "desired_revision": configuration["revision"],
                "desired_timeout_seconds": configuration["communication_timeout_seconds"],
                "status": status,
                "applied_revision": sync.get("applied_revision"),
                "applied_timeout_seconds": sync.get("applied_timeout_seconds"),
                "confirmed_at": sync.get("confirmed_at"),
                "last_attempt_at": sync.get("last_attempt_at"),
                "error": sync.get("error") if current else None,
            }
        )
    return {key: value for key, value in configuration.items() if key != "_id"} | {
        "devices": devices
    }


@router.get("")
def read_settings(request: Request) -> dict[str, Any]:
    return settings_snapshot(database(request))


@router.patch("")
def change_timeout(payload: TimeoutUpdate, request: Request) -> dict[str, Any]:
    db = database(request)
    timeout_configuration(db)
    db.settings.update_one(
        {
            "_id": "global",
            "communication_timeout_seconds": {"$ne": payload.communication_timeout_seconds},
        },
        {
            "$set": {
                "communication_timeout_seconds": payload.communication_timeout_seconds,
                "updated_at": datetime.now(UTC),
            },
            "$inc": {"revision": 1},
        },
    )
    return settings_snapshot(db)

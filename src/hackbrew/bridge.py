"""Stable source registry consumed by the external Bluetooth bridge."""

import hashlib
import json

from fastapi import APIRouter, Request

from hackbrew.storage import database

router = APIRouter(prefix="/api/bridge")


@router.get("/pills")
def bridge_pills(request: Request) -> dict[str, object]:
    pills = [
        {"id": pill["_id"], "name": pill["name"], "mac": pill["mac"]}
        for pill in database(request).pills.find().sort("_id", 1)
    ]
    # Content revision: computed from this exact snapshot, independent of reads,
    # live measurements, assignments and process restarts.
    revision = hashlib.sha256(json.dumps(pills, sort_keys=True).encode()).hexdigest()
    return {"revision": revision, "pills": pills}

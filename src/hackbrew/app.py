"""Public HTTP application."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from starlette.concurrency import run_in_threadpool

from hackbrew.fermentations import active_snapshot, initialize_fermentations
from hackbrew.fermentations import router as fermentations_router
from hackbrew.history import initialize_history, record_reading
from hackbrew.models import GatewayReading
from hackbrew.storage import database


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    freshness_seconds = int(os.environ.get("HACKBREW_FRESHNESS_SECONDS", "300"))
    if freshness_seconds <= 0:
        raise ValueError("HACKBREW_FRESHNESS_SECONDS must be a positive integer")
    application.state.freshness_seconds = freshness_seconds
    with MongoClient[dict[str, Any]](
        os.environ.get("MONGODB_URI", "mongodb://mongo:27017"),
        serverSelectionTimeoutMS=2000,
        connectTimeoutMS=2000,
        tz_aware=True,
    ) as client:
        application.state.database = client[os.environ.get("MONGODB_DATABASE", "hackbrew")]
        initialize_fermentations(application.state.database)
        initialize_history(application.state.database)
        yield


app = FastAPI(title="HackBrew", lifespan=lifespan)
app.include_router(fermentations_router)


@app.exception_handler(RequestValidationError)
async def invalid_reading(_request: Request, error: RequestValidationError) -> JSONResponse:
    details = [
        {"loc": issue["loc"], "msg": issue["msg"], "type": issue["type"]}
        for issue in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.exception_handler(PyMongoError)
async def database_unavailable(_request: Request, _error: PyMongoError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Archivio delle letture temporaneamente non disponibile."},
    )


@app.get("/api/health")
def health(request: Request) -> dict[str, str]:
    database(request).command("ping")
    return {"status": "ok"}


@app.get("/api/readings/latest")
def latest_reading(request: Request) -> dict[str, object]:
    reading = (
        database(request)
        .get_collection("latest_reading")
        .find_one({"_id": "latest"}, {"_id": False})
    )
    return {
        "reading": reading,
        **active_snapshot(database(request)),
        "freshness_seconds": request.app.state.freshness_seconds,
        "server_time": datetime.now(UTC).timestamp(),
    }


@app.get("/api/readings/events", response_class=EventSourceResponse)
async def reading_events(request: Request) -> AsyncIterator[ServerSentEvent]:
    previous: object = object()
    while not await request.is_disconnected():
        try:
            snapshot = await run_in_threadpool(latest_reading, request)
        except PyMongoError:
            # Closing the stream triggers EventSource's automatic reconnection.
            yield ServerSentEvent(event="unavailable", data={}, retry=2000)
            return
        persisted_state = (
            snapshot["reading"],
            snapshot["fermentation"],
            snapshot["fermentation_reading"],
            snapshot["fermentation_reading_count"],
        )
        if persisted_state != previous:
            yield ServerSentEvent(
                event="reading",
                data=snapshot,
                retry=2000,
            )
            previous = persisted_state
        await asyncio.sleep(1)


@app.post("/telemetry")
def receive_reading(payload: GatewayReading, request: Request) -> dict[str, object]:
    reading = payload.model_dump(
        include={"temperature", "specific_gravity", "battery", "timestamp"}
    )
    reading["specific_gravity"] = payload.specific_gravity / 1000
    reading["received_at"] = datetime.now(UTC)
    record_reading(database(request), reading)
    reading["_id"] = "latest"
    collection = database(request).get_collection("latest_reading")
    update = [
        {
            "$replaceWith": {
                "$cond": [
                    {"$gt": [payload.timestamp, {"$ifNull": ["$timestamp", -1]}]},
                    {"$literal": reading},
                    "$$ROOT",
                ]
            }
        }
    ]
    try:
        latest = collection.find_one_and_update(
            {"_id": "latest"}, update, upsert=True, return_document=ReturnDocument.AFTER
        )
    except DuplicateKeyError:
        latest = collection.find_one_and_update(
            {"_id": "latest"}, update, return_document=ReturnDocument.AFTER
        )
    if latest is None:
        raise PyMongoError("Latest reading was not persisted")
    latest.pop("_id", None)
    return {"reading": latest}


frontend_dist = os.environ.get("HACKBREW_FRONTEND_DIST")
if frontend_dist and Path(frontend_dist).is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

"""Persist and reconcile configuration-only actuator updates independently of the browser."""

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from hackbrew.settings import timeout_configuration
from hackbrew.thermal_client import ActuatorError, ThermalDeviceClient
from hackbrew.thermal_contract import DeviceState, TimeoutConfiguration

logger = logging.getLogger(__name__)


def validate_observation(
    state: DeviceState, capability: str, revision: int, duration: float
) -> None:
    if state.capability != capability:
        raise ActuatorError("Le funzioni dichiarate dal dispositivo non corrispondono al registro.")
    desired = state.configuration_command or state.accepted_command
    if desired is not None and (
        desired.config_revision > revision
        or (desired.config_revision == revision and desired.timeout_seconds != duration)
    ):
        raise ActuatorError(
            "Il dispositivo dichiara una configurazione discordante; riconciliazione richiesta."
        )
    if state.applied_config_revision > revision or (
        state.applied_config_revision == revision and state.applied_timeout_seconds != duration
    ):
        raise ActuatorError("La configurazione applicata dal dispositivo è discordante.")


def configuration_command(
    db: Database[dict[str, Any]], identifier: str, configuration: dict[str, Any], state: DeviceState
) -> TimeoutConfiguration:
    control_id = state.accepted_command.command_id if state.accepted_command else None
    target = [identifier, configuration["revision"], state.boot_id, control_id]
    key = hashlib.sha256(json.dumps(target).encode()).hexdigest()
    command = TimeoutConfiguration(
        boot_id=state.boot_id,
        command_id=str(uuid4()),
        expected_control_id=control_id,
        config_revision=configuration["revision"],
        timeout_seconds=configuration["communication_timeout_seconds"],
    )
    try:
        document = db.timeout_commands.find_one_and_update(
            {"_id": key},
            {"$setOnInsert": {"command": command.model_dump()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        document = db.timeout_commands.find_one({"_id": key})
    assert document is not None
    return TimeoutConfiguration.model_validate(document["command"])


def synchronize_device(db: Database[dict[str, Any]], device: dict[str, Any]) -> None:
    if db.thermal_devices.find_one({"_id": device["_id"]}) is None:
        return
    configuration = timeout_configuration(db)
    revision = configuration["revision"]
    duration = configuration["communication_timeout_seconds"]
    try:
        attempt = db.device_timeout_sync.find_one_and_update(
            {"_id": device["_id"]},
            {
                "$inc": {"attempt": 1},
                "$set": {"desired_revision": revision, "last_attempt_at": datetime.now(UTC)},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        return  # Another process owns a newer attempt; its result is authoritative.
    assert attempt is not None
    try:
        client = ThermalDeviceClient(device["base_url"])
        state = client.read_state()
        validate_observation(state, device["capability"], revision, duration)
        if state.actual_mode is not None and (
            state.applied_config_revision != revision or state.applied_timeout_seconds != duration
        ):
            command = configuration_command(db, device["_id"], configuration, state)
            if timeout_configuration(db)["revision"] != revision:
                return
            if db.thermal_devices.find_one({"_id": device["_id"]}) is None:
                return
            identity = state.device_id
            state = client.configure_timeout(command)
            if state.boot_id != command.boot_id or state.device_id != identity:
                raise ActuatorError("La conferma appartiene a un dispositivo o avvio diverso.")
            validate_observation(state, device["capability"], revision, duration)
        confirmed = (
            state.actual_mode is not None
            and state.applied_config_revision == revision
            and state.applied_timeout_seconds == duration
        )
        update: dict[str, Any] = {"status": "confirmed" if confirmed else "pending", "error": None}
        if state.actual_mode is not None:
            update.update(
                {
                    "applied_revision": state.applied_config_revision,
                    "applied_timeout_seconds": state.applied_timeout_seconds,
                    "confirmed_at": state.applied_configuration.confirmed_at
                    if state.applied_configuration
                    else state.confirmed_at,
                    "boot_id": state.boot_id,
                }
            )
    except ActuatorError as error:
        update = {"status": "error", "error": str(error)}
    db.device_timeout_sync.update_one(
        {"_id": device["_id"], "attempt": attempt["attempt"], "desired_revision": revision},
        {"$set": update},
    )


async def synchronize_timeouts(db: Database[dict[str, Any]]) -> None:
    semaphore = asyncio.Semaphore(4)

    async def synchronize(device: dict[str, Any]) -> None:
        async with semaphore:
            try:
                await asyncio.to_thread(synchronize_device, db, device)
            except PyMongoError as error:
                logger.warning("Timeout synchronization unavailable: %s", error)

    while True:
        try:
            devices = await asyncio.to_thread(lambda: list(db.thermal_devices.find()))
            await asyncio.gather(*(synchronize(device) for device in devices))
        except PyMongoError as error:
            logger.warning("Timeout synchronization unavailable: %s", error)
        await asyncio.sleep(0.5)

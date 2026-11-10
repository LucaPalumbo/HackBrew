"""Persistent heating control, physical reconciliation and definitive shutdown."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError

from hackbrew.settings import timeout_configuration
from hackbrew.thermal_client import ActuatorError, ThermalDeviceClient
from hackbrew.thermal_contract import ControlCommand, DeviceState, Mode

logger = logging.getLogger(__name__)


def save_control(
    db: Database[dict[str, Any]],
    cycle: dict[str, Any],
    control: dict[str, Any],
    *,
    released: bool = False,
) -> dict[str, Any] | None:
    return db.fermentations.find_one_and_update(
        {
            "_id": cycle["_id"],
            "control_revision": cycle["control_revision"],
            "heater_reserved": True,
        },
        {
            "$set": {"regulation": control, "heater_reserved": not released},
            "$inc": {"control_revision": 1},
        },
        return_document=ReturnDocument.AFTER,
    )


def command_confirmed(state: DeviceState, command: ControlCommand | None) -> bool:
    return bool(
        command is not None
        and state.boot_id == command.boot_id
        and state.accepted_command == command
        and state.applied_command_id == command.command_id
        and state.actual_mode == command.mode
        and state.application_status == "applied"
    )


def usable_temperature(
    db: Database[dict[str, Any]],
    cycle: dict[str, Any],
    timeout: float,
) -> tuple[float | None, Literal["waiting", "suspended"] | None, str | None]:
    latest = db.latest_reading.find_one({"_id": cycle["pill_id"]})
    if latest is None or latest.get("reading", {}).get("timestamp", -1) < cycle["started_at"]:
        return None, "waiting", "In attesa di temperatura utilizzabile."
    if (datetime.now(UTC) - latest["last_received_at"]).total_seconds() >= timeout:
        return None, "suspended", "Timeout di comunicazione della pillola superato."
    return float(latest["reading"]["temperature"]), None, None


def make_command(
    cycle: dict[str, Any],
    state: DeviceState,
    mode: Mode,
    configuration: dict[str, Any],
) -> ControlCommand:
    previous = cycle["regulation"].get("command")
    accepted = state.accepted_command
    epoch = max(
        previous["ownership_epoch"] if previous else 0, accepted.ownership_epoch if accepted else 0
    )
    owned = accepted is not None and accepted.ownership_id == cycle["_id"]
    pending_claim = (
        previous
        and previous["boot_id"] == state.boot_id
        and previous["mode"] == "off"
        and previous["ownership_epoch"] > (accepted.ownership_epoch if accepted else 0)
    )
    if not owned and not pending_claim:
        epoch += 1
    sequence = (
        max(
            previous["sequence"] if previous and previous["ownership_epoch"] == epoch else 0,
            accepted.sequence if accepted and accepted.ownership_epoch == epoch else 0,
        )
        + 1
    )
    return ControlCommand(
        boot_id=state.boot_id,
        command_id=str(uuid4()),
        ownership_epoch=epoch,
        ownership_id=cycle["_id"],
        sequence=sequence,
        mode=mode,
        config_revision=configuration["revision"],
        timeout_seconds=configuration["communication_timeout_seconds"],
    )


def observe(control: dict[str, Any], state: DeviceState) -> None:
    control.update(
        actual_mode=state.actual_mode,
        confirmed_at=state.confirmed_at,
        device_id=state.device_id,
        error=None,
    )


def finish_observation(
    db: Database[dict[str, Any]],
    cycle: dict[str, Any],
    control: dict[str, Any],
    state: DeviceState,
) -> None:
    command = ControlCommand.model_validate(control["command"]) if control.get("command") else None
    confirmed = command_confirmed(state, command)
    released = cycle["status"] == "concluded" and control["desired_mode"] == "off" and confirmed
    if released:
        control.update(status="stopped", reason="Spegnimento confermato.")
    elif cycle["status"] == "concluded":
        control.update(status="stopping", reason="Spegnimento in attesa di conferma.")
    elif control["reason"] is None:
        control["status"] = (
            ("heating" if control["desired_mode"] == "heating" else "idle")
            if confirmed
            else "pending"
        )
    save_control(db, cycle, control, released=released)


def request_off_after_failure(
    db: Database[dict[str, Any]],
    cycle: dict[str, Any],
    control: dict[str, Any],
    client: ThermalDeviceClient,
    configuration: dict[str, Any],
    error: ActuatorError,
) -> None:
    control.update(
        status="stopping" if cycle["status"] == "concluded" else "suspended",
        desired_mode="off",
        actual_mode=None,
        confirmed_at=None,
        needs_off=True,
        error=str(error),
        reason="Comunicazione del heater non confermata; richiesto OFF.",
    )
    previous = control.get("command")
    if previous is None:
        save_control(db, cycle, control)
        return  # No observed boot identity: reconcile before issuing a command.
    command = ControlCommand.model_validate(previous)
    if command.mode != "off" or command.config_revision != configuration["revision"]:
        command = command.model_copy(
            update={
                "command_id": str(uuid4()),
                "sequence": command.sequence + 1,
                "mode": "off",
                "config_revision": configuration["revision"],
                "timeout_seconds": configuration["communication_timeout_seconds"],
            }
        )
    control["command"] = command.model_dump()
    saved = save_control(db, cycle, control)
    if saved is None:
        return
    try:
        state = client.control(command)
        if (
            state.boot_id != command.boot_id
            or state.device_id != control.get("device_id")
            or state.capability != "heating"
        ):
            raise ActuatorError("Conferma OFF riferita a un altro dispositivo o avvio.")
        observe(control, state)
        control.update(error=str(error), last_sent_at=datetime.now(UTC))
        finish_observation(db, saved, control, state)
    except ActuatorError as failure:
        control["error"] = str(failure)
        save_control(db, saved, control)


def reconcile_cycle(db: Database[dict[str, Any]], identifier: str) -> None:
    cycle = db.fermentations.find_one({"_id": identifier, "heater_reserved": True})
    if cycle is None:
        return
    device = db.thermal_devices.find_one({"_id": cycle["heater_id"]})
    if device is None:
        return
    configuration = timeout_configuration(db)
    timeout = configuration["communication_timeout_seconds"]
    control = dict(cycle["regulation"])
    client = ThermalDeviceClient(device["base_url"])
    try:
        state = client.read_state()
        if state.capability != "heating" or (
            control.get("device_id") and control["device_id"] != state.device_id
        ):
            raise ActuatorError("Identità o capacità del heater discordanti.")
        previous = (
            ControlCommand.model_validate(control["command"]) if control.get("command") else None
        )
        accepted = state.accepted_command
        owned = accepted is not None and accepted.ownership_id == identifier
        if (
            not owned
            or previous is None
            or previous.boot_id != state.boot_id
            or state.application_status in {"unknown", "timed_out"}
        ):
            control["needs_off"] = True
        elif previous.mode == "off" and command_confirmed(state, previous):
            control["needs_off"] = False
        value, data_status, reason = usable_temperature(db, cycle, timeout)
        mode: Mode = "off"
        control["reason"] = reason
        if cycle["status"] == "concluded":
            control.update(
                status="stopping", reason="Spegnimento in attesa di conferma.", needs_off=True
            )
        elif data_status is not None:
            control.update(
                status=data_status,
                needs_off=True,
            )
        elif control["needs_off"]:
            control.update(
                status="suspended", reason="In attesa della conferma OFF prima della ripresa."
            )
        elif value is not None and (
            value <= cycle["temperature_min"]
            or (
                value < cycle["temperature_min"] + cycle["hysteresis"]
                and state.actual_mode == "heating"
            )
        ):
            mode = "heating"
        control["desired_mode"] = mode
        observe(control, state)
        interval = min(5.0, timeout / 3)
        due = (
            control["last_sent_at"] is None
            or (datetime.now(UTC) - control["last_sent_at"]).total_seconds() >= interval
        )
        compatible = (
            previous is not None
            and previous.boot_id == state.boot_id
            and previous.mode == mode
            and previous.config_revision == configuration["revision"]
            and previous.timeout_seconds == timeout
        )
        if (
            compatible
            and not command_confirmed(state, previous)
            and state.application_status != "timed_out"
        ):
            command = previous
        elif not compatible or due or state.application_status == "timed_out":
            command = make_command(cycle, state, mode, configuration)
        else:
            finish_observation(db, cycle, control, state)
            return
        assert command is not None
        control["command"] = command.model_dump()
        saved = save_control(db, cycle, control)
        if saved is None:
            return
        cycle = saved
        if (
            db.fermentations.find_one(
                {
                    "_id": identifier,
                    "control_revision": cycle["control_revision"],
                    "heater_reserved": True,
                }
            )
            is None
        ):
            return
        response = client.control(command)
        if (
            response.boot_id != command.boot_id
            or response.device_id != state.device_id
            or response.capability != "heating"
        ):
            raise ActuatorError("Conferma riferita a un altro dispositivo o avvio.")
        observe(control, response)
        control["last_sent_at"] = datetime.now(UTC)
        finish_observation(db, cycle, control, response)
    except ActuatorError as error:
        request_off_after_failure(db, cycle, control, client, configuration, error)


async def regulate_heating(db: Database[dict[str, Any]]) -> None:
    jobs: dict[str, asyncio.Task[None]] = {}

    async def reconcile(identifier: str) -> None:
        while True:
            try:
                reserved = await asyncio.to_thread(
                    db.fermentations.find_one, {"_id": identifier, "heater_reserved": True}
                )
                if reserved is None:
                    return
                await asyncio.to_thread(reconcile_cycle, db, identifier)
            except PyMongoError as error:
                logger.warning("Heating regulation unavailable: %s", error)
            await asyncio.sleep(0.05)

    try:
        while True:
            for identifier, job in list(jobs.items()):
                if job.done():
                    del jobs[identifier]
                    try:
                        job.result()
                    except Exception:
                        logger.exception("Heating reconciliation failed for %s", identifier)
            try:
                identifiers = await asyncio.to_thread(
                    lambda: [
                        d["_id"]
                        for d in db.fermentations.find({"heater_reserved": True}, {"_id": True})
                    ]
                )
                for identifier in identifiers:
                    if identifier not in jobs:
                        jobs[identifier] = asyncio.create_task(reconcile(identifier))
            except PyMongoError as error:
                logger.warning("Heating regulation unavailable: %s", error)
            await asyncio.sleep(0.1)
    finally:
        for job in jobs.values():
            job.cancel()
        await asyncio.gather(*jobs.values(), return_exceptions=True)

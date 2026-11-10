"""Coordinated thermal control with persistent commands and physical reconciliation."""

import asyncio
import copy
import logging
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import partial
from typing import Any, Literal
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError

from hackbrew.settings import timeout_configuration
from hackbrew.thermal_client import ActuatorError, ThermalDeviceClient
from hackbrew.thermal_contract import ControlCommand, DeviceState, Mode

logger = logging.getLogger(__name__)


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
    db: Database[dict[str, Any]], cycle: dict[str, Any], timeout: float
) -> tuple[float | None, Literal["waiting", "suspended"] | None, str | None]:
    latest = db.latest_reading.find_one({"_id": cycle["pill_id"]})
    if latest is None or latest.get("reading", {}).get("timestamp", -1) < cycle["started_at"]:
        return None, "waiting", "In attesa di temperatura utilizzabile."
    if (datetime.now(UTC) - latest["last_received_at"]).total_seconds() >= timeout:
        return None, "suspended", "Timeout di comunicazione della pillola superato."
    return float(latest["reading"]["temperature"]), None, None


def make_command(
    owner: str,
    control: dict[str, Any],
    state: DeviceState,
    mode: Mode,
    configuration: dict[str, Any],
) -> ControlCommand:
    previous = control.get("command")
    accepted = state.accepted_command
    epoch = max(
        previous["ownership_epoch"] if previous else 0, accepted.ownership_epoch if accepted else 0
    )
    owned = accepted is not None and accepted.ownership_id == owner
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
        ownership_id=owner,
        sequence=sequence,
        mode=mode,
        config_revision=configuration["revision"],
        timeout_seconds=configuration["communication_timeout_seconds"],
    )


def exchange_all(
    actions: dict[str, Callable[[], DeviceState]],
) -> dict[str, DeviceState | ActuatorError]:
    def exchange(action: Callable[[], DeviceState]) -> DeviceState | ActuatorError:
        try:
            return action()
        except ActuatorError as error:
            return error

    if not actions:
        return {}
    if len(actions) == 1:
        identifier, action = next(iter(actions.items()))
        return {identifier: exchange(action)}
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return dict(zip(actions, pool.map(exchange, actions.values()), strict=True))


class ThermalControl:
    """One atomic ownership/control snapshot coordinates all functions of a cycle."""

    def __init__(self, db: Database[dict[str, Any]], cycle: dict[str, Any]) -> None:
        self.db = db
        self.cycle = cycle
        self.configuration = timeout_configuration(db)
        self.control = copy.deepcopy(cycle["regulation"])
        self.assignments = {device["id"]: device for device in cycle["devices"]}
        self.active = list(cycle["reserved_device_ids"])
        fields = (
            "command",
            "last_sent_at",
            "desired_mode",
            "actual_mode",
            "confirmed_at",
            "error",
            "device_id",
            "reserved",
        )
        self.devices = {
            identifier: {
                key: value
                for key, value in self.control["devices"][identifier].items()
                if key in fields
            }
            for identifier in self.assignments
        }
        self.control["devices"] = self.devices
        self.clients: dict[str, ThermalDeviceClient] = {}
        self.states: dict[str, DeviceState] = {}
        self.errors: dict[str, str] = {}
        self.cancelled = False
        for identifier in self.active:
            device = db.thermal_devices.find_one({"_id": identifier})
            if device is not None:
                self.clients[identifier] = ThermalDeviceClient(device["base_url"])
            else:
                self.record_error(identifier, ActuatorError("Dispositivo termico non registrato."))

    def record_error(self, identifier: str, error: ActuatorError) -> None:
        self.errors[identifier] = str(error)
        self.states.pop(identifier, None)
        self.devices[identifier].update(actual_mode=None, confirmed_at=None, error=str(error))

    def observe(
        self, identifier: str, state: DeviceState, command: ControlCommand | None = None
    ) -> None:
        control = self.devices[identifier]
        if (
            state.capability != self.assignments[identifier]["capability"]
            or (control.get("device_id") and control["device_id"] != state.device_id)
            or (command is not None and state.boot_id != command.boot_id)
        ):
            raise ActuatorError("Identità, avvio o capacità del dispositivo discordanti.")
        self.states[identifier] = state
        self.errors.pop(identifier, None)
        control.update(
            actual_mode=state.actual_mode,
            confirmed_at=state.confirmed_at,
            device_id=state.device_id,
            error=None,
        )
        if state.actual_mode is None:
            self.errors[identifier] = "Conferma fisica del dispositivo indisponibile."
            control["error"] = self.errors[identifier]

    def read_devices(self) -> None:
        for identifier, result in exchange_all(
            {identifier: client.read_state for identifier, client in self.clients.items()}
        ).items():
            try:
                if isinstance(result, ActuatorError):
                    raise result
                self.observe(identifier, result)
            except ActuatorError as error:
                self.record_error(identifier, error)

    def persist(self, remaining: list[str] | None = None) -> bool:
        if self.cancelled:
            return False
        reserved = self.active if remaining is None else remaining
        if (
            self.control == self.cycle["regulation"]
            and reserved == self.cycle["reserved_device_ids"]
        ):
            return True
        document = self.db.fermentations.find_one_and_update(
            {
                "_id": self.cycle["_id"],
                "control_revision": self.cycle["control_revision"],
                "thermal_reserved": True,
            },
            {
                "$set": {
                    "regulation": self.control,
                    "reserved_device_ids": reserved,
                    "thermal_reserved": bool(reserved),
                    "heater_reserved": self.cycle.get("heater_id") in reserved,
                },
                "$inc": {"control_revision": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            self.cancelled = True
            return False
        self.cycle = document
        return True

    def next_command(self, identifier: str, mode: Mode) -> ControlCommand | None:
        control = self.devices[identifier]
        state = self.states.get(identifier)
        previous = (
            ControlCommand.model_validate(control["command"]) if control.get("command") else None
        )
        duration = self.configuration["communication_timeout_seconds"]
        compatible = (
            previous is not None
            and previous.mode == mode
            and previous.config_revision == self.configuration["revision"]
            and previous.timeout_seconds == duration
        )
        if state is None:
            if previous is None:
                return None
            if compatible:
                return previous
            return previous.model_copy(
                update={
                    "command_id": str(uuid4()),
                    "sequence": previous.sequence + 1,
                    "mode": "off",
                    "config_revision": self.configuration["revision"],
                    "timeout_seconds": duration,
                }
            )
        compatible = compatible and previous is not None and previous.boot_id == state.boot_id
        if compatible and state.accepted_command is not None and previous is not None:
            compatible = state.accepted_command.ownership_epoch <= previous.ownership_epoch and (
                state.accepted_command.ownership_epoch != previous.ownership_epoch
                or state.accepted_command.sequence <= previous.sequence
            )
        if (
            compatible
            and not command_confirmed(state, previous)
            and state.application_status != "timed_out"
        ):
            return previous
        due = control["last_sent_at"] is None or (
            datetime.now(UTC) - control["last_sent_at"]
        ).total_seconds() >= min(5.0, duration / 3)
        if not compatible or due or state.application_status == "timed_out":
            return make_command(self.cycle["_id"], control, state, mode, self.configuration)
        return None

    def send_modes(self, modes: Mapping[str, Mode]) -> bool:
        commands: dict[str, ControlCommand] = {}
        for identifier, mode in modes.items():
            self.devices[identifier]["desired_mode"] = mode
            command = self.next_command(identifier, mode)
            if command is not None and identifier in self.clients:
                self.devices[identifier]["command"] = command.model_dump()
                commands[identifier] = command
        if not self.persist():
            return False
        current = self.db.fermentations.find_one(
            {
                "_id": self.cycle["_id"],
                "control_revision": self.cycle["control_revision"],
                "thermal_reserved": True,
            }
        )
        if current is None:
            self.cancelled = True
            return False
        actions: dict[str, Callable[[], DeviceState]] = {
            identifier: partial(self.clients[identifier].control, command)
            for identifier, command in commands.items()
        }
        for identifier, result in exchange_all(actions).items():
            try:
                if isinstance(result, ActuatorError):
                    raise result
                self.observe(identifier, result, commands[identifier])
                self.devices[identifier]["last_sent_at"] = datetime.now(UTC)
            except ActuatorError as error:
                self.record_error(identifier, error)
        return not self.errors and not self.cancelled

    def all_off_confirmed(self) -> bool:
        return all(
            identifier in self.states
            and self.devices[identifier].get("command") is not None
            and self.devices[identifier]["command"]["mode"] == "off"
            and command_confirmed(
                self.states[identifier],
                ControlCommand.model_validate(self.devices[identifier]["command"]),
            )
            for identifier in self.active
        )

    def off_observed(self, identifier: str) -> bool:
        state = self.states.get(identifier)
        return bool(
            state is not None
            and state.actual_mode == "off"
            and (state.accepted_command is None or state.accepted_command.mode == "off")
        )

    def opposite_requested(self, identifier: str, opposite: str) -> bool:
        state = self.states[identifier]
        accepted = state.accepted_command
        previous = self.devices[identifier].get("command") or {}
        return (
            state.actual_mode == opposite
            or (accepted is not None and accepted.mode == opposite)
            or previous.get("mode") == opposite
        )

    def force_off(self, status: str, reason: str) -> None:
        self.control.update(desired_mode="off", needs_off=True, status=status, reason=reason)
        self.send_modes({identifier: "off" for identifier in self.active})

    def actual_mode(self) -> Mode | None:
        modes = [self.devices[identifier].get("actual_mode") for identifier in self.assignments]
        if any(mode is None for mode in modes):
            return None
        enabled = {mode for mode in modes if mode != "off"}
        if len(enabled) > 1:
            return None
        if "heating" in enabled:
            return "heating"
        if "cooling" in enabled:
            return "cooling"
        return "off"

    def finish(self) -> None:
        remaining = list(self.active)
        if self.cycle["status"] == "concluded":
            for identifier in self.active:
                command = self.devices[identifier].get("command")
                if (
                    identifier in self.states
                    and command is not None
                    and command["mode"] == "off"
                    and command_confirmed(
                        self.states[identifier], ControlCommand.model_validate(command)
                    )
                ):
                    remaining.remove(identifier)
            self.control.update(
                status="stopping" if remaining else "stopped",
                desired_mode="off",
                reason="Spegnimento in attesa di conferma."
                if remaining
                else "Spegnimento confermato.",
            )
        for identifier, control in self.devices.items():
            control["reserved"] = identifier in remaining
        actual = self.actual_mode()
        dates = [
            value
            for control in self.devices.values()
            if isinstance(value := control.get("confirmed_at"), datetime)
        ]
        self.control.update(
            actual_mode=actual,
            confirmed_at=min(dates)
            if actual is not None and len(dates) == len(self.devices)
            else None,
            error="; ".join(
                f"{self.assignments[identifier]['name']}: {error}"
                for identifier, error in self.errors.items()
            )
            or None,
        )
        if self.cycle["status"] == "active" and self.control["reason"] is None:
            confirmed = all(
                identifier in self.states
                and self.devices[identifier].get("command") is not None
                and command_confirmed(
                    self.states[identifier],
                    ControlCommand.model_validate(self.devices[identifier]["command"]),
                )
                for identifier in self.active
            )
            self.control["status"] = (
                (self.control["desired_mode"] if self.control["desired_mode"] != "off" else "idle")
                if confirmed
                else "pending"
            )
        if len(self.devices) == 1:
            single = next(iter(self.devices.values()))
            for key in ("command", "last_sent_at", "device_id"):
                self.control[key] = single.get(key)
        self.persist(remaining)

    def run(self) -> None:
        self.read_devices()
        for identifier in self.active:
            state = self.states.get(identifier)
            previous = self.devices[identifier].get("command")
            if (
                state is None
                or state.accepted_command is None
                or state.accepted_command.ownership_id != self.cycle["_id"]
                or previous is None
                or previous["boot_id"] != state.boot_id
                or state.application_status in {"unknown", "timed_out"}
            ):
                self.control["needs_off"] = True
        if self.all_off_confirmed():
            self.control["needs_off"] = False
        value, data_status, reason = usable_temperature(
            self.db, self.cycle, self.configuration["communication_timeout_seconds"]
        )
        if self.cycle["status"] == "concluded":
            self.force_off("stopping", "Spegnimento in attesa di conferma.")
        elif self.errors:
            self.force_off(
                "suspended", "Comunicazione dei dispositivi non confermata; richiesto OFF a tutti."
            )
        elif data_status is not None:
            self.force_off(data_status, reason or "Temperatura non disponibile.")
        elif self.control["needs_off"]:
            self.force_off("suspended", "In attesa della conferma OFF prima della ripresa.")
        else:
            actual = self.actual_mode()
            wanted: Mode = "off"
            assert value is not None
            heating = self.cycle["control_mode"] in {"heating", "heating_cooling", "combined"}
            cooling = self.cycle["control_mode"] in {"cooling", "heating_cooling", "combined"}
            if heating and (
                value <= self.cycle["temperature_min"]
                or (
                    actual == "heating"
                    and value < self.cycle["temperature_min"] + self.cycle["hysteresis"]
                )
            ):
                wanted = "heating"
            elif cooling and (
                value >= self.cycle["temperature_max"]
                or (
                    actual == "cooling"
                    and value > self.cycle["temperature_max"] - self.cycle["hysteresis"]
                )
            ):
                wanted = "cooling"
            opposite = "cooling" if wanted == "heating" else "heating"
            if wanted != "off" and any(
                self.opposite_requested(identifier, opposite) for identifier in self.active
            ):
                self.force_off(
                    "suspended", "In attesa della conferma OFF prima del cambio di funzione."
                )
                self.finish()
                return
            self.control.update(desired_mode=wanted, reason=None)
            targets: dict[str, Mode] = {
                identifier: wanted
                if self.assignments[identifier]["capability"] in {wanted, "both"}
                else "off"
                for identifier in self.active
            }
            off = {identifier: mode for identifier, mode in targets.items() if mode == "off"}
            on = {identifier: mode for identifier, mode in targets.items() if mode != "off"}
            successful = self.send_modes(off)
            if not successful or any(not self.off_observed(identifier) for identifier in off):
                self.force_off("suspended", "In attesa della conferma OFF; regolazione sospesa.")
            elif on and not self.send_modes(on):
                self.force_off("suspended", "Comando non confermato; richiesto OFF a tutti.")
        self.finish()


def reconcile_cycle(db: Database[dict[str, Any]], identifier: str) -> None:
    cycle = db.fermentations.find_one({"_id": identifier, "thermal_reserved": True})
    if cycle is not None:
        ThermalControl(db, cycle).run()


async def regulate_temperature(db: Database[dict[str, Any]]) -> None:
    jobs: dict[str, asyncio.Task[None]] = {}

    async def reconcile(identifier: str) -> None:
        while True:
            try:
                reserved = await asyncio.to_thread(
                    db.fermentations.find_one, {"_id": identifier, "thermal_reserved": True}
                )
                if reserved is None:
                    return
                await asyncio.to_thread(reconcile_cycle, db, identifier)
            except PyMongoError as error:
                logger.warning("Thermal regulation unavailable: %s", error)
            await asyncio.sleep(0.05)

    try:
        while True:
            for identifier, job in list(jobs.items()):
                if job.done():
                    del jobs[identifier]
                    try:
                        job.result()
                    except Exception:
                        logger.exception("Thermal reconciliation failed for %s", identifier)
            try:
                identifiers = await asyncio.to_thread(
                    lambda: [
                        d["_id"]
                        for d in db.fermentations.find({"thermal_reserved": True}, {"_id": True})
                    ]
                )
                for identifier in identifiers:
                    if identifier not in jobs:
                        jobs[identifier] = asyncio.create_task(reconcile(identifier))
            except PyMongoError as error:
                logger.warning("Thermal regulation unavailable: %s", error)
            await asyncio.sleep(0.1)
    finally:
        for job in jobs.values():
            job.cancel()
        await asyncio.gather(*jobs.values(), return_exceptions=True)

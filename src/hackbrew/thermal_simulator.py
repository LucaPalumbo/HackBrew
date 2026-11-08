"""Standalone development simulator; never mounted in the HackBrew application."""

import asyncio
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from hackbrew.thermal_contract import (
    AppliedTimeoutConfiguration,
    Capability,
    ControlCommand,
    DeviceState,
    Mode,
    TimeoutConfiguration,
)


class SimulationSettings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    state_http_status: Literal[200, 503] = 200
    control_http_status: Literal[200, 503] = 200
    state_delay_seconds: FiniteFloat = Field(default=0, ge=0, le=10)
    control_delay_seconds: FiniteFloat = Field(default=0, ge=0, le=10)
    apply_delay_seconds: FiniteFloat = Field(default=0, ge=0, le=10)
    confirmation_available: bool = True
    malformed_state: bool = False


class Simulator:
    def __init__(self, capability: Capability, device_id: str) -> None:
        self.capability = capability
        self.device_id = device_id
        self.boot_id = str(uuid4())
        self.accepted: ControlCommand | None = None
        self.commands: dict[str, ControlCommand] = {}
        self.actual_mode: Mode = "off"
        self.applied_command_id: str | None = None
        self.applied_timeout = 10800.0
        self.applied_revision = 0
        self.confirmed_at = datetime.now(UTC)
        self.last_command_at: datetime | None = None
        self.last_valid_time: float | None = None
        self.expired = False
        self.settings = SimulationSettings()
        self.pending: tuple[ControlCommand, float] | None = None
        self.ready_epoch: int | None = None
        self.configuration_command: TimeoutConfiguration | None = None
        self.applied_configuration: AppliedTimeoutConfiguration | None = None
        self.pending_configuration: tuple[TimeoutConfiguration, float] | None = None
        self.configuration_ids: set[str] = set()

    def state(self) -> DeviceState:
        return DeviceState(
            protocol_version=1,
            device_id=self.device_id,
            boot_id=self.boot_id,
            capability=self.capability,
            desired_mode=self.accepted.mode if self.accepted else "off",
            actual_mode=self.actual_mode if self.settings.confirmation_available else None,
            application_status=(
                "unknown"
                if not self.settings.confirmation_available
                else "timed_out"
                if self.expired
                else "pending"
                if self.pending is not None
                else "applied"
            ),
            accepted_command=self.accepted,
            applied_command_id=self.applied_command_id,
            applied_timeout_seconds=self.applied_timeout,
            applied_config_revision=self.applied_revision,
            confirmed_at=self.confirmed_at if self.settings.confirmation_available else None,
            last_command_at=self.last_command_at,
            lease_expires_at=(self.last_command_at.timestamp() + self.applied_timeout)
            if self.last_command_at
            else None,
            configuration_command=self.configuration_command,
            applied_configuration=self.applied_configuration
            if self.settings.confirmation_available
            else None,
        )

    def control(self, command: ControlCommand) -> DeviceState:
        if command.boot_id != self.boot_id:
            raise HTTPException(
                409, "Obsolete device boot; read state before issuing a new command."
            )
        if command.mode != "off" and self.capability not in {"both", command.mode}:
            raise HTTPException(422, "Mode not supported by this device.")
        previous = self.accepted
        if previous:
            if command.ownership_epoch < previous.ownership_epoch:
                raise HTTPException(409, "Obsolete ownership epoch.")
            if command.ownership_epoch == previous.ownership_epoch:
                if command.ownership_id != previous.ownership_id:
                    raise HTTPException(409, "Ownership identity conflicts with the current epoch.")
                if command.sequence <= previous.sequence:
                    if command == previous:
                        return self.state()
                    raise HTTPException(409, "Obsolete or conflicting command sequence.")
        if command.command_id in self.commands or command.command_id in self.configuration_ids:
            raise HTTPException(409, "Command identity already used.")
        if command.mode != "off" and self.ready_epoch != command.ownership_epoch:
            raise HTTPException(409, "Wait for confirmed off before enabling this ownership epoch.")
        revision = previous.config_revision if previous else self.applied_revision
        timeout = previous.timeout_seconds if previous else self.applied_timeout
        if (
            self.configuration_command is not None
            and self.configuration_command.config_revision >= revision
        ):
            revision = self.configuration_command.config_revision
            timeout = self.configuration_command.timeout_seconds
        if command.config_revision < revision or (
            command.config_revision == revision and command.timeout_seconds != timeout
        ):
            raise HTTPException(409, "Obsolete or conflicting timeout configuration revision.")
        self.accepted = command
        self.commands[command.command_id] = command
        self.last_command_at = datetime.now(UTC)
        self.last_valid_time = time.monotonic()
        self.expired = False
        self.pending_configuration = None
        self.configuration_command = None
        self.pending = (command, self.last_valid_time + self.settings.apply_delay_seconds)
        if self.settings.apply_delay_seconds == 0:
            self.apply(command)
        return self.state()

    def apply(self, command: ControlCommand) -> None:
        self.pending = None
        if command.config_revision >= self.applied_revision:
            self.applied_timeout = command.timeout_seconds
            self.applied_revision = command.config_revision
            self.applied_configuration = None
        # Delayed physical application never starts an already expired ON lease.
        if (
            self.last_valid_time is not None
            and time.monotonic() - self.last_valid_time >= self.applied_timeout
        ):
            self.expire()
            return
        self.actual_mode = command.mode
        self.applied_command_id = command.command_id
        self.confirmed_at = datetime.now(UTC)
        if command.mode == "off":
            self.ready_epoch = command.ownership_epoch

    def expire(self) -> None:
        self.expired = True
        self.pending = None
        self.actual_mode = "off"
        self.confirmed_at = datetime.now(UTC)

    def tick(self) -> None:
        if (
            self.pending_configuration is not None
            and time.monotonic() >= self.pending_configuration[1]
        ):
            self.apply_configuration(self.pending_configuration[0])
        if (
            self.last_valid_time is not None
            and not self.expired
            and time.monotonic() - self.last_valid_time >= self.applied_timeout
        ):
            self.expire()
        if self.pending is not None and time.monotonic() >= self.pending[1]:
            self.apply(self.pending[0])

    def configure_timeout(self, command: TimeoutConfiguration) -> DeviceState:
        identifier = self.accepted.command_id if self.accepted else None
        if command.boot_id != self.boot_id or command.expected_control_id != identifier:
            raise HTTPException(409, "Device boot/control changed; reconcile before configuring.")
        if command == self.configuration_command:
            return self.state()
        previous = self.configuration_command or self.accepted
        revision = previous.config_revision if previous else self.applied_revision
        timeout = previous.timeout_seconds if previous else self.applied_timeout
        if command.config_revision < revision or (
            command.config_revision == revision and command.timeout_seconds != timeout
        ):
            raise HTTPException(409, "Obsolete or conflicting configuration revision.")
        if command.command_id in self.configuration_ids or command.command_id in self.commands:
            raise HTTPException(409, "Configuration identity already used.")
        self.configuration_command = command
        self.configuration_ids.add(command.command_id)
        self.pending_configuration = (command, time.monotonic() + self.settings.apply_delay_seconds)
        if self.settings.apply_delay_seconds == 0:
            self.apply_configuration(command)
        return self.state()

    def apply_configuration(self, command: TimeoutConfiguration) -> None:
        self.pending_configuration = None
        identifier = self.accepted.command_id if self.accepted else None
        if command.boot_id != self.boot_id or command.expected_control_id != identifier:
            return
        self.applied_timeout = command.timeout_seconds
        self.applied_revision = command.config_revision
        self.applied_configuration = AppliedTimeoutConfiguration(
            **command.model_dump(), confirmed_at=datetime.now(UTC)
        )
        # Configuration does not renew contact, clear an expiry or reactivate a mode.


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    capability = os.environ.get("THERMAL_SIM_CAPABILITY", "both")
    if capability not in {"heating", "cooling", "both"}:
        raise ValueError("THERMAL_SIM_CAPABILITY must be heating, cooling or both")
    application.state.simulator = Simulator(
        cast(Capability, capability), os.environ.get("THERMAL_SIM_DEVICE_ID", "demo-thermal")
    )

    async def watchdog() -> None:
        while True:
            cast(Simulator, application.state.simulator).tick()
            await asyncio.sleep(0.02)

    task = asyncio.create_task(watchdog())
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


app = FastAPI(title="HackBrew thermal device simulator", lifespan=lifespan)


def simulator(request: Request) -> Simulator:
    return cast(Simulator, request.app.state.simulator)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/state", response_model=DeviceState)
async def state(request: Request) -> DeviceState | JSONResponse:
    device = simulator(request)
    snapshot = device.state()
    settings = device.settings
    await asyncio.sleep(settings.state_delay_seconds)
    if settings.state_http_status != 200:
        raise HTTPException(settings.state_http_status, "Simulated status failure.")
    if settings.malformed_state:
        return JSONResponse({"actual_mode": "off"})
    return snapshot


@app.put("/api/v1/control")
async def control(command: ControlCommand, request: Request) -> DeviceState:
    settings = simulator(request).settings
    await asyncio.sleep(settings.control_delay_seconds)
    if settings.control_http_status != 200:
        raise HTTPException(settings.control_http_status, "Simulated command failure.")
    return simulator(request).control(command)


@app.put("/api/v1/configuration")
async def configuration(command: TimeoutConfiguration, request: Request) -> DeviceState:
    settings = simulator(request).settings
    await asyncio.sleep(settings.control_delay_seconds)
    if settings.control_http_status != 200:
        raise HTTPException(settings.control_http_status, "Simulated configuration failure.")
    return simulator(request).configure_timeout(command)


@app.post("/__simulation/reset")
async def reset(request: Request) -> DeviceState:
    previous = simulator(request)
    request.app.state.simulator = Simulator(previous.capability, previous.device_id)
    return simulator(request).state()


@app.patch("/__simulation")
async def configure(settings: SimulationSettings, request: Request) -> SimulationSettings:
    device = simulator(request)
    device.settings = device.settings.model_copy(update=settings.model_dump(exclude_unset=True))
    return device.settings

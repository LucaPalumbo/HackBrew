"""Provisional, versioned HTTP contract shared with the actuator simulator."""

from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Capability = Literal["heating", "cooling", "both"]
Mode = Literal["off", "heating", "cooling"]


class ControlCommand(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    boot_id: str = Field(min_length=1, max_length=128)
    command_id: str = Field(min_length=1, max_length=128)
    ownership_epoch: int = Field(ge=1)
    ownership_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1)
    mode: Mode
    timeout_seconds: FiniteFloat = Field(default=10800, gt=0)
    config_revision: int = Field(ge=0)


class DeviceState(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    protocol_version: Literal[1]
    device_id: str = Field(min_length=1)
    boot_id: str = Field(min_length=1)
    capability: Capability
    desired_mode: Mode
    actual_mode: Mode | None
    application_status: Literal["applied", "pending", "unknown", "timed_out"]
    accepted_command: ControlCommand | None
    applied_command_id: str | None
    applied_timeout_seconds: FiniteFloat = Field(gt=0)
    applied_config_revision: int = Field(ge=0)
    confirmed_at: AwareDatetime | None
    last_command_at: AwareDatetime | None
    lease_expires_at: FiniteFloat | None

    @model_validator(mode="after")
    def consistent_confirmation(self) -> Self:
        supported = (
            {"off", "heating", "cooling"} if self.capability == "both" else {"off", self.capability}
        )
        if self.actual_mode not in supported | {None} or self.desired_mode not in supported:
            raise ValueError("Device reports an unsupported mode")
        if (self.actual_mode is None) != (self.confirmed_at is None):
            raise ValueError("Actual state and physical confirmation must be present together")
        if self.application_status == "unknown" and self.actual_mode is not None:
            raise ValueError("Unknown physical state must not claim an actual mode")
        if self.application_status != "unknown" and self.actual_mode is None:
            raise ValueError("Missing physical confirmation")
        command = self.accepted_command
        if command is not None:
            if command.boot_id != self.boot_id or command.mode != self.desired_mode:
                raise ValueError("Accepted command belongs to another state")
            if self.last_command_at is None or self.lease_expires_at is None:
                raise ValueError("Accepted command requires its communication deadline")
        if self.application_status == "applied":
            if self.actual_mode != self.desired_mode:
                raise ValueError("Acceptance is not confirmation of physical application")
            if command is not None and (
                self.applied_command_id != command.command_id
                or self.applied_timeout_seconds != command.timeout_seconds
                or self.applied_config_revision != command.config_revision
            ):
                raise ValueError("Command/configuration has not been physically confirmed")
        if self.application_status == "timed_out" and self.actual_mode != "off":
            raise ValueError("Expired communication requires confirmed off")
        return self

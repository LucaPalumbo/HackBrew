"""Public input contracts for measurements and fermentazioni."""

import re
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    field_validator,
    model_validator,
)


def normalize_mac(value: str) -> str:
    value = value.strip()
    if not any(
        re.fullmatch(pattern, value)
        for pattern in (
            r"[0-9a-fA-F]{12}",
            r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}",
            r"(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}",
        )
    ):
        raise ValueError("Inserisci un MAC Bluetooth valido, per esempio AA:BB:CC:DD:EE:FF.")
    digits = value.replace(":", "").replace("-", "").upper()
    return ":".join(digits[index : index + 2] for index in range(0, 12, 2))


BluetoothMac = Annotated[str, AfterValidator(normalize_mac)]


class PillRegistration(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    mac: BluetoothMac


class FermentationStart(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1)
    pill_id: str = Field(min_length=1)
    control_mode: Literal["monitor_only", "heating"] = "monitor_only"
    heater_id: str | None = Field(default=None, min_length=1)
    temperature_min: FiniteFloat | None = Field(default=None, ge=-273.15)
    temperature_max: FiniteFloat | None = Field(default=None, ge=-273.15)
    hysteresis: FiniteFloat | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def valid_heating_settings(self) -> Self:
        settings = (self.heater_id, self.temperature_min, self.temperature_max, self.hysteresis)
        if self.control_mode == "monitor_only":
            if any(value is not None for value in settings):
                raise ValueError("Solo monitoraggio non richiede dispositivi o soglie termiche.")
        elif any(value is None for value in settings):
            raise ValueError("Seleziona un heater e imposta minimo, massimo e isteresi.")
        else:
            assert self.temperature_min is not None
            assert self.temperature_max is not None
            assert self.hysteresis is not None
            if (
                self.temperature_min >= self.temperature_max
                or self.temperature_min + self.hysteresis > self.temperature_max
            ):
                raise ValueError(
                    "Minimo inferiore al massimo e spegnimento entro la fascia richiesti."
                )
        return self


class GatewayReading(BaseModel):
    model_config = ConfigDict(strict=True)

    pill_mac: BluetoothMac
    temperature: FiniteFloat = Field(ge=-273.15)
    specific_gravity: FiniteFloat = Field(gt=0)
    battery: FiniteFloat = Field(ge=0, le=100)
    timestamp: FiniteFloat = Field(ge=0)
    valid: bool | None = None
    gravity_velocity: FiniteFloat | None = None
    accel_x: FiniteFloat | None = None
    accel_y: FiniteFloat | None = None
    accel_z: FiniteFloat | None = None

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_representable(cls, value: float) -> float:
        try:
            datetime.fromtimestamp(value, UTC)
        except (OverflowError, OSError, ValueError):
            raise ValueError("L'istante di acquisizione non è rappresentabile.") from None
        return value

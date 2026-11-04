"""Public input contracts for measurements and fermentazioni."""

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, FiniteFloat, field_validator


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
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    pill_id: str = Field(min_length=1)


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

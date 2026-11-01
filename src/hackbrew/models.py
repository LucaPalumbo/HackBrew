"""The gateway's measurement contract."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator


class GatewayReading(BaseModel):
    model_config = ConfigDict(strict=True)

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

"""Replaceable adapter for the provisional external actuator HTTP endpoints."""

import json
from http.client import HTTPException as HTTPProtocolError
from urllib.request import Request, urlopen

from hackbrew.thermal_contract import ControlCommand, DeviceState


class ActuatorError(Exception):
    """Communication or protocol failed; no physical state can be inferred."""


class ThermalDeviceClient:
    def __init__(self, base_url: str, timeout_seconds: float = 2) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def read_state(self) -> DeviceState:
        return self._exchange("GET", "/api/v1/state")

    def control(self, command: ControlCommand) -> DeviceState:
        return self._exchange("PUT", "/api/v1/control", command)

    def _exchange(
        self, method: str, path: str, command: ControlCommand | None = None
    ) -> DeviceState:
        data = json.dumps(command.model_dump(mode="json")).encode() if command else None
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read(65537)
            if len(body) > 65536:
                raise ActuatorError("Risposta del dispositivo troppo grande.")
        except (OSError, HTTPProtocolError) as error:
            raise ActuatorError(f"Verifica HTTP fallita: {error}.") from error
        try:
            return DeviceState.model_validate_json(body)
        except ValueError as error:
            raise ActuatorError(
                "Risposta non compatibile con il protocollo del dispositivo."
            ) from error

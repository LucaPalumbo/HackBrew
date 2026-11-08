"""HTTP clients for the simulator's external protocol and simulation controls."""

import json
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4

import httpx


@contextmanager
def thermal_simulator(capability: str = "both") -> Iterator[httpx.Client]:
    with httpx.Client(base_url=f"http://thermal-{capability}:8000", timeout=5) as client:
        client.post("/__simulation/reset").raise_for_status()
        try:
            yield client
        finally:
            client.post("/__simulation/reset").raise_for_status()


def claim_command(simulator: httpx.Client, **changes: Any) -> dict[str, Any]:
    state = simulator.get("/api/v1/state").json()
    return {
        "boot_id": state["boot_id"],
        "command_id": str(uuid4()),
        "ownership_epoch": 1,
        "ownership_id": "fermentation-ipa",
        "sequence": 1,
        "mode": "off",
        "config_revision": 0,
        **changes,
    }


@contextmanager
def malformed_http_device(state: dict[str, Any]) -> Iterator[tuple[str, threading.Event]]:
    """External wire fixture: change a valid response into broken chunk framing."""
    fault = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            if fault.is_set():
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(b"not-a-chunk-size\r\n")
                self.close_connection = True
            else:
                body = json.dumps(state).encode()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = socket.gethostbyname(socket.gethostname())
    try:
        yield f"http://{address}:{server.server_port}", fault
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@contextmanager
def discordant_configuration_device(
    simulator: httpx.Client,
) -> Iterator[tuple[str, threading.Event]]:
    """HTTP fault proxy: stale reads and coherent acknowledgements for a different boot."""
    initial = simulator.get("/api/v1/state").json()
    fault = threading.Event()
    fault.set()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if fault.is_set():
                self.reply(initial)
            else:
                self.reply(simulator.get(self.path).json())

        def do_PUT(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            response = simulator.put(
                self.path, content=body, headers={"Content-Type": "application/json"}
            )
            payload = response.json()
            if response.status_code == 200 and fault.is_set():
                payload["boot_id"] = "different-boot"
                for key in ("configuration_command", "applied_configuration", "accepted_command"):
                    if payload.get(key) is not None:
                        payload[key]["boot_id"] = "different-boot"
            self.reply(payload, response.status_code)

        def reply(self, payload: dict[str, Any], status: int = 200) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = socket.gethostbyname(socket.gethostname())
    try:
        yield f"http://{address}:{server.server_port}", fault
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

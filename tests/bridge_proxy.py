"""Controllable HTTP boundary; successful requests reach the real HackBrew app."""

import threading
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx


class BridgeProxy:
    def __init__(self, upstream: str) -> None:
        self.registry_response: bytes | None = None
        self.registry_status = 200
        self.telemetry_status = 200
        self.telemetry_delay = 0.0
        self.deliveries: list[bytes] = []
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if proxy.registry_response is not None or proxy.registry_status != 200:
                    self.reply(proxy.registry_status, proxy.registry_response or b"{}")
                else:
                    self.forward("GET")

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                proxy.deliveries.append(body)
                status, delay = proxy.telemetry_status, proxy.telemetry_delay
                if delay:
                    time.sleep(delay)
                if status != 200 or delay:
                    # A timed-out request is never forwarded after a mode change.
                    self.reply(status if status != 200 else 504, b"{}")
                else:
                    self.forward("POST", body)

            def forward(self, method: str, body: bytes | None = None) -> None:
                with httpx.Client(base_url=upstream, timeout=5) as client:
                    response = client.request(
                        method,
                        self.path,
                        content=body,
                        headers={"Content-Type": "application/json"},
                    )
                self.reply(response.status_code, response.content)

            def reply(self, status: int, body: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                # The bridge may already have observed its HTTP timeout.
                with suppress(BrokenPipeError):
                    self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

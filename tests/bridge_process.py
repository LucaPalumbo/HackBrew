"""Drive the real gateway executable at its hardware-free advertisement input."""

import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


class BridgeProcess:
    def __init__(self, directory: Path, base_url: str, *, interval: float = 0.15) -> None:
        config = directory / "bridge.json"
        config.write_text(
            json.dumps(
                {
                    "registry": {
                        "url": base_url + "/api/bridge/pills",
                        "poll_interval_seconds": interval,
                        "timeout_seconds": 1,
                    },
                    "http": {"url": base_url + "/telemetry", "timeout_seconds": 1},
                }
            )
        )
        self.process = subprocess.Popen(
            [
                sys.executable,
                "/opt/rapt-gateway/main.py",
                "--config",
                str(config),
                "--replay",
                "-",
                "--log-level",
                "DEBUG",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=directory,
        )
        self.lines: queue.Queue[str] = queue.Queue()
        self.output: list[str] = []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.put(line.rstrip())

    def wait_message(self, text: str, timeout: float = 10) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self.lines.get(timeout=max(0.001, deadline - time.monotonic()))
            except queue.Empty:
                break
            self.output.append(line)
            if text in line:
                return line
        raise AssertionError(f"Missing bridge message {text!r}: {self.output}")

    def advertise(self, mac: str, payload: str) -> None:
        # Bleak reports manufacturer ID separately, as a little-endian integer.
        frame: dict[str, Any] = {
            "address": mac,
            "manufacturer_data": {"16722": payload},
        }
        self.send_frame(frame)

    def send_frame(self, frame: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(frame) + "\n")
        self.process.stdin.flush()

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.reader.join(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                stream.close()


def advertisement_fixture(name: str) -> str:
    fixtures = json.loads(Path("/opt/rapt-gateway/fixtures/rapt-v2.json").read_text())
    return str(fixtures[name])

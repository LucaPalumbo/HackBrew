"""Observe synchronization exclusively through the public settings API."""

import time
from typing import Any

import httpx


def wait_for_sync(
    api: httpx.Client, identifier: str, status: str = "confirmed", revision: int | None = None
) -> dict[str, Any]:
    deadline = time.monotonic() + 15
    observed: dict[str, Any] = {}
    while time.monotonic() < deadline:
        entries = api.get("/api/settings").json()["devices"]
        observed = next(entry for entry in entries if entry["id"] == identifier)
        if observed["status"] == status and (
            revision is None or observed["applied_revision"] == revision
        ):
            return observed
        time.sleep(0.05)
    raise AssertionError(f"Synchronization did not reach {status}: {observed}")

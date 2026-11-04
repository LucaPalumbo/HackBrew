"""One concurrent-start winner per pillola through the public HTTP API."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from tests.payloads import fermentation_payload


def assert_single_concurrent_start(api: httpx.Client) -> dict[str, Any]:
    pill_id = fermentation_payload(api, "")["pill_id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(
                lambda number: api.post(
                    "/api/fermentations", json={"name": f"IPA {number}", "pill_id": pill_id}
                ),
                range(8),
            )
        )
    assert [response.status_code for response in responses].count(201) == 1
    assert [response.status_code for response in responses].count(409) == 7
    winner: dict[str, Any] = next(
        response.json()["fermentation"] for response in responses if response.status_code == 201
    )
    assert winner in api.get("/api/fermentations/active").json()["fermentations"]
    return winner

import os
from collections.abc import Iterator

import httpx
import pytest

from tests.database import reset_test_database
from tests.payloads import register_test_pill


@pytest.fixture
def empty_api() -> Iterator[httpx.Client]:
    reset_test_database()
    with httpx.Client(base_url=os.environ["HACKBREW_BASE_URL"], timeout=10) as client:
        yield client


@pytest.fixture
def api(empty_api: httpx.Client) -> httpx.Client:
    register_test_pill(empty_api)
    return empty_api

import os
from collections.abc import Iterator

import httpx
import pytest

from tests.database import reset_test_database


@pytest.fixture
def api() -> Iterator[httpx.Client]:
    reset_test_database()
    with httpx.Client(base_url=os.environ["HACKBREW_BASE_URL"], timeout=10) as client:
        yield client

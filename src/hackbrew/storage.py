"""Access to the application's MongoDB database."""

from typing import Any, cast

from fastapi import Request
from pymongo.database import Database


def database(request: Request) -> Database[dict[str, Any]]:
    return cast(Database[dict[str, Any]], request.app.state.database)

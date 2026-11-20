"""Access to the application's MongoDB database."""

from collections.abc import Callable
from typing import Any, cast

from fastapi import Request
from pymongo import timeout
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern


def database(request: Request) -> Database[dict[str, Any]]:
    return cast(Database[dict[str, Any]], request.app.state.database)


def registry_transaction[T](
    db: Database[dict[str, Any]], action: Callable[[ClientSession], T]
) -> T:
    """Retry registry write conflicts within the HTTP request's time budget."""
    with timeout(5), db.client.start_session() as session:
        return session.with_transaction(
            action,
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
            max_commit_time_ms=2000,
        )

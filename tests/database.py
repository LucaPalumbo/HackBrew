"""Cleanup confined to the isolated test database, preserving application indexes."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database


@contextmanager
def isolated_database() -> Iterator[Database[dict[str, Any]]]:
    name = os.environ["MONGODB_DATABASE"]
    if name != "hackbrew_test":
        raise RuntimeError("Cleanup requires the isolated hackbrew_test database")
    with MongoClient[dict[str, Any]](os.environ["MONGODB_URI"]) as mongo:
        yield mongo[name]


def reset_test_database() -> None:
    with isolated_database() as db:
        for collection in db.list_collection_names():
            db[collection].delete_many({})


def arrange_single_active_index() -> None:
    """Arrange the #9 constraint; the upgrade is verified through public HTTP."""
    with isolated_database() as db:
        db.fermentations.create_index(
            "status",
            name="one_active_fermentation",
            unique=True,
            partialFilterExpression={"status": "active"},
        )
        db.fermentations.drop_index("one_active_fermentation_per_pill")


def arrange_heating_v16(identifier: str, heater_identifier: str) -> None:
    """Prepare the previous persisted format; verify its upgrade through HTTP after restart."""
    with isolated_database() as db:
        db.fermentations.update_one(
            {"_id": identifier, "control_mode": "heating"},
            [
                {
                    "$set": {
                        "regulation": {
                            "$mergeObjects": [
                                "$regulation",
                                {
                                    "$getField": {
                                        "field": heater_identifier,
                                        "input": "$regulation.devices",
                                    }
                                },
                            ]
                        },
                        "control_revision": {"$add": ["$control_revision", 1]},
                    }
                },
                {
                    "$unset": [
                        "devices",
                        "reserved_device_ids",
                        "thermal_reserved",
                        "regulation.devices",
                        "regulation.reserved",
                        "thermal_settings_revision",
                        "thermal_settings_history",
                    ]
                },
            ],
        )


def arrange_registry_before_management(cycles: list[dict[str, Any]]) -> None:
    """Arrange existing monitor-only cycles and pill records from before management."""
    with isolated_database() as db:
        db.pills.update_many(
            {"_id": {"$in": [cycle["pill_id"] for cycle in cycles]}},
            {"$unset": {"archived": "", "registry_revision": ""}},
        )
        db.fermentations.insert_many(cycles)


def arrange_thermal_registry_before_management(
    devices: list[dict[str, Any]], cycle: dict[str, Any]
) -> None:
    """Prepare the previous thermal schema/index; assertions stay at HTTP boundaries."""
    with isolated_database() as db:
        db.thermal_devices.update_many(
            {"_id": {"$in": [device["id"] for device in devices]}},
            {"$unset": {"archived": "", "connection_revision": "", "registry_revision": ""}},
        )
        db.thermal_devices.create_index("base_url", unique=True)
        db.thermal_devices.drop_index("active_thermal_address")
        db.fermentations.insert_one(cycle)

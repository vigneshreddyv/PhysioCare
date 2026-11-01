"""Opt-in connected Mongo contract for an isolated local test database.

This module is skipped unless all three PHYSIOCARE_CONNECTED_MONGO_TEST_*
variables explicitly select and acknowledge the dedicated loopback database.
It must never be pointed at staging, production, or a database containing normal
application data.
"""

import asyncio
import os
from datetime import datetime
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

from app.models.auth_rate_limit import AuthRateLimitBucket
from app.services.auth_rate_limit_service import MongoRateLimitStore


CONNECTED_URL = os.environ.get("PHYSIOCARE_CONNECTED_MONGO_TEST_URL", "")
CONNECTED_DATABASE = os.environ.get("PHYSIOCARE_CONNECTED_MONGO_TEST_DATABASE", "")
CONNECTED_ACK = os.environ.get("PHYSIOCARE_CONNECTED_MONGO_TEST_ACK", "")
EXPECTED_DATABASE = "physiocare_phase14_connected_test"


def connected_test_is_explicitly_safe() -> bool:
    if CONNECTED_ACK != "isolated-loopback-test-only" or CONNECTED_DATABASE != EXPECTED_DATABASE:
        return False
    try:
        parsed = urlsplit(CONNECTED_URL)
    except ValueError:
        return False
    return parsed.scheme == "mongodb" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


pytestmark = pytest.mark.skipif(
    not connected_test_is_explicitly_safe(),
    reason="isolated loopback Mongo contract was not explicitly enabled",
)


@pytest.mark.asyncio
async def test_two_rate_limit_store_instances_share_atomic_counter_and_indexes(monkeypatch):
    client = AsyncIOMotorClient(CONNECTED_URL, serverSelectionTimeoutMS=2000)
    database = client[CONNECTED_DATABASE]
    collection_name = f"auth_rate_limit_contract_{uuid4().hex}"
    collection = database[collection_name]
    try:
        await collection.create_index("bucket_key", unique=True)
        await collection.create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0,
        )
        monkeypatch.setattr(
            AuthRateLimitBucket,
            "get_pymongo_collection",
            lambda: collection,
        )
        stores = (MongoRateLimitStore(), MongoRateLimitStore())
        now = datetime(2026, 11, 1, 12, 0, 1)
        decisions = await asyncio.gather(
            *(
                stores[index % 2].consume(
                    "opaque-shared-bucket",
                    limit=5,
                    window_seconds=60,
                    now=now,
                )
                for index in range(30)
            )
        )

        assert sum(item.allowed for item in decisions) == 5
        document = await collection.find_one({"bucket_key": "opaque-shared-bucket"})
        assert document["attempt_count"] == 30
        indexes = await collection.index_information()
        assert any(index.get("unique") for index in indexes.values())
        assert any(index.get("expireAfterSeconds") == 0 for index in indexes.values())
    finally:
        await database.drop_collection(collection_name)
        client.close()

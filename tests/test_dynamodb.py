"""
Unit tests for the DynamoDB data-access layer.
Uses moto for in-memory DynamoDB simulation.
"""
import os
from decimal import Decimal

import boto3
import pytest

# moto must be imported before any boto3 Table usage.
try:
    from moto import mock_aws
    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False

pytestmark = pytest.mark.skipif(not HAS_MOTO, reason="moto not installed")


EVENTS_TABLE = os.environ["EVENTS_TABLE"]
STATS_TABLE = os.environ["STATS_TABLE"]


@pytest.fixture
def aws_tables():
    """Spin up an in-memory DynamoDB with the same schema as template.yaml."""
    with mock_aws():
        client = boto3.resource("dynamodb", region_name="us-east-1")

        client.create_table(
            TableName=EVENTS_TABLE,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "event_id", "AttributeType": "S"},
                {"AttributeName": "event_type", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "type-created_at-index",
                    "KeySchema": [
                        {"AttributeName": "event_type", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )

        client.create_table(
            TableName=STATS_TABLE,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "stat_key", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "stat_key", "KeyType": "HASH"}],
        )

        yield


class TestStoreEvent:
    def test_stores_new_event(self, aws_tables):
        from db.dynamodb import DynamoDBClient
        db = DynamoDBClient()
        result = db.store_event("evt-1", "click", 5.0, "2024-01-01T00:00:00+00:00")
        assert result is True

    def test_duplicate_event_rejected(self, aws_tables):
        from db.dynamodb import DynamoDBClient
        db = DynamoDBClient()
        db.store_event("evt-dup", "click", 1.0, "2024-01-01T00:00:00+00:00")
        result = db.store_event("evt-dup", "click", 1.0, "2024-01-01T00:00:00+00:00")
        assert result is False

    def test_event_data_persisted(self, aws_tables):
        from db.dynamodb import DynamoDBClient
        db = DynamoDBClient()
        db.store_event("evt-chk", "purchase", 99.99, "2024-03-15T12:00:00+00:00")

        table = boto3.resource("dynamodb", region_name="us-east-1").Table(EVENTS_TABLE)
        item = table.get_item(Key={"event_id": "evt-chk"})["Item"]
        assert item["event_type"] == "purchase"
        assert float(item["value"]) == pytest.approx(99.99)
        assert item["status"] == "processed"


class TestIncrementStats:
    def test_total_incremented(self, aws_tables):
        from db.dynamodb import DynamoDBClient
        db = DynamoDBClient()
        db.increment_stats("click", 10.0)
        db.increment_stats("click", 20.0)

        total = db.get_stat("TOTAL")
        assert total["event_count"] == 2.0
        assert total["total_value"] == pytest.approx(30.0)

    def test_per_type_incremented(self, aws_tables):
        from db.dynamodb import DynamoDBClient
        db = DynamoDBClient()
        db.increment_stats("purchase", 50.0)
        db.increment_stats("purchase", 75.0)
        db.increment_stats("view", 1.0)

        type_stats = {s["stat_key"]: s for s in db.get_all_type_stats()}
        assert type_stats["TYPE#purchase"]["event_count"] == 2.0
        assert type_stats["TYPE#purchase"]["total_value"] == pytest.approx(125.0)
        assert type_stats["TYPE#view"]["event_count"] == 1.0


class TestQueryRecentEvents:
    def test_query_by_type_uses_gsi(self, aws_tables):
        from db.dynamodb import DynamoDBClient
        db = DynamoDBClient()
        db.store_event("e1", "click", 1.0, "2024-01-01T10:00:00+00:00")
        db.store_event("e2", "click", 2.0, "2024-01-01T11:00:00+00:00")
        db.store_event("e3", "view", 3.0, "2024-01-01T12:00:00+00:00")

        results = db.query_events_by_type("click", limit=10)
        assert len(results) == 2
        assert all(r["event_type"] == "click" for r in results)

    def test_scan_recent_returns_all_types(self, aws_tables):
        from db.dynamodb import DynamoDBClient
        db = DynamoDBClient()
        db.store_event("s1", "click", 1.0, "2024-01-01T00:00:00+00:00")
        db.store_event("s2", "purchase", 100.0, "2024-01-02T00:00:00+00:00")

        results = db.scan_recent_events(limit=10)
        types = {r["event_type"] for r in results}
        assert "click" in types
        assert "purchase" in types

"""
DynamoDB data-access layer.

All table interaction is isolated here so handlers and services stay
free of AWS SDK details.  Decimal conversions happen here too so callers
always receive plain Python floats/ints.
"""
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from utils.logger import get_logger

logger = get_logger(__name__)

EVENTS_TABLE: str = os.environ["EVENTS_TABLE"]
STATS_TABLE: str = os.environ["STATS_TABLE"]

# Events older than 30 days are auto-expired via DynamoDB TTL.
_TTL_DAYS = 30


def _to_decimal(value: float) -> Decimal:
    """Convert float → Decimal safely (avoids float binary-representation noise)."""
    return Decimal(str(value))


def _deserialize(item: dict) -> dict:
    """Recursively convert Decimal → float so callers get JSON-serialisable dicts."""
    result: dict[str, Any] = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, dict):
            result[k] = _deserialize(v)
        elif isinstance(v, list):
            result[k] = [_deserialize(i) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


class DynamoDBClient:
    """Thin wrapper around boto3 DynamoDB resource."""

    def __init__(self) -> None:
        dynamodb = boto3.resource("dynamodb")
        self.events_table = dynamodb.Table(EVENTS_TABLE)
        self.stats_table = dynamodb.Table(STATS_TABLE)

    # ── Events ────────────────────────────────────────────────────────────────

    def store_event(
        self,
        event_id: str,
        event_type: str,
        value: float,
        created_at: str,
    ) -> bool:
        """
        Write a new event record with idempotency guard.

        Uses a DynamoDB conditional expression so that a duplicate message
        (same event_id) causes a ConditionalCheckFailedException instead of
        silently overwriting the record.

        Returns True if stored, False if already exists (duplicate).
        """
        processed_at = datetime.now(timezone.utc).isoformat()
        ttl_expiry = int(
            datetime.now(timezone.utc).timestamp() + _TTL_DAYS * 86400
        )

        try:
            self.events_table.put_item(
                Item={
                    "event_id": event_id,
                    "event_type": event_type,
                    "value": _to_decimal(value),
                    "created_at": created_at,
                    "processed_at": processed_at,
                    "status": "processed",
                    "ttl_expiry": ttl_expiry,
                },
                # Idempotency: fail if this event_id was already written.
                ConditionExpression="attribute_not_exists(event_id)",
            )
            logger.info("Event stored", extra={"event_id": event_id})
            return True

        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == "ConditionalCheckFailedException":
                logger.warning("Duplicate event_id rejected", extra={"event_id": event_id})
                return False
            raise

    # ── Stats (atomic counters) ───────────────────────────────────────────────

    def increment_stats(self, event_type: str, value: float) -> None:
        """
        Atomically increment total and per-type counters.

        Uses DynamoDB's ADD operation so concurrent Lambda invocations
        don't race — each update is an atomic read-modify-write.
        """
        decimal_value = _to_decimal(value)

        # Global totals
        self.stats_table.update_item(
            Key={"stat_key": "TOTAL"},
            UpdateExpression="ADD event_count :one, total_value :val",
            ExpressionAttributeValues={":one": Decimal("1"), ":val": decimal_value},
        )

        # Per-type totals
        self.stats_table.update_item(
            Key={"stat_key": f"TYPE#{event_type}"},
            UpdateExpression="ADD event_count :one, total_value :val SET #t = :type_name",
            ExpressionAttributeNames={"#t": "event_type"},
            ExpressionAttributeValues={
                ":one": Decimal("1"),
                ":val": decimal_value,
                ":type_name": event_type,
            },
        )

    def get_stat(self, stat_key: str) -> dict | None:
        response = self.stats_table.get_item(Key={"stat_key": stat_key})
        item = response.get("Item")
        return _deserialize(item) if item else None

    def get_all_type_stats(self) -> list[dict]:
        """Return all per-type stat records (stat_key starts with TYPE#)."""
        response = self.stats_table.scan(
            FilterExpression=Attr("stat_key").begins_with("TYPE#")
        )
        return [_deserialize(item) for item in response.get("Items", [])]

    # ── Recent events ─────────────────────────────────────────────────────────

    def query_events_by_type(
        self,
        event_type: str,
        since: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        Query the GSI (type-created_at-index) for events of a specific type,
        newest first, optionally filtered by a lower-bound timestamp.
        """
        key_condition = Key("event_type").eq(event_type)
        if since:
            key_condition = key_condition & Key("created_at").gte(since)

        response = self.events_table.query(
            IndexName="type-created_at-index",
            KeyConditionExpression=key_condition,
            ScanIndexForward=False,   # descending by created_at
            Limit=limit,
        )
        return [_deserialize(item) for item in response.get("Items", [])]

    def scan_recent_events(self, since: str | None = None, limit: int = 20) -> list[dict]:
        """
        Scan for recent events across all types.
        NOTE: Scan is acceptable for low-volume demo use; a production system
        should add a date-partitioned GSI to avoid full-table scans.
        """
        kwargs: dict[str, Any] = {}
        if since:
            kwargs["FilterExpression"] = Attr("created_at").gte(since)

        # Over-fetch then sort + truncate in memory (scan order is not time-ordered).
        items: list[dict] = []
        response = self.events_table.scan(Limit=min(limit * 5, 500), **kwargs)
        items.extend(response.get("Items", []))

        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return [_deserialize(item) for item in items[:limit]]

"""
EventService — business logic for event ingestion and processing.

Keeps SQS and DynamoDB concerns separated so handlers stay thin.
"""
import json
import os
from typing import Any

import boto3

from db.dynamodb import DynamoDBClient
from utils.logger import get_logger

logger = get_logger(__name__)

QUEUE_URL: str = os.environ["EVENT_QUEUE_URL"]


class EventService:
    def __init__(self) -> None:
        # Re-use clients across Lambda warm invocations.
        self._sqs = boto3.client("sqs")
        self._db = DynamoDBClient()

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def enqueue_event(self, event_data: dict[str, Any]) -> str:
        """
        Send an event payload to SQS and return the SQS MessageId.

        The MessageGroupId / MessageDeduplicationId are intentionally omitted
        here (standard queue) — idempotency is enforced at the consumer side
        via DynamoDB conditional writes, which is more reliable because it
        survives queue redeliveries beyond the SQS dedup window (5 min).
        """
        response = self._sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(event_data),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": event_data["type"],
                }
            },
        )
        return response["MessageId"]

    # ── Processing (called from SQS processor Lambda) ─────────────────────────

    def process_event(self, event_data: dict[str, Any]) -> str:
        """
        Validate, store, and aggregate a single event.

        Returns:
            "processed"  – event was stored and stats updated
            "duplicate"  – event_id already in DynamoDB (idempotent skip)

        Raises:
            ValueError   – required fields missing or invalid
            Exception    – unexpected DB / network error (caller retries via SQS)
        """
        event_id: str | None = event_data.get("event_id")
        event_type: str | None = event_data.get("type")
        value = event_data.get("value")
        created_at: str | None = event_data.get("created_at")

        if not all([event_id, event_type, value is not None, created_at]):
            raise ValueError(
                f"Message missing required fields: {list(event_data.keys())}"
            )

        stored = self._db.store_event(
            event_id=event_id,
            event_type=event_type,
            value=float(value),
            created_at=created_at,
        )

        if not stored:
            return "duplicate"

        # Atomic counter update — safe under concurrent Lambda invocations.
        self._db.increment_stats(event_type=event_type, value=float(value))

        return "processed"

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_recent_events(
        self,
        limit: int = 20,
        event_type: str | None = None,
        since: str | None = None,
    ) -> list[dict]:
        """
        Return recent events, newest first.
        If event_type is provided, use the GSI for an efficient range query.
        Otherwise fall back to a scan (acceptable for demo-scale data).
        """
        if event_type:
            return self._db.query_events_by_type(
                event_type=event_type,
                since=since,
                limit=limit,
            )
        return self._db.scan_recent_events(since=since, limit=limit)

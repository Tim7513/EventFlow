"""
SQS Processor (triggered by EventQueue)

Processes events in batches (up to 10 per invocation).
Uses SQS ReportBatchItemFailures so only failed messages are retried,
not the entire batch.

Idempotency is enforced in the DB layer via DynamoDB conditional writes.
"""
import json
from typing import Any

from services.event_service import EventService
from utils.logger import get_logger

logger = get_logger(__name__)

_event_service = EventService()


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    records = event.get("Records", [])
    total = len(records)

    logger.info(
        "SQS batch received",
        extra={"batch_size": total, "request_id": context.aws_request_id},
    )

    batch_item_failures: list[dict[str, str]] = []
    processed = 0
    skipped = 0

    for record in records:
        message_id: str = record["messageId"]

        try:
            body = json.loads(record["body"])
            event_id = body.get("event_id", "<unknown>")

            logger.info(
                "Processing message",
                extra={"message_id": message_id, "event_id": event_id},
            )

            result = _event_service.process_event(body)

            if result == "duplicate":
                logger.warning(
                    "Duplicate event — skipping",
                    extra={"event_id": event_id, "message_id": message_id},
                )
                skipped += 1
            else:
                logger.info(
                    "Event processed",
                    extra={"event_id": event_id, "message_id": message_id},
                )
                processed += 1

        except Exception as exc:
            # Log and mark message for retry; DLQ handles exhausted retries.
            logger.error(
                "Failed to process message — will retry",
                extra={"message_id": message_id, "error": str(exc)},
                exc_info=True,
            )
            batch_item_failures.append({"itemIdentifier": message_id})

    logger.info(
        "Batch complete",
        extra={
            "total": total,
            "processed": processed,
            "skipped_duplicates": skipped,
            "failures": len(batch_item_failures),
        },
    )

    # Return partial failure list so SQS only re-enqueues failed items.
    return {"batchItemFailures": batch_item_failures}

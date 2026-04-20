"""
POST /event

Accepts { "type": str, "value": number }, assigns a UUID, and enqueues
the payload to SQS for asynchronous processing.  The handler never writes
to DynamoDB directly — it returns 202 Accepted once the message is queued.
"""
import json
import uuid
from datetime import datetime, timezone

from services.event_service import EventService
from utils.logger import get_logger
from utils.response import error_response, success_response

logger = get_logger(__name__)

# Module-level singleton keeps the boto3 client alive across warm invocations.
_event_service = EventService()


def handler(event: dict, context) -> dict:
    logger.info(
        "POST /event received",
        extra={"request_id": context.aws_request_id},
    )

    # ── Parse body ──────────────────────────────────────────────────────────
    try:
        body: dict = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error_response(400, "Request body must be valid JSON")

    # ── Validate fields ──────────────────────────────────────────────────────
    event_type = body.get("type")
    value = body.get("value")

    if not event_type or not isinstance(event_type, str) or not event_type.strip():
        return error_response(400, "Field 'type' is required and must be a non-empty string")

    if value is None:
        return error_response(400, "Field 'value' is required")

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return error_response(400, "Field 'value' must be a number")

    # ── Build event payload ──────────────────────────────────────────────────
    event_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    event_payload = {
        "event_id": event_id,
        "type": event_type.strip(),
        "value": float(value),
        "created_at": created_at,
    }

    # ── Enqueue to SQS (fire-and-forget) ────────────────────────────────────
    try:
        sqs_message_id = _event_service.enqueue_event(event_payload)
    except Exception as exc:
        logger.error(
            "Failed to enqueue event",
            extra={"error": str(exc), "event_id": event_id},
            exc_info=True,
        )
        return error_response(503, "Service temporarily unavailable — please retry")

    logger.info(
        "Event enqueued",
        extra={
            "event_id": event_id,
            "event_type": event_type,
            "sqs_message_id": sqs_message_id,
        },
    )

    return success_response(
        202,
        {
            "event_id": event_id,
            "message": "Event accepted for processing",
            "created_at": created_at,
        },
    )

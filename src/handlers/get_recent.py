"""
GET /events/recent

Query parameters (all optional):
  limit  – max items to return (default 20, max 100)
  type   – filter by event type (uses GSI: type-created_at-index)
  since  – ISO-8601 timestamp; only return events created after this time
"""
from services.event_service import EventService
from utils.logger import get_logger
from utils.response import error_response, success_response

logger = get_logger(__name__)

_event_service = EventService()
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


def handler(event: dict, context) -> dict:
    logger.info(
        "GET /events/recent received",
        extra={"request_id": context.aws_request_id},
    )

    params = event.get("queryStringParameters") or {}

    # ── Parse limit ──────────────────────────────────────────────────────────
    try:
        limit = int(params.get("limit", _DEFAULT_LIMIT))
        if not (1 <= limit <= _MAX_LIMIT):
            raise ValueError
    except (ValueError, TypeError):
        return error_response(
            400,
            f"'limit' must be an integer between 1 and {_MAX_LIMIT}",
        )

    event_type = params.get("type") or None
    since = params.get("since") or None

    try:
        items = _event_service.get_recent_events(
            limit=limit,
            event_type=event_type,
            since=since,
        )
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception as exc:
        logger.error(
            "Failed to retrieve recent events",
            extra={"error": str(exc)},
            exc_info=True,
        )
        return error_response(500, "Failed to retrieve recent events")

    return success_response(
        200,
        {
            "count": len(items),
            "limit": limit,
            "filters": {"type": event_type, "since": since},
            "events": items,
        },
    )

"""
GET /stats

Returns aggregated statistics stored in the StatsTable:
  - total events processed
  - overall average value
  - per-type breakdowns (count, total, average)
"""
from services.stats_service import StatsService
from utils.logger import get_logger
from utils.response import error_response, success_response

logger = get_logger(__name__)

_stats_service = StatsService()


def handler(event: dict, context) -> dict:
    logger.info(
        "GET /stats received",
        extra={"request_id": context.aws_request_id},
    )

    try:
        stats = _stats_service.get_stats()
    except Exception as exc:
        logger.error("Failed to retrieve stats", extra={"error": str(exc)}, exc_info=True)
        return error_response(500, "Failed to retrieve statistics")

    return success_response(200, stats)

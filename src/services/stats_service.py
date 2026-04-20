"""
StatsService — aggregates raw DynamoDB counter records into a tidy response.
"""
from db.dynamodb import DynamoDBClient
from utils.logger import get_logger

logger = get_logger(__name__)


class StatsService:
    def __init__(self) -> None:
        self._db = DynamoDBClient()

    def get_stats(self) -> dict:
        """
        Read the TOTAL record and all TYPE#<name> records from StatsTable
        and return a formatted stats payload.
        """
        total_record = self._db.get_stat("TOTAL")
        type_records = self._db.get_all_type_stats()

        total_count = int(total_record.get("event_count", 0)) if total_record else 0
        total_value = float(total_record.get("total_value", 0.0)) if total_record else 0.0

        average_value = round(total_value / total_count, 6) if total_count > 0 else 0.0

        by_type: dict = {}
        for record in type_records:
            type_name = record["stat_key"].replace("TYPE#", "", 1)
            count = int(record.get("event_count", 0))
            type_total = float(record.get("total_value", 0.0))
            by_type[type_name] = {
                "count": count,
                "total_value": round(type_total, 6),
                "average_value": round(type_total / count, 6) if count > 0 else 0.0,
            }

        return {
            "total_events": total_count,
            "total_value": round(total_value, 6),
            "average_value": average_value,
            "by_type": by_type,
        }

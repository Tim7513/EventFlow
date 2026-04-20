"""
Helpers for building consistent Lambda proxy-integration responses.
"""
import json
from decimal import Decimal
from typing import Any


class _DecimalEncoder(json.JSONEncoder):
    """json.dumps can't handle Decimal from DynamoDB — convert to float."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _dumps(body: Any) -> str:
    return json.dumps(body, cls=_DecimalEncoder)


_BASE_HEADERS = {
    "Content-Type": "application/json",
    "X-Content-Type-Options": "nosniff",
}


def success_response(status_code: int, body: Any) -> dict:
    return {
        "statusCode": status_code,
        "headers": _BASE_HEADERS,
        "body": _dumps(body),
    }


def error_response(status_code: int, message: str, detail: str | None = None) -> dict:
    payload: dict[str, Any] = {"error": message}
    if detail:
        payload["detail"] = detail
    return {
        "statusCode": status_code,
        "headers": _BASE_HEADERS,
        "body": _dumps(payload),
    }

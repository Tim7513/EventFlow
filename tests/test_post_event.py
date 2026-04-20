"""
Unit tests for POST /event handler.
All AWS calls are mocked — no real infrastructure required.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from handlers.post_event import handler


def _make_event(body: dict | None = None, raw_body: str | None = None) -> dict:
    return {
        "body": raw_body if raw_body is not None else (json.dumps(body) if body else None),
        "httpMethod": "POST",
        "path": "/event",
    }


@pytest.fixture(autouse=True)
def mock_event_service():
    """Patch EventService so no real SQS calls are made."""
    with patch("handlers.post_event._event_service") as mock:
        mock.enqueue_event.return_value = "sqs-message-id-abc"
        yield mock


class TestPostEventValidation:
    def test_missing_body_returns_400(self, lambda_context):
        resp = handler({"body": None}, lambda_context)
        assert resp["statusCode"] == 400

    def test_invalid_json_returns_400(self, lambda_context):
        resp = handler(_make_event(raw_body="not-json"), lambda_context)
        assert resp["statusCode"] == 400

    def test_missing_type_returns_400(self, lambda_context):
        resp = handler(_make_event({"value": 42}), lambda_context)
        assert resp["statusCode"] == 400
        assert "type" in json.loads(resp["body"])["error"].lower()

    def test_missing_value_returns_400(self, lambda_context):
        resp = handler(_make_event({"type": "click"}), lambda_context)
        assert resp["statusCode"] == 400
        assert "value" in json.loads(resp["body"])["error"].lower()

    def test_boolean_value_rejected(self, lambda_context):
        resp = handler(_make_event({"type": "click", "value": True}), lambda_context)
        assert resp["statusCode"] == 400

    def test_string_value_rejected(self, lambda_context):
        resp = handler(_make_event({"type": "click", "value": "five"}), lambda_context)
        assert resp["statusCode"] == 400

    def test_empty_type_rejected(self, lambda_context):
        resp = handler(_make_event({"type": "   ", "value": 1}), lambda_context)
        assert resp["statusCode"] == 400


class TestPostEventSuccess:
    def test_returns_202_with_event_id(self, lambda_context):
        resp = handler(_make_event({"type": "purchase", "value": 99.99}), lambda_context)
        assert resp["statusCode"] == 202
        body = json.loads(resp["body"])
        assert "event_id" in body
        assert body["message"] == "Event accepted for processing"
        assert "created_at" in body

    def test_float_value_accepted(self, lambda_context):
        resp = handler(_make_event({"type": "sale", "value": 1.5}), lambda_context)
        assert resp["statusCode"] == 202

    def test_zero_value_accepted(self, lambda_context):
        resp = handler(_make_event({"type": "view", "value": 0}), lambda_context)
        assert resp["statusCode"] == 202

    def test_enqueue_called_once(self, mock_event_service, lambda_context):
        handler(_make_event({"type": "click", "value": 10}), lambda_context)
        mock_event_service.enqueue_event.assert_called_once()
        payload = mock_event_service.enqueue_event.call_args[0][0]
        assert payload["type"] == "click"
        assert payload["value"] == 10.0


class TestPostEventServiceFailure:
    def test_sqs_failure_returns_503(self, mock_event_service, lambda_context):
        mock_event_service.enqueue_event.side_effect = RuntimeError("SQS unavailable")
        resp = handler(_make_event({"type": "error_test", "value": 1}), lambda_context)
        assert resp["statusCode"] == 503

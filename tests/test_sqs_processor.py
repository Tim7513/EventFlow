"""
Unit tests for the SQS batch processor handler.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from handlers.sqs_processor import handler


def _make_record(event_id: str, event_type: str = "click", value: float = 5.0) -> dict:
    return {
        "messageId": f"msg-{event_id}",
        "receiptHandle": f"receipt-{event_id}",
        "body": json.dumps(
            {
                "event_id": event_id,
                "type": event_type,
                "value": value,
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        ),
    }


@pytest.fixture(autouse=True)
def mock_event_service():
    with patch("handlers.sqs_processor._event_service") as mock:
        mock.process_event.return_value = "processed"
        yield mock


class TestSqsProcessorBatch:
    def test_all_success_returns_empty_failures(self, mock_event_service, lambda_context):
        records = [_make_record("id-1"), _make_record("id-2"), _make_record("id-3")]
        result = handler({"Records": records}, lambda_context)
        assert result == {"batchItemFailures": []}
        assert mock_event_service.process_event.call_count == 3

    def test_duplicate_events_not_in_failures(self, mock_event_service, lambda_context):
        mock_event_service.process_event.return_value = "duplicate"
        records = [_make_record("dup-1")]
        result = handler({"Records": records}, lambda_context)
        # Duplicates are silently skipped, not retried.
        assert result == {"batchItemFailures": []}

    def test_failed_message_returned_in_failures(self, mock_event_service, lambda_context):
        mock_event_service.process_event.side_effect = [
            "processed",
            RuntimeError("DB write failed"),
            "processed",
        ]
        records = [_make_record("id-1"), _make_record("id-2"), _make_record("id-3")]
        result = handler({"Records": records}, lambda_context)
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-id-2"

    def test_all_fail_returns_all_in_failures(self, mock_event_service, lambda_context):
        mock_event_service.process_event.side_effect = RuntimeError("total outage")
        records = [_make_record("id-1"), _make_record("id-2")]
        result = handler({"Records": records}, lambda_context)
        assert len(result["batchItemFailures"]) == 2

    def test_empty_batch_returns_empty_failures(self, lambda_context):
        result = handler({"Records": []}, lambda_context)
        assert result == {"batchItemFailures": []}

    def test_partial_batch_failure_correct_message_ids(self, mock_event_service, lambda_context):
        def side_effect(event_data):
            if event_data["event_id"] == "bad-id":
                raise ValueError("Invalid data")
            return "processed"

        mock_event_service.process_event.side_effect = side_effect
        records = [
            _make_record("good-id"),
            _make_record("bad-id"),
        ]
        result = handler({"Records": records}, lambda_context)
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-bad-id"

"""
Shared pytest fixtures and environment setup.
"""
import os
import sys

import pytest

# Ensure src/ is on the path so handlers/services/db can be imported without
# installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Stub out AWS environment variables before any module-level boto3 calls.
os.environ.setdefault("EVENTS_TABLE", "test-events")
os.environ.setdefault("STATS_TABLE", "test-stats")
os.environ.setdefault("EVENT_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789/test-queue")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


class _FakeContext:
    aws_request_id = "test-request-id-123"
    function_name = "test-function"
    memory_limit_in_mb = 256
    remaining_time_in_millis = lambda self: 30000  # noqa: E731


@pytest.fixture
def lambda_context():
    return _FakeContext()

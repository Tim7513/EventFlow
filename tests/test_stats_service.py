"""
Unit tests for StatsService.
"""
from unittest.mock import MagicMock, patch

import pytest

from services.stats_service import StatsService


@pytest.fixture
def mock_db():
    with patch("services.stats_service.DynamoDBClient") as MockDB:
        instance = MockDB.return_value
        yield instance


class TestGetStatsEmpty:
    def test_empty_table_returns_zeroes(self, mock_db):
        mock_db.get_stat.return_value = None
        mock_db.get_all_type_stats.return_value = []

        svc = StatsService()
        stats = svc.get_stats()

        assert stats["total_events"] == 0
        assert stats["average_value"] == 0.0
        assert stats["total_value"] == 0.0
        assert stats["by_type"] == {}

    def test_no_division_by_zero(self, mock_db):
        mock_db.get_stat.return_value = {"event_count": 0, "total_value": 0}
        mock_db.get_all_type_stats.return_value = []

        svc = StatsService()
        stats = svc.get_stats()
        assert stats["average_value"] == 0.0


class TestGetStatsWithData:
    def test_average_calculated_correctly(self, mock_db):
        mock_db.get_stat.return_value = {"event_count": 4, "total_value": 100.0}
        mock_db.get_all_type_stats.return_value = [
            {"stat_key": "TYPE#click", "event_count": 3, "total_value": 60.0},
            {"stat_key": "TYPE#purchase", "event_count": 1, "total_value": 40.0},
        ]

        svc = StatsService()
        stats = svc.get_stats()

        assert stats["total_events"] == 4
        assert stats["total_value"] == 100.0
        assert stats["average_value"] == 25.0

    def test_by_type_breakdown(self, mock_db):
        mock_db.get_stat.return_value = {"event_count": 2, "total_value": 30.0}
        mock_db.get_all_type_stats.return_value = [
            {"stat_key": "TYPE#view", "event_count": 2, "total_value": 30.0},
        ]

        svc = StatsService()
        stats = svc.get_stats()

        assert "view" in stats["by_type"]
        view = stats["by_type"]["view"]
        assert view["count"] == 2
        assert view["total_value"] == 30.0
        assert view["average_value"] == 15.0

    def test_type_key_prefix_stripped(self, mock_db):
        mock_db.get_stat.return_value = {"event_count": 1, "total_value": 5.0}
        mock_db.get_all_type_stats.return_value = [
            {"stat_key": "TYPE#order_placed", "event_count": 1, "total_value": 5.0},
        ]

        svc = StatsService()
        stats = svc.get_stats()
        assert "order_placed" in stats["by_type"]
        assert "TYPE#order_placed" not in stats["by_type"]

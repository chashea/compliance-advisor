"""Tests for fetch_scores prompt flow node."""
from unittest.mock import patch, MagicMock
import pytest


class TestFetchScores:
    def test_returns_list_of_dicts(self, mock_connection, mock_cursor):
        mock_cursor.description = [("tenant_id",), ("display_name",), ("compliance_pct",)]
        mock_cursor.fetchall.return_value = [
            ("uuid-1", "Tenant A", 75.0),
            ("uuid-2", "Tenant B", 82.0),
        ]

        with patch("fetch_scores.get_connection", return_value=mock_connection), \
             patch("fetch_scores.set_admin_context"):
            from fetch_scores import fetch_scores
            result = fetch_scores()

        assert len(result) == 2
        assert result[0]["tenant_id"] == "uuid-1"
        assert result[1]["compliance_pct"] == 82.0

    def test_calls_set_admin_context(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []

        with patch("fetch_scores.get_connection", return_value=mock_connection), \
             patch("fetch_scores.set_admin_context") as mock_admin:
            from fetch_scores import fetch_scores
            fetch_scores()

        mock_admin.assert_called_once_with(mock_connection)

    def test_closes_connection_on_error(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = RuntimeError("db")

        with patch("fetch_scores.get_connection", return_value=mock_connection), \
             patch("fetch_scores.set_admin_context"):
            from fetch_scores import fetch_scores
            with pytest.raises(RuntimeError):
                fetch_scores()

        mock_connection.close.assert_called_once()

"""Tests for compute_gaps prompt flow node."""
from unittest.mock import patch, MagicMock
import pytest


class TestComputeGaps:
    def test_empty_scores_returns_empty(self):
        from compute_gaps import compute_gaps
        result = compute_gaps([])
        assert result["tenant_summaries"] == []
        assert result["enterprise_rollup"] == {}
        assert result["top_gaps"] == []

    def test_enterprise_rollup_avg(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []

        scores = [
            {"compliance_pct": 40, "current_score": 40, "max_score": 100, "display_name": "A"},
            {"compliance_pct": 80, "current_score": 80, "max_score": 100, "display_name": "B"},
        ]

        with patch("compute_gaps.get_connection", return_value=mock_connection), \
             patch("compute_gaps.set_admin_context"):
            from compute_gaps import compute_gaps
            result = compute_gaps(scores)

        assert result["enterprise_rollup"]["avg_compliance_pct"] == 60.0
        assert result["enterprise_rollup"]["tenant_count"] == 2

    def test_lowest_tenant_is_first(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []

        scores = [
            {"compliance_pct": 30, "current_score": 30, "max_score": 100, "display_name": "Lowest"},
            {"compliance_pct": 90, "current_score": 90, "max_score": 100, "display_name": "Highest"},
        ]

        with patch("compute_gaps.get_connection", return_value=mock_connection), \
             patch("compute_gaps.set_admin_context"):
            from compute_gaps import compute_gaps
            result = compute_gaps(scores)

        assert result["enterprise_rollup"]["lowest_tenant"] == "Lowest"

    def test_min_max_correct(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []

        scores = [
            {"compliance_pct": 40, "current_score": 40, "max_score": 100, "display_name": "A"},
            {"compliance_pct": 80, "current_score": 80, "max_score": 100, "display_name": "B"},
        ]

        with patch("compute_gaps.get_connection", return_value=mock_connection), \
             patch("compute_gaps.set_admin_context"):
            from compute_gaps import compute_gaps
            result = compute_gaps(scores)

        assert result["enterprise_rollup"]["min_compliance_pct"] == 40.0
        assert result["enterprise_rollup"]["max_compliance_pct"] == 80.0

    def test_gaps_from_sql(self, mock_connection, mock_cursor):
        # First call returns gaps, second returns weekly changes, third returns dept rollup
        mock_cursor.description = [("control_name",), ("total_gap",)]
        mock_cursor.fetchall.side_effect = [
            [("MFA", 50)],   # top gaps
            [],              # weekly changes
            [],              # department rollup
        ]

        scores = [{"compliance_pct": 50, "current_score": 50, "max_score": 100, "display_name": "A"}]

        with patch("compute_gaps.get_connection", return_value=mock_connection), \
             patch("compute_gaps.set_admin_context"):
            from compute_gaps import compute_gaps
            result = compute_gaps(scores)

        assert len(result["top_gaps"]) == 1

    def test_closes_connection_on_error(self, mock_connection, mock_cursor):
        mock_cursor.execute.side_effect = RuntimeError("db")
        scores = [{"compliance_pct": 50, "current_score": 50, "max_score": 100, "display_name": "A"}]

        with patch("compute_gaps.get_connection", return_value=mock_connection), \
             patch("compute_gaps.set_admin_context"):
            from compute_gaps import compute_gaps
            with pytest.raises(RuntimeError):
                compute_gaps(scores)

        mock_connection.close.assert_called_once()

"""Test that compute_aggregates uses the new CTE+LEFT JOIN query shape."""

from unittest.mock import MagicMock, patch

import azure.functions as func


def _timer_request():
    return MagicMock(spec=func.TimerRequest)


@patch("routes.timers.upsert_trend")
@patch("routes.timers.query")
def test_compute_aggregates_uses_single_cte_query(mock_query, mock_upsert):
    """Verify a single CTE roundtrip replaces the 4 correlated subqueries."""
    mock_query.return_value = [
        {"tenant_id": "t1", "department": "DOJ", "sensitivity": 5, "dlp": 2, "audit": 100},
        {"tenant_id": "t2", "department": "DOJ", "sensitivity": 3, "dlp": 0, "audit": 50},
    ]

    from routes.timers import compute_aggregates

    compute_aggregates(_timer_request())

    # Only one SQL query for the tenant counts (rewrite goal)
    assert mock_query.call_count == 1
    sql = mock_query.call_args.args[0]
    # CTE structure
    assert "WITH" in sql
    assert sql.count("LEFT JOIN") >= 3, "expected one LEFT JOIN per workload"
    assert "COALESCE" in sql, "expected COALESCE for tenants with no rows"
    # No correlated subselects on the snapshot_date lookup anymore
    assert "MAX(snapshot_date)" in sql
    assert "GROUP BY tenant_id" in sql

    # Statewide + per-department upserts: 1 statewide + 1 dept (both tenants in DOJ)
    assert mock_upsert.call_count == 2
    statewide = mock_upsert.call_args_list[0]
    assert statewide.kwargs["department"] is None
    assert statewide.kwargs["sensitivity_labels"] == 8  # 5 + 3
    assert statewide.kwargs["dlp_alerts"] == 2
    assert statewide.kwargs["audit_records"] == 150


@patch("routes.timers.upsert_trend")
@patch("routes.timers.query")
def test_compute_aggregates_skips_when_no_tenants(mock_query, mock_upsert):
    mock_query.return_value = []

    from routes.timers import compute_aggregates

    compute_aggregates(_timer_request())

    mock_query.assert_called_once()
    mock_upsert.assert_not_called()

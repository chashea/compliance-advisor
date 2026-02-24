"""Tests for the HTTP API — routing, handlers, error handling."""
import json
from unittest.mock import patch, MagicMock
import pytest
import azure.functions as func


def _make_request(action, body=None):
    """Create a mock HttpRequest for the given action and JSON body."""
    req = func.HttpRequest(
        method="POST",
        url=f"http://localhost/api/advisor/{action}",
        route_params={"action": action},
        body=json.dumps(body).encode() if body else b"",
    )
    return req


class TestRouting:
    def test_unknown_action_returns_404(self):
        from http_api import main
        resp = main(_make_request("nonexistent"))
        assert resp.status_code == 404
        data = json.loads(resp.get_body())
        assert "error" in data
        assert "available_actions" in data

    def test_invalid_json_body_handled_gracefully(self, mock_connection):
        with patch("http_api.get_connection", return_value=mock_connection), \
             patch("http_api.set_admin_context"):
            mock_connection.cursor.return_value.fetchone.return_value = (3, None, None)
            mock_connection.cursor.return_value.description = [
                ("active_tenants",), ("oldest_sync",), ("newest_sync",)
            ]
            from http_api import main
            req = func.HttpRequest(
                method="POST",
                url="http://localhost/api/advisor/status",
                route_params={"action": "status"},
                body=b"not-json",
            )
            resp = main(req)
        assert resp.status_code == 200


class TestHandleStatus:
    def test_returns_healthy(self, mock_connection):
        with patch("http_api.get_connection", return_value=mock_connection), \
             patch("http_api.set_admin_context"):
            cursor = mock_connection.cursor.return_value
            cursor.fetchone.return_value = (3, "2026-02-21", "2026-02-22")
            cursor.description = [
                ("active_tenants",), ("oldest_sync",), ("newest_sync",)
            ]
            from http_api import main
            resp = main(_make_request("status"))

        data = json.loads(resp.get_body())
        assert data["status"] == "healthy"
        assert data["active_tenants"] == 3


class TestHandleAsk:
    def test_missing_question_returns_400(self):
        from http_api import main
        resp = main(_make_request("ask", {}))
        assert resp.status_code == 400

    def test_calls_foundry_agent(self):
        mock_result = {"answer": "Your score is 72%", "sources": []}

        with patch("shared.agents.compliance_advisor.ask_advisor", return_value=mock_result):
            from http_api import main
            resp = main(_make_request("ask", {"question": "What is my score?"}))

        data = json.loads(resp.get_body())
        assert data["answer"] == "Your score is 72%"

    def test_passes_tenant_context(self):
        mock_result = {"answer": "Tenant score: 85%", "sources": []}

        with patch("shared.agents.compliance_advisor.ask_advisor", return_value=mock_result) as mock_ask:
            from http_api import main
            resp = main(_make_request("ask", {
                "question": "What is my score?",
                "tenant_id": "abc-123",
                "cross_tenant": True,
            }))
            mock_ask.assert_called_once_with(
                "What is my score?", tenant_id="abc-123", cross_tenant=True
            )


class TestHandleTrends:
    def test_caps_days_at_90(self, mock_connection, mock_cursor):
        mock_cursor.description = [("snapshot_date",), ("avg_score_pct",)]
        mock_cursor.fetchall.return_value = []

        with patch("http_api.get_connection", return_value=mock_connection), \
             patch("http_api.set_admin_context"):
            from http_api import main
            resp = main(_make_request("trends", {"days": 999}))

        data = json.loads(resp.get_body())
        assert data["filters"]["days"] == 90

    def test_returns_three_keys(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []

        with patch("http_api.get_connection", return_value=mock_connection), \
             patch("http_api.set_admin_context"):
            from http_api import main
            resp = main(_make_request("trends", {}))

        data = json.loads(resp.get_body())
        assert "score_trend" in data
        assert "weekly_changes" in data
        assert "category_trends" in data


class TestHandleAssessments:
    def test_caps_top_gaps_at_50(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        with patch("http_api.get_connection", return_value=mock_connection), \
             patch("http_api.set_admin_context"):
            from http_api import main
            resp = main(_make_request("assessments", {"top_gaps": 999}))

        # Verify the SQL used TOP 50 by checking cursor.execute calls
        calls = mock_cursor.execute.call_args_list
        gap_sql = [c for c in calls if "TOP" in str(c)]
        assert any("50" in str(c) for c in gap_sql)


class TestHandleActions:
    def test_caps_top_n_at_200(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        with patch("http_api.get_connection", return_value=mock_connection), \
             patch("http_api.set_admin_context"):
            from http_api import main
            resp = main(_make_request("actions", {"top_n": 9999}))

        data = json.loads(resp.get_body())
        assert data["filters"]["top_n"] == 200


class TestErrorHandling:
    def test_unhandled_exception_returns_500(self):
        with patch("http_api.get_connection", side_effect=RuntimeError("db down")):
            from http_api import main
            resp = main(_make_request("status"))

        assert resp.status_code == 500
        data = json.loads(resp.get_body())
        assert data["error"] == "Internal server error"

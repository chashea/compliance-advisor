"""Tests for the FastAPI server — routing, handlers, error handling."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(mock_connection):
    with patch("api.get_connection", return_value=mock_connection), patch("api.set_admin_context"):
        from api import app

        yield TestClient(app)


class TestRouting:
    def test_unknown_action_returns_404(self, client):
        resp = client.post("/api/advisor/nonexistent", json={})
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert "available_actions" in data

    def test_invalid_json_body_handled_gracefully(self, mock_connection):
        with patch("api.get_connection", return_value=mock_connection), patch("api.set_admin_context"):
            mock_connection.cursor.return_value.fetchone.return_value = (3, None, None)
            mock_connection.cursor.return_value.description = [("active_tenants",), ("oldest_sync",), ("newest_sync",)]
            from api import app

            tc = TestClient(app)
            resp = tc.post(
                "/api/advisor/status",
                content=b"not-json",
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 200


class TestHandleStatus:
    def test_returns_healthy(self, mock_connection):
        with patch("api.get_connection", return_value=mock_connection), patch("api.set_admin_context"):
            cursor = mock_connection.cursor.return_value
            cursor.fetchone.return_value = (3, "2026-02-21", "2026-02-22")
            cursor.description = [("active_tenants",), ("oldest_sync",), ("newest_sync",)]
            from api import app

            tc = TestClient(app)
            resp = tc.post("/api/advisor/status", json={})

        data = resp.json()
        assert data["status"] == "healthy"
        assert data["active_tenants"] == 3


class TestHandleAsk:
    def test_missing_question_returns_400(self, client):
        resp = client.post("/api/advisor/ask", json={})
        assert resp.status_code == 400

    def test_stub_response_without_foundry(self, client):
        with patch("api._foundry_respond", None):
            resp = client.post("/api/advisor/ask", json={"question": "What is my score?"})
        data = resp.json()
        assert data["answer"] == "AI advisor not available in local MVP."


class TestHandleTrends:
    def test_caps_days_at_90(self, mock_connection, mock_cursor):
        mock_cursor.description = [("snapshot_date",), ("avg_score_pct",)]
        mock_cursor.fetchall.return_value = []

        with patch("api.get_connection", return_value=mock_connection), patch("api.set_admin_context"):
            from api import app

            tc = TestClient(app)
            resp = tc.post("/api/advisor/trends", json={"days": 999})

        data = resp.json()
        assert data["filters"]["days"] == 90

    def test_returns_three_keys(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []

        with patch("api.get_connection", return_value=mock_connection), patch("api.set_admin_context"):
            from api import app

            tc = TestClient(app)
            resp = tc.post("/api/advisor/trends", json={})

        data = resp.json()
        assert "score_trend" in data
        assert "weekly_changes" in data
        assert "category_trends" in data


class TestHandleActions:
    def test_caps_top_n_at_200(self, mock_connection, mock_cursor):
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        with patch("api.get_connection", return_value=mock_connection), patch("api.set_admin_context"):
            from api import app

            tc = TestClient(app)
            resp = tc.post("/api/advisor/actions", json={"top_n": 9999})

        data = resp.json()
        assert data["filters"]["top_n"] == 200


class TestErrorHandling:
    def test_unhandled_exception_returns_500(self):
        with patch("api.get_connection", side_effect=RuntimeError("db down")):
            from api import app

            tc = TestClient(app)
            resp = tc.post("/api/advisor/status", json={})

        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "Internal server error"

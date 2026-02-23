"""Tests for the collect_tenant_data activity."""
from unittest.mock import patch, MagicMock
import importlib
import pytest


@pytest.fixture
def activity():
    import activities.collect_tenant_data as mod
    importlib.reload(mod)
    return mod


class TestCollectTenantData:
    def _run(self, activity, sample_tenant, mock_connection,
             scores=None, profiles=None, token="tok"):
        scores = scores if scores is not None else []
        profiles = profiles if profiles is not None else []

        with patch.object(activity, "get_graph_token", return_value=token), \
             patch.object(activity, "get_secure_scores", return_value=scores), \
             patch.object(activity, "get_control_profiles", return_value=profiles), \
             patch.object(activity, "get_connection", return_value=mock_connection), \
             patch.object(activity, "set_tenant_context"), \
             patch.object(activity, "upsert_secure_score") as mock_upsert_ss, \
             patch.object(activity, "upsert_control_scores") as mock_upsert_cs, \
             patch.object(activity, "upsert_control_profiles") as mock_upsert_cp, \
             patch.object(activity, "upsert_benchmarks") as mock_upsert_bm, \
             patch.object(activity, "mark_tenant_synced") as mock_synced:
            result = activity.main(sample_tenant)
            return result, {
                "upsert_ss": mock_upsert_ss,
                "upsert_cs": mock_upsert_cs,
                "upsert_cp": mock_upsert_cp,
                "upsert_bm": mock_upsert_bm,
                "synced": mock_synced,
            }

    def test_happy_path(self, sample_tenant, mock_connection, sample_secure_score, activity):
        result, mocks = self._run(activity, sample_tenant, mock_connection,
                                   scores=[sample_secure_score],
                                   profiles=[{"id": "p1"}])
        assert result["success"] is True
        assert result["snapshots"] == 1
        mocks["synced"].assert_called_once()
        mock_connection.close.assert_called_once()

    def test_calls_upsert_per_snapshot(self, sample_tenant, mock_connection, sample_secure_score, activity):
        scores = [sample_secure_score, sample_secure_score, sample_secure_score]
        result, mocks = self._run(activity, sample_tenant, mock_connection, scores=scores)
        assert mocks["upsert_ss"].call_count == 3
        assert mocks["upsert_cs"].call_count == 3
        assert mocks["upsert_bm"].call_count == 3

    def test_returns_failure_on_auth_error(self, sample_tenant, mock_connection, activity):
        with patch.object(activity, "get_graph_token", side_effect=Exception("auth failed")):
            result = activity.main(sample_tenant)
        assert result["success"] is False
        assert "auth failed" in result["error"]

    def test_closes_connection_on_upsert_error(self, sample_tenant, mock_connection, sample_secure_score, activity):
        with patch.object(activity, "get_graph_token", return_value="tok"), \
             patch.object(activity, "get_secure_scores", return_value=[sample_secure_score]), \
             patch.object(activity, "get_control_profiles", return_value=[]), \
             patch.object(activity, "get_connection", return_value=mock_connection), \
             patch.object(activity, "set_tenant_context"), \
             patch.object(activity, "upsert_secure_score", side_effect=RuntimeError("db")), \
             patch.object(activity, "upsert_control_scores"), \
             patch.object(activity, "upsert_control_profiles"), \
             patch.object(activity, "upsert_benchmarks"), \
             patch.object(activity, "mark_tenant_synced"):
            result = activity.main(sample_tenant)

        assert result["success"] is False
        mock_connection.close.assert_called_once()

    def test_empty_scores_still_syncs(self, sample_tenant, mock_connection, activity):
        result, mocks = self._run(activity, sample_tenant, mock_connection, scores=[], profiles=[])
        assert result["success"] is True
        assert result["snapshots"] == 0
        mocks["upsert_ss"].assert_not_called()
        mocks["synced"].assert_called_once()

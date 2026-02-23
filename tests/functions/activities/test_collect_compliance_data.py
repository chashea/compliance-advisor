"""Tests for the collect_compliance_data activity."""
from unittest.mock import patch, MagicMock
import importlib
import sys
import os
import pytest

# Ensure source paths are available
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../src/functions"))


@pytest.fixture
def activity():
    """Import the activity module fresh, handling sys.path inserts."""
    import activities.collect_compliance_data as mod
    importlib.reload(mod)
    return mod


class TestCollectComplianceData:
    def test_happy_path_sdk(self, sample_tenant, activity):
        assessments = [{"id": "a1", "displayName": "Test", "status": "active", "regulation": "SOC 2"}]
        controls = [{"id": "c1", "displayName": "MFA", "controlFamily": "Identity"}]

        with patch.object(activity, "get_graph_client"), \
             patch.object(activity, "get_graph_token", return_value="raw-tok"), \
             patch.object(activity, "get_compliance_score_sdk", return_value={"currentScore": 80, "maxScore": 100}), \
             patch.object(activity, "get_compliance_score_breakdown_sdk", return_value=[]), \
             patch.object(activity, "get_compliance_assessments_sdk", return_value=assessments), \
             patch.object(activity, "get_assessment_controls_sdk", return_value=controls), \
             patch.object(activity, "get_compliance_score", return_value=None), \
             patch.object(activity, "get_compliance_score_breakdown", return_value=[]), \
             patch.object(activity, "get_compliance_assessments", return_value=[]), \
             patch.object(activity, "get_assessment_controls", return_value=[]), \
             patch.object(activity, "get_connection") as mock_conn, \
             patch.object(activity, "set_tenant_context"), \
             patch.object(activity, "upsert_compliance_score"), \
             patch.object(activity, "upsert_assessment") as mock_upsert_a, \
             patch.object(activity, "upsert_assessment_control") as mock_upsert_ac, \
             patch.object(activity, "mark_tenant_synced"):
            result = activity.main(sample_tenant)

        assert result["success"] is True
        assert result["assessments"] == 1
        assert result["controls"] == 1
        mock_upsert_a.assert_called_once()
        mock_upsert_ac.assert_called_once()

    def test_falls_back_to_http_when_sdk_score_is_none(self, sample_tenant, activity):
        with patch.object(activity, "get_graph_client"), \
             patch.object(activity, "get_graph_token", return_value="raw-tok"), \
             patch.object(activity, "get_compliance_score_sdk", return_value=None), \
             patch.object(activity, "get_compliance_score_breakdown_sdk", return_value=[]), \
             patch.object(activity, "get_compliance_assessments_sdk", return_value=[]), \
             patch.object(activity, "get_assessment_controls_sdk", return_value=[]), \
             patch.object(activity, "get_compliance_score", return_value={"currentScore": 75, "maxScore": 100}) as mock_http, \
             patch.object(activity, "get_compliance_score_breakdown", return_value=[]), \
             patch.object(activity, "get_compliance_assessments", return_value=[]), \
             patch.object(activity, "get_assessment_controls", return_value=[]), \
             patch.object(activity, "get_connection"), \
             patch.object(activity, "set_tenant_context"), \
             patch.object(activity, "upsert_compliance_score") as mock_upsert, \
             patch.object(activity, "upsert_assessment"), \
             patch.object(activity, "upsert_assessment_control"), \
             patch.object(activity, "mark_tenant_synced"):
            result = activity.main(sample_tenant)

        assert result["success"] is True
        mock_http.assert_called_once()
        mock_upsert.assert_called()

    def test_skips_controls_for_assessment_without_id(self, sample_tenant, activity):
        assessment_no_id = {"displayName": "No ID", "status": "active"}

        with patch.object(activity, "get_graph_client"), \
             patch.object(activity, "get_graph_token", return_value="tok"), \
             patch.object(activity, "get_compliance_score_sdk", return_value={"currentScore": 80, "maxScore": 100}), \
             patch.object(activity, "get_compliance_score_breakdown_sdk", return_value=[]), \
             patch.object(activity, "get_compliance_assessments_sdk", return_value=[assessment_no_id]), \
             patch.object(activity, "get_assessment_controls_sdk") as mock_get_ctrls, \
             patch.object(activity, "get_compliance_score", return_value=None), \
             patch.object(activity, "get_compliance_score_breakdown", return_value=[]), \
             patch.object(activity, "get_compliance_assessments", return_value=[]), \
             patch.object(activity, "get_assessment_controls", return_value=[]), \
             patch.object(activity, "get_connection"), \
             patch.object(activity, "set_tenant_context"), \
             patch.object(activity, "upsert_compliance_score"), \
             patch.object(activity, "upsert_assessment"), \
             patch.object(activity, "upsert_assessment_control") as mock_upsert_ac, \
             patch.object(activity, "mark_tenant_synced"):
            result = activity.main(sample_tenant)

        assert result["success"] is True
        mock_get_ctrls.assert_not_called()
        mock_upsert_ac.assert_not_called()

    def test_returns_failure_on_exception(self, sample_tenant, activity):
        with patch.object(activity, "get_graph_client", side_effect=RuntimeError("boom")):
            result = activity.main(sample_tenant)

        assert result["success"] is False
        assert "boom" in result["error"]


class TestNormalizeAssessment:
    def test_handles_snake_case_sdk_keys(self, activity):
        a = {"display_name": "Test", "compliance_score": 85, "id": "a1"}
        result = activity._normalize_assessment(a)
        assert result["displayName"] == "Test"
        assert result["complianceScore"] == 85


class TestNormalizeControl:
    def test_falls_back_through_key_chain(self, activity):
        c = {"control_name": "MFA", "id": "c1"}
        result = activity._normalize_control(c)
        assert result["displayName"] == "MFA"

    def test_uses_display_name_first(self, activity):
        c = {"displayName": "Primary", "controlName": "Fallback", "id": "c1"}
        result = activity._normalize_control(c)
        assert result["displayName"] == "Primary"

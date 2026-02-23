"""Tests for shared.sql_client — connection, context, upserts, regulation extraction."""
from unittest.mock import patch, MagicMock, call
import pytest


class TestGetConnection:
    def test_uses_env_var(self, mock_env):
        with patch("shared.sql_client.pyodbc.connect") as mock_connect:
            from shared.sql_client import get_connection
            conn = get_connection()
        mock_connect.assert_called_once()
        assert "fake" in mock_connect.call_args[0][0]


class TestSetTenantContext:
    def test_executes_two_stored_procs(self, mock_connection):
        from shared.sql_client import set_tenant_context
        set_tenant_context(mock_connection, "test-uuid")
        cursor = mock_connection.cursor.return_value
        assert cursor.execute.call_count == 2
        first_sql = cursor.execute.call_args_list[0][0][0]
        assert "tenant_id" in first_sql


class TestSetAdminContext:
    def test_executes_one_stored_proc(self, mock_connection):
        from shared.sql_client import set_admin_context
        set_admin_context(mock_connection)
        cursor = mock_connection.cursor.return_value
        cursor.execute.assert_called_once()
        assert "is_admin" in cursor.execute.call_args[0][0]


class TestGetActiveTenants:
    def test_maps_columns_to_dicts(self, mock_connection, mock_cursor):
        mock_cursor.description = [("tenant_id",), ("display_name",)]
        mock_cursor.fetchall.return_value = [
            ("uuid-1", "Tenant A"),
            ("uuid-2", "Tenant B"),
        ]
        from shared.sql_client import get_active_tenants
        result = get_active_tenants(mock_connection)
        assert len(result) == 2
        assert result[0]["tenant_id"] == "uuid-1"
        assert result[1]["display_name"] == "Tenant B"


class TestUpsertSecureScore:
    def test_extracts_date_and_commits(self, mock_connection, sample_secure_score):
        from shared.sql_client import upsert_secure_score
        upsert_secure_score(mock_connection, "tid", sample_secure_score)

        cursor = mock_connection.cursor.return_value
        args = cursor.execute.call_args[0]
        assert "tid" == args[1]
        assert "2026-02-22" == args[2]
        mock_connection.commit.assert_called_once()


class TestUpsertControlProfiles:
    def test_handles_empty_state_updates(self, mock_connection):
        from shared.sql_client import upsert_control_profiles
        profile = {"id": "ctrl1", "controlStateUpdates": []}
        upsert_control_profiles(mock_connection, "tid", [profile])

        cursor = mock_connection.cursor.return_value
        args = cursor.execute.call_args[0]
        # latest_state and assigned_to should be None
        assert args[11] is None  # control_state
        assert args[12] is None  # assigned_to

    def test_extracts_latest_state(self, mock_connection):
        from shared.sql_client import upsert_control_profiles
        profile = {
            "id": "ctrl1",
            "controlStateUpdates": [
                {"state": "ignored", "assignedTo": "alice"},
                {"state": "active", "assignedTo": "bob"},
            ],
        }
        upsert_control_profiles(mock_connection, "tid", [profile])

        cursor = mock_connection.cursor.return_value
        args = cursor.execute.call_args[0]
        assert args[11] == "active"
        assert args[12] == "bob"


class TestExtractRegulation:
    def test_direct_regulation_field(self):
        from shared.sql_client import _extract_regulation
        assert _extract_regulation({"regulation": "SOC 2"}) == "SOC 2"

    def test_regulation_name_field(self):
        from shared.sql_client import _extract_regulation
        assert _extract_regulation({"regulationName": "ISO 27001"}) == "ISO 27001"

    def test_nested_compliance_standard(self):
        from shared.sql_client import _extract_regulation
        result = _extract_regulation({"complianceStandard": {"name": "NIST"}})
        assert result == "NIST"

    def test_returns_none_when_missing(self):
        from shared.sql_client import _extract_regulation
        assert _extract_regulation({}) is None


class TestMarkTenantSynced:
    def test_calls_update_and_commits(self, mock_connection):
        from shared.sql_client import mark_tenant_synced
        mark_tenant_synced(mock_connection, "uuid-1")
        mock_connection.commit.assert_called_once()

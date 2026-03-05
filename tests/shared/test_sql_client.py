"""Tests for shared.sql_client — SQLite connection, upserts, regulation extraction."""

from unittest.mock import patch, MagicMock


class TestGetConnection:
    def test_uses_env_var(self, monkeypatch):
        monkeypatch.setenv("SQLITE_DB_PATH", "/tmp/test.db")
        with patch("shared.sql_client.sqlite3.connect") as mock_connect:
            mock_connect.return_value = MagicMock()
            from shared.sql_client import get_connection

            get_connection()
        mock_connect.assert_called_once_with("/tmp/test.db", check_same_thread=False)


class TestSetTenantContext:
    def test_is_noop(self, mock_connection):
        from shared.sql_client import set_tenant_context

        set_tenant_context(mock_connection, "test-uuid")
        mock_connection.cursor.assert_not_called()


class TestSetAdminContext:
    def test_is_noop(self, mock_connection):
        from shared.sql_client import set_admin_context

        set_admin_context(mock_connection)
        mock_connection.cursor.assert_not_called()


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
        params = cursor.execute.call_args[0][1]
        assert params[0] == "tid"
        assert params[1] == "2026-02-22"
        mock_connection.commit.assert_called_once()


class TestUpsertControlProfiles:
    def test_handles_empty_state_updates(self, mock_connection):
        from shared.sql_client import upsert_control_profiles

        profile = {"id": "ctrl1", "controlStateUpdates": []}
        upsert_control_profiles(mock_connection, "tid", [profile])

        cursor = mock_connection.cursor.return_value
        params = cursor.execute.call_args[0][1]
        assert params[10] is None  # control_state
        assert params[11] is None  # assigned_to

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
        params = cursor.execute.call_args[0][1]
        assert params[10] == "active"
        assert params[11] == "bob"


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

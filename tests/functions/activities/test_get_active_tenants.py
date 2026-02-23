"""Tests for the get_active_tenants activity."""
from unittest.mock import patch
import importlib
import pytest


@pytest.fixture
def activity():
    import activities.get_active_tenants as mod
    importlib.reload(mod)
    return mod


class TestGetActiveTenantsActivity:
    def test_returns_tenant_list(self, mock_connection, sample_tenant, activity):
        with patch.object(activity, "get_connection", return_value=mock_connection), \
             patch.object(activity, "set_admin_context") as mock_admin, \
             patch.object(activity, "get_active_tenants", return_value=[sample_tenant]):
            result = activity.main(None)

        assert result == [sample_tenant]
        mock_admin.assert_called_once_with(mock_connection)
        mock_connection.close.assert_called_once()

    def test_closes_connection_on_exception(self, mock_connection, activity):
        with patch.object(activity, "get_connection", return_value=mock_connection), \
             patch.object(activity, "set_admin_context"), \
             patch.object(activity, "get_active_tenants", side_effect=RuntimeError("db")):
            with pytest.raises(RuntimeError):
                activity.main(None)

        mock_connection.close.assert_called_once()

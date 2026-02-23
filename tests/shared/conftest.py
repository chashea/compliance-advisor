"""Shared conftest scoped to tests/shared/ — resets auth singleton between tests."""
import pytest


@pytest.fixture(autouse=True)
def reset_kv_singleton():
    import shared.auth as auth_module
    auth_module._kv_client = None
    yield
    auth_module._kv_client = None

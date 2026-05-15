"""Tests for shared.rate_limit — sliding-window rate limiter backends."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from shared.config import get_settings
    from shared.rate_limit import get_rate_limiter

    get_settings.cache_clear()
    get_rate_limiter.cache_clear()
    yield
    get_settings.cache_clear()
    get_rate_limiter.cache_clear()


# ── InMemoryRateLimiter ───────────────────────────────────────────


def test_inmemory_allows_within_quota():
    from shared.rate_limit import InMemoryRateLimiter

    limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        assert limiter.is_rate_limited("ip1") is False


def test_inmemory_blocks_over_quota():
    from shared.rate_limit import InMemoryRateLimiter

    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
    assert limiter.is_rate_limited("ip1") is False
    assert limiter.is_rate_limited("ip1") is False
    assert limiter.is_rate_limited("ip1") is True


def test_inmemory_isolates_keys():
    from shared.rate_limit import InMemoryRateLimiter

    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
    assert limiter.is_rate_limited("ip1") is False
    assert limiter.is_rate_limited("ip2") is False
    assert limiter.is_rate_limited("ip1") is True


def test_inmemory_window_expiry():
    from shared.rate_limit import InMemoryRateLimiter

    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
    with patch("shared.rate_limit.time.monotonic") as t:
        t.return_value = 0.0
        assert limiter.is_rate_limited("ip1") is False
        t.return_value = 30.0
        assert limiter.is_rate_limited("ip1") is True
        t.return_value = 61.0
        assert limiter.is_rate_limited("ip1") is False


# ── TableStorageRateLimiter ───────────────────────────────────────


def _fake_settings(backend="memory", account=""):
    s = MagicMock()
    s.RATE_LIMIT_BACKEND = backend
    s.RATE_LIMIT_MAX = 5
    s.RATE_LIMIT_WINDOW_SECONDS = 60
    s.RATE_LIMIT_STORAGE_ACCOUNT = account
    return s


def test_get_rate_limiter_defaults_to_memory():
    from shared import rate_limit

    with patch("shared.config.get_settings", return_value=_fake_settings(backend="memory")):
        limiter = rate_limit.get_rate_limiter()
    assert isinstance(limiter, rate_limit.InMemoryRateLimiter)


def test_get_rate_limiter_falls_back_when_no_account():
    from shared import rate_limit

    with patch("shared.config.get_settings", return_value=_fake_settings(backend="table", account="")):
        limiter = rate_limit.get_rate_limiter()
    assert isinstance(limiter, rate_limit.InMemoryRateLimiter)


def test_table_limiter_allows_when_no_existing_entity():
    from azure.core.exceptions import ResourceNotFoundError
    from shared.rate_limit import TableStorageRateLimiter

    limiter = TableStorageRateLimiter(max_requests=2, window_seconds=60, account_name="acct")
    fake_client = MagicMock()
    fake_client.get_entity.side_effect = ResourceNotFoundError()
    limiter._client = fake_client

    assert limiter.is_rate_limited("ip1") is False
    fake_client.create_entity.assert_called_once()


def test_table_limiter_blocks_when_quota_exceeded():
    import time as _time

    from shared.rate_limit import TableStorageRateLimiter

    limiter = TableStorageRateLimiter(max_requests=2, window_seconds=60, account_name="acct")
    fake_client = MagicMock()
    now = _time.time()
    existing = {
        "PartitionKey": "default",
        "RowKey": "ip1",
        "Timestamps": f"{now - 5:.3f},{now - 1:.3f}",
    }
    existing_md = MagicMock()
    existing_md.get.return_value = "etag-1"
    type(fake_client.get_entity.return_value).metadata = existing_md
    fake_client.get_entity.return_value = MagicMock(spec=dict)
    fake_client.get_entity.return_value.get = lambda key, default="": existing.get(key, default)
    fake_client.get_entity.return_value.metadata = {"etag": "etag-1"}
    limiter._client = fake_client

    assert limiter.is_rate_limited("ip1") is True
    fake_client.update_entity.assert_not_called()
    fake_client.create_entity.assert_not_called()


def test_table_limiter_sanitises_keys():
    from shared.rate_limit import TableStorageRateLimiter

    assert TableStorageRateLimiter._sanitise_key("a/b\\c#d?e") == "a_b_c_d_e"
    assert TableStorageRateLimiter._sanitise_key("") == "unknown"

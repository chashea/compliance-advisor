"""
Distributed rate limiting backends.

Two implementations are provided:

- ``InMemoryRateLimiter`` — per-process sliding-window counter. Suitable
  for local dev and single-instance deployments. State is lost on restart.

- ``TableStorageRateLimiter`` — sliding-window counter persisted in Azure
  Table Storage using the existing Functions storage account. Atomic via
  ETag-based optimistic concurrency. Multiple Function App instances see
  a consistent view, so the rate limit is enforced globally.

The active backend is selected by the ``RATE_LIMIT_BACKEND`` setting
(``memory`` or ``table``). The ``get_rate_limiter()`` helper memoises the
chosen instance.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from functools import lru_cache
from typing import Protocol

log = logging.getLogger(__name__)


class RateLimiter(Protocol):
    """A sliding-window rate limiter keyed by an opaque client identifier."""

    def is_rate_limited(self, key: str) -> bool:
        """Return True if ``key`` has exceeded the configured window quota."""


class InMemoryRateLimiter:
    """Per-process sliding-window rate limiter. Not safe across instances."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_rate_limited(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            timestamps = [t for t in self._store[key] if now - t < self.window_seconds]
            if len(timestamps) >= self.max_requests:
                self._store[key] = timestamps
                return True
            timestamps.append(now)
            self._store[key] = timestamps
            return False


class TableStorageRateLimiter:
    """Sliding-window rate limiter backed by Azure Table Storage.

    Each ``key`` is a single entity in the ``ratelimit`` table; the
    entity's ``Timestamps`` property is a comma-separated list of unix
    timestamps. Updates use ETag-based optimistic concurrency so concurrent
    increments cannot race past the quota.

    Authenticates via the Function App's managed identity
    (``DefaultAzureCredential``) — no connection string or shared key.
    """

    _TABLE_NAME = "ratelimit"
    _PARTITION_KEY = "default"

    def __init__(self, max_requests: int, window_seconds: int, account_name: str) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.account_name = account_name
        self._client = None
        self._client_lock = threading.Lock()

    def _get_client(self):
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    from azure.data.tables import TableServiceClient
                    from azure.identity import DefaultAzureCredential

                    endpoint = f"https://{self.account_name}.table.core.windows.net"
                    service = TableServiceClient(endpoint=endpoint, credential=DefaultAzureCredential())
                    try:
                        service.create_table_if_not_exists(self._TABLE_NAME)
                    except Exception:
                        log.exception("create_table_if_not_exists failed (continuing)")
                    self._client = service.get_table_client(self._TABLE_NAME)
        return self._client

    @staticmethod
    def _sanitise_key(key: str) -> str:
        # Azure table row keys cannot contain /, \, #, ?, or control chars.
        bad = "/\\#?\t\n\r"
        out = "".join("_" if c in bad else c for c in key)
        return out[:1024] or "unknown"

    def is_rate_limited(self, key: str) -> bool:
        from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError
        from azure.data.tables import UpdateMode

        client = self._get_client()
        row_key = self._sanitise_key(key)
        now = time.time()
        cutoff = now - self.window_seconds

        for attempt in range(3):
            try:
                entity = client.get_entity(self._PARTITION_KEY, row_key)
                etag = entity.metadata.get("etag")
                raw = entity.get("Timestamps", "")
                timestamps = [float(t) for t in raw.split(",") if t]
            except ResourceNotFoundError:
                entity = None
                etag = None
                timestamps = []

            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self.max_requests:
                return True

            timestamps.append(now)
            new_entity = {
                "PartitionKey": self._PARTITION_KEY,
                "RowKey": row_key,
                "Timestamps": ",".join(f"{t:.3f}" for t in timestamps),
            }

            try:
                if entity is None:
                    client.create_entity(new_entity)
                else:
                    client.update_entity(new_entity, mode=UpdateMode.REPLACE, etag=etag, match_condition="IfMatch")
                return False
            except ResourceModifiedError:
                log.debug("Rate-limit ETag conflict for key=%s attempt=%d", key, attempt)
                continue
            except Exception:
                log.exception("Rate limiter table-storage failure (failing open) for key=%s", key)
                return False

        log.warning("Rate-limit ETag retries exhausted for key=%s; failing open", key)
        return False


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    """Return the configured rate limiter, memoised for the process lifetime."""
    from shared.config import get_settings

    settings = get_settings()
    backend = (settings.RATE_LIMIT_BACKEND or "memory").lower()
    if backend == "table":
        if not settings.RATE_LIMIT_STORAGE_ACCOUNT:
            log.warning("RATE_LIMIT_BACKEND=table but RATE_LIMIT_STORAGE_ACCOUNT is unset — falling back to memory")
            return InMemoryRateLimiter(settings.RATE_LIMIT_MAX, settings.RATE_LIMIT_WINDOW_SECONDS)
        return TableStorageRateLimiter(
            max_requests=settings.RATE_LIMIT_MAX,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
            account_name=settings.RATE_LIMIT_STORAGE_ACCOUNT,
        )
    return InMemoryRateLimiter(settings.RATE_LIMIT_MAX, settings.RATE_LIMIT_WINDOW_SECONDS)

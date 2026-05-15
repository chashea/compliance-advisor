"""Tests for /health/deep and the hunt-uniqueness migration shape."""

from pathlib import Path
from unittest.mock import patch

import azure.functions as func
import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from shared.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _req() -> func.HttpRequest:
    return func.HttpRequest(method="GET", url="/api/health/deep", body=b"", headers={})


def _no_rate_limit():
    """Patch the rate limiter to never block in tests."""
    from unittest.mock import MagicMock

    limiter = MagicMock()
    limiter.is_rate_limited.return_value = False
    return patch("shared.rate_limit.get_rate_limiter", return_value=limiter)


def test_health_deep_all_ok():
    from routes import admin

    with (
        _no_rate_limit(),
        patch.object(admin, "_check_db", return_value={"status": "ok", "latency_ms": 1}),
        patch.object(admin, "_check_keyvault", return_value={"status": "ok", "latency_ms": 2}),
        patch.object(admin, "_check_openai", return_value={"status": "ok", "latency_ms": 3}),
    ):
        resp = admin.health_deep(_req())

    import json
    body = json.loads(resp.get_body())
    assert resp.status_code == 200
    assert body["status"] == "healthy"
    assert set(body["components"]) == {"db", "keyvault", "openai"}


def test_health_deep_returns_503_when_any_component_errors():
    from routes import admin

    with (
        _no_rate_limit(),
        patch.object(admin, "_check_db", return_value={"status": "ok", "latency_ms": 1}),
        patch.object(admin, "_check_keyvault", return_value={"status": "error", "error": "boom"}),
        patch.object(admin, "_check_openai", return_value={"status": "ok", "latency_ms": 3}),
    ):
        resp = admin.health_deep(_req())

    import json
    assert resp.status_code == 503
    body = json.loads(resp.get_body())
    assert body["status"] == "unhealthy"
    assert body["components"]["keyvault"]["status"] == "error"


def test_health_deep_skipped_components_do_not_fail():
    from routes import admin

    with (
        _no_rate_limit(),
        patch.object(admin, "_check_db", return_value={"status": "ok", "latency_ms": 1}),
        patch.object(admin, "_check_keyvault", return_value={"status": "skipped", "reason": "x"}),
        patch.object(admin, "_check_openai", return_value={"status": "skipped", "reason": "y"}),
    ):
        resp = admin.health_deep(_req())

    assert resp.status_code == 200


def test_health_deep_honours_rate_limit():
    from unittest.mock import MagicMock

    from routes import admin

    limiter = MagicMock()
    limiter.is_rate_limited.return_value = True
    with patch("shared.rate_limit.get_rate_limiter", return_value=limiter):
        resp = admin.health_deep(_req())

    assert resp.status_code == 429


# ── Hunt-uniqueness migration ─────────────────────────────────────


def test_hunt_uniqueness_migration_present():
    mig = Path(__file__).resolve().parent.parent / "sql" / "migrations" / "0003_hunt_uniqueness.sql"
    assert mig.is_file(), f"expected migration at {mig}"
    text = mig.read_text()
    # Both natural keys are constrained
    assert "hunt_runs" in text and "UNIQUE" in text
    assert "hunt_results" in text
    assert "tenant_id" in text and "template_name" in text and "run_at" in text
    assert "run_id" in text and "finding_type" in text
    # Dedup happens BEFORE the constraint (so existing dup data doesn't block)
    runs_dedup = text.find("DELETE FROM hunt_runs")
    constraint = text.find("hunt_runs_uniq")
    assert runs_dedup < constraint, "dedup must precede the UNIQUE constraint"

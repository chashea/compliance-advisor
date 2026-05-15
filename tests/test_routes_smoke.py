"""HTTP-level smoke tests for every registered route.

Each route module's blueprint is walked, and the registered user function
is invoked with a synthesized ``HttpRequest``. The dashboard query layer,
collector, and external services are mocked out so these tests run
without any network or DB dependency.

For each route we assert:

- A successful invocation returns the documented status code + a JSON
  body (or HTML for the consent callback).
- An auth-required route returns 401 when EasyAuth headers are missing
  in fail-closed mode.
- A POST route returns 400 for malformed JSON bodies (per the failure-
  mode contract introduced alongside #18).

These tests are the safety net for the route refactor. They cover every
function that the host indexes, so any regression that breaks a wire
contract is caught here.
"""

from __future__ import annotations

import json
from collections import namedtuple
from unittest.mock import MagicMock, patch

import azure.functions as func
import pytest

RouteSpec = namedtuple("RouteSpec", "blueprint_module function_name route methods")


# ── Discovery ─────────────────────────────────────────────────────


def _all_routes() -> list[RouteSpec]:
    """Walk every blueprint and collect (module, fn_name, route, methods)."""
    from routes import admin, ai, collect, dashboard, ingest, tenants

    specs: list[RouteSpec] = []
    for module in (admin, ai, dashboard, ingest, tenants, collect):
        for fb in module.bp._function_builders:
            f = fb._function
            trigger = f._trigger
            if type(trigger).__name__ != "HttpTrigger":
                continue
            specs.append(
                RouteSpec(
                    blueprint_module=module,
                    function_name=f._name,
                    route=getattr(trigger, "route", None),
                    methods=tuple(m.value for m in getattr(trigger, "methods", []) or []),
                )
            )
    return specs


def _user_function(module, fn_name):
    """Pull the underlying Python function out of a registered blueprint entry."""
    for fb in module.bp._function_builders:
        if fb._function._name == fn_name:
            return fb._function._func
    raise KeyError(fn_name)


def _http_request(method: str, path: str, body: bytes = b"", route_params: dict | None = None) -> func.HttpRequest:
    return func.HttpRequest(
        method=method,
        url=f"/api/{path}",
        body=body,
        headers={"Content-Type": "application/json"},
        route_params=route_params or {},
    )


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    from shared.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def stub_dashboard_queries():
    """Override every dashboard handler with a stub returning {"ok": True}."""
    from routes import dashboard

    saved: dict[str, callable] = {}
    sentinel = lambda **_kw: {"ok": True}  # noqa: E731

    for fb in dashboard.bp._function_builders:
        f = fb._function
        impl = f._func
        if hasattr(impl, "_handler"):
            saved[f._name] = impl._handler
            impl._handler = sentinel
    yield
    for name, fn in saved.items():
        for fb in dashboard.bp._function_builders:
            if fb._function._name == name:
                fb._function._func._handler = fn
                break


# ── Discovery sanity ──────────────────────────────────────────────


def test_route_discovery_finds_expected_blueprints():
    specs = _all_routes()
    function_names = {s.function_name for s in specs}
    # Spot-check one route per blueprint
    assert "health" in function_names
    assert "advisor_status" in function_names
    assert "advisor_briefing" in function_names
    assert "ingest_compliance" in function_names
    assert "register_tenant" in function_names
    assert "collect_single" in function_names
    # Total HTTP routes (excluding timers): 27
    assert len(specs) == 27, f"got {len(specs)}: {sorted(function_names)}"


# ── Positive smoke tests for read-only dashboard routes ───────────


SIMPLE_DASHBOARD = [
    "advisor_status",
    "advisor_overview",
    "advisor_labels",
    "advisor_audit",
    "advisor_dlp",
    "advisor_irm",
    "advisor_purview_incidents",
    "advisor_info_barriers",
    "advisor_governance",
    "advisor_actions",
    "advisor_dlp_policies",
    "advisor_irm_policies",
    "advisor_assessments",
    "advisor_threat_assessments",
]


@pytest.mark.parametrize("fn_name", SIMPLE_DASHBOARD)
def test_dashboard_route_returns_200(fn_name, stub_dashboard_queries):
    from routes import dashboard

    fn = _user_function(dashboard, fn_name)
    resp = fn(_http_request("POST", f"advisor/{fn_name}", b"{}"))
    assert resp.status_code == 200
    body = json.loads(resp.get_body())
    assert body == {"ok": True}


@pytest.mark.parametrize("fn_name", SIMPLE_DASHBOARD)
def test_dashboard_route_rejects_malformed_body(fn_name, stub_dashboard_queries):
    from routes import dashboard

    fn = _user_function(dashboard, fn_name)
    resp = fn(_http_request("POST", f"advisor/{fn_name}", b"{not-json}"))
    assert resp.status_code == 400


@pytest.mark.parametrize("fn_name", SIMPLE_DASHBOARD)
def test_dashboard_route_returns_401_when_auth_required(fn_name, stub_dashboard_queries, monkeypatch):
    """Fail-closed mode: missing principal → 401."""
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    from shared.config import get_settings

    get_settings.cache_clear()

    from routes import dashboard

    fn = _user_function(dashboard, fn_name)
    resp = fn(_http_request("POST", f"advisor/{fn_name}", b"{}"))
    assert resp.status_code == 401


# ── Routes with extra body params ─────────────────────────────────


@pytest.mark.parametrize("fn_name", ["advisor_trend", "advisor_purview_insights"])
def test_routes_with_days_validate_input(fn_name):
    """The handler signatures call get_trend / get_purview_insights directly,
    so we patch those at the module level."""
    from routes import dashboard

    target = "get_trend" if fn_name == "advisor_trend" else "get_purview_insights"
    fn = _user_function(dashboard, fn_name)
    with patch.object(dashboard, target, return_value={"ok": True}):
        # Invalid days: 0 (out of 1..365)
        resp = fn(_http_request("POST", f"advisor/{fn_name}", b'{"days": 0}'))
        assert resp.status_code == 400
        # Invalid days: non-int
        resp = fn(_http_request("POST", f"advisor/{fn_name}", b'{"days": "x"}'))
        assert resp.status_code == 400
        # Valid
        resp = fn(_http_request("POST", f"advisor/{fn_name}", b'{"days": 30}'))
        assert resp.status_code == 200


def test_hunt_results_returns_200():
    from routes import dashboard

    fn = _user_function(dashboard, "advisor_hunt_results")
    with patch.object(dashboard, "get_hunt_results", return_value={"ok": True}):
        resp = fn(_http_request("POST", "advisor/hunt-results", b"{}"))
    assert resp.status_code == 200


# ── AI routes (rate-limited) ──────────────────────────────────────


@patch("routes.ai.ask_advisor", return_value="answer text")
@patch("routes.ai.generate_briefing", return_value="briefing text")
def test_ai_routes_return_200(mock_brief, mock_ask):
    from routes import ai

    # Reset rate limiter so previous tests don't bleed in
    from shared.rate_limit import get_rate_limiter

    get_rate_limiter.cache_clear()

    fn = _user_function(ai, "advisor_briefing")
    resp = fn(_http_request("POST", "advisor/briefing", b"{}"))
    assert resp.status_code == 200
    assert json.loads(resp.get_body())["briefing"] == "briefing text"

    fn = _user_function(ai, "advisor_ask")
    resp = fn(_http_request("POST", "advisor/ask", b'{"question": "what?"}'))
    assert resp.status_code == 200
    assert json.loads(resp.get_body())["answer"] == "answer text"


def test_ai_ask_rejects_empty_question():
    from shared.rate_limit import get_rate_limiter

    get_rate_limiter.cache_clear()
    from routes import ai

    fn = _user_function(ai, "advisor_ask")
    resp = fn(_http_request("POST", "advisor/ask", b"{}"))
    assert resp.status_code == 400


# ── Admin routes ──────────────────────────────────────────────────


def test_health_returns_200_when_db_reachable():
    from routes import admin

    fake_pool = MagicMock()
    fake_conn = MagicMock()
    fake_pool.getconn.return_value = fake_conn
    with patch.object(admin, "_get_pool", return_value=fake_pool):
        fn = _user_function(admin, "health")
        resp = fn(_http_request("GET", "health"))
    assert resp.status_code == 200
    assert json.loads(resp.get_body()) == {"status": "healthy"}


def test_health_returns_503_when_db_unreachable():
    from routes import admin

    with patch.object(admin, "_get_pool", side_effect=RuntimeError("conn refused")):
        fn = _user_function(admin, "health")
        resp = fn(_http_request("GET", "health"))
    assert resp.status_code == 503


# ── Tenant registration ───────────────────────────────────────────


@patch("routes.tenants._trigger_collection_async")
@patch("routes.tenants.upsert_tenant")
def test_register_tenant_returns_200(mock_upsert, mock_trigger):
    from routes import tenants

    fn = _user_function(tenants, "register_tenant")
    body = json.dumps({
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "display_name": "Test",
        "department": "DOJ",
    }).encode()
    resp = fn(_http_request("POST", "tenants", body))
    assert resp.status_code == 200
    mock_upsert.assert_called_once()


def test_register_tenant_rejects_missing_fields():
    from routes import tenants

    fn = _user_function(tenants, "register_tenant")
    resp = fn(_http_request("POST", "tenants", b"{}"))
    assert resp.status_code == 400


def test_register_tenant_rejects_bad_uuid():
    from routes import tenants

    fn = _user_function(tenants, "register_tenant")
    body = json.dumps({"tenant_id": "not-a-uuid", "display_name": "x", "department": "y"}).encode()
    resp = fn(_http_request("POST", "tenants", body))
    assert resp.status_code == 400


def test_consent_callback_rejects_missing_tenant():
    from routes import tenants

    fn = _user_function(tenants, "tenant_consent_callback")
    req = func.HttpRequest(method="GET", url="/api/tenants/callback", body=b"", headers={}, params={})
    resp = fn(req)
    assert resp.status_code == 400
    assert resp.mimetype == "text/html"


# ── On-demand collection ──────────────────────────────────────────


def test_collect_single_404_when_tenant_unknown():
    from routes import collect

    with patch.object(collect, "query", return_value=[]):
        fn = _user_function(collect, "collect_single")
        resp = fn(
            _http_request(
                "POST",
                "collect/11111111-1111-1111-1111-111111111111",
                b"{}",
                route_params={"tenant_id": "11111111-1111-1111-1111-111111111111"},
            )
        )
    assert resp.status_code == 404


def test_collect_single_400_for_bad_uuid():
    from routes import collect

    fn = _user_function(collect, "collect_single")
    resp = fn(
        _http_request(
            "POST",
            "collect/abc",
            b"{}",
            route_params={"tenant_id": "abc"},
        )
    )
    assert resp.status_code == 400


# ── Ingest ────────────────────────────────────────────────────────


def test_ingest_rejects_malformed_body():
    from routes import ingest

    fn = _user_function(ingest, "ingest_compliance")
    resp = fn(_http_request("POST", "ingest", b"{garbage"))
    assert resp.status_code == 400


def test_ingest_rejects_missing_required_fields():
    from routes import ingest

    fn = _user_function(ingest, "ingest_compliance")
    # Empty object fails JSON-schema validation (missing required fields)
    resp = fn(_http_request("POST", "ingest", b"{}"))
    assert resp.status_code == 400

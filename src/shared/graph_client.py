"""
Microsoft Graph API client — Compliance Manager & Secure Score.

Uses the msgraph-beta-sdk for typed, paginated access to Compliance Manager
endpoints. Falls back to raw HTTP for v1.0 Secure Score endpoints if needed.
Includes retry logic with exponential backoff for 429 / 5xx responses.

SDK benefits over raw HTTP:
  - Typed response models (assessment.display_name, control.implementation_status)
  - Built-in pagination (no manual @odata.nextLink handling)
  - Built-in retry with Retry-After header support
  - Authentication handled by azure-identity credential (no manual token mgmt)
"""
import asyncio
import concurrent.futures
import logging
from typing import Any, Generator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from msgraph_beta import GraphServiceClient
from msgraph_beta.generated.security.compliance_manager.assessments.assessments_request_builder import (
    AssessmentsRequestBuilder,
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_BETA = "https://graph.microsoft.com/beta"
MAX_DAYS   = 90
log        = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Async-to-sync bridge
# Azure Functions v1 programming model is synchronous. The Graph SDK is async.
# We run SDK coroutines in a dedicated thread with its own event loop.
# ═════════════════════════════════════════════════════════════════════════════

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_async(coro) -> Any:
    """Run an async coroutine from synchronous code, safe in any context."""
    return _executor.submit(asyncio.run, coro).result()


def _model_to_dict(obj) -> dict:
    """Convert a msgraph model object to a plain dict, handling None fields."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        # msgraph models expose additional_data and backing_store
        result = {}
        for key in dir(obj):
            if key.startswith("_") or key in ("additional_data", "backing_store",
                                                "odata_type", "serialize",
                                                "create_from_discriminator_value"):
                continue
            try:
                val = getattr(obj, key)
                if callable(val):
                    continue
                if val is not None:
                    result[key] = val
            except Exception:
                continue
        # Merge any additional_data (Graph SDK stashes unknown props here)
        if hasattr(obj, "additional_data") and obj.additional_data:
            result.update(obj.additional_data)
        return result
    except Exception:
        return {}


# ═════════════════════════════════════════════════════════════════════════════
# Compliance Manager — SDK-based (preferred)
# ═════════════════════════════════════════════════════════════════════════════

def get_compliance_assessments_sdk(client: GraphServiceClient) -> list[dict]:
    """
    Fetch all Compliance Manager assessments using the typed Graph SDK.
    Returns a list of dicts with assessment metadata.
    """
    async def _fetch():
        try:
            result = await client.security.compliance_manager.assessments.get()
            if result and result.value:
                return [_model_to_dict(a) for a in result.value]
            return []
        except Exception as e:
            log.warning("SDK: assessments endpoint failed: %s", e)
            return []

    return _run_async(_fetch())


def get_assessment_controls_sdk(
    client: GraphServiceClient, assessment_id: str
) -> list[dict]:
    """
    Fetch all controls (improvement actions) for a specific assessment.
    Includes solution/remediation fields: implementationDetails, testPlan,
    managementResponse, evidenceOfCompletion, service, scoreImpact.
    """
    async def _fetch():
        try:
            result = (
                await client.security.compliance_manager
                .assessments.by_compliance_assessment_id(assessment_id)
                .controls.get()
            )
            if result and result.value:
                controls = []
                for c in result.value:
                    d = _model_to_dict(c)
                    # Ensure solution fields are captured even if stored
                    # in additional_data by the SDK
                    if hasattr(c, 'additional_data') and c.additional_data:
                        for field in ('implementationDetails', 'testPlan',
                                      'managementResponse', 'evidenceOfCompletion',
                                      'service', 'scoreImpact'):
                            if field not in d and field in c.additional_data:
                                d[field] = c.additional_data[field]
                    controls.append(d)
                return controls
            return []
        except Exception as e:
            log.warning("SDK: controls for assessment %s failed: %s",
                        assessment_id, e)
            return []

    return _run_async(_fetch())


def get_compliance_score_sdk(client: GraphServiceClient) -> dict | None:
    """
    Return the tenant's overall compliance score from the SDK.
    Returns dict with currentScore, maxScore, etc. or None.
    """
    async def _fetch():
        try:
            result = await client.security.compliance_manager.compliance_score.get()
            return _model_to_dict(result) if result else None
        except Exception as e:
            log.info("SDK: complianceScore endpoint unavailable: %s", e)
            return None

    return _run_async(_fetch())


def get_compliance_score_breakdown_sdk(client: GraphServiceClient) -> list[dict]:
    """
    Return compliance score broken down by category using the SDK.
    """
    async def _fetch():
        try:
            result = (
                await client.security.compliance_manager
                .compliance_score.categories.get()
            )
            if result and result.value:
                return [_model_to_dict(c) for c in result.value]
            return []
        except Exception as e:
            log.info("SDK: category breakdown not available: %s", e)
            return []

    return _run_async(_fetch())


# ═════════════════════════════════════════════════════════════════════════════
# Legacy raw-HTTP helpers (for Secure Score v1.0 endpoints + fallback)
# ═════════════════════════════════════════════════════════════════════════════

def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _get(url: str, token: str) -> dict:
    resp = _session().get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _paginate(url: str, token: str) -> Generator[dict, None, None]:
    """Follow @odata.nextLink pagination and yield every item."""
    while url:
        data = _get(url, token)
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")


def get_secure_scores(token: str, days: int = MAX_DAYS) -> list[dict]:
    """Return up to `days` daily Secure Score snapshots, newest first."""
    if not isinstance(days, int) or not (1 <= days <= MAX_DAYS):
        raise ValueError(f"days must be an integer between 1 and {MAX_DAYS}")
    url = f"{GRAPH_BASE}/security/secureScores?$top={days}"
    return list(_paginate(url, token))


def get_control_profiles(token: str) -> list[dict]:
    """Return the full Secure Score control profile catalog for this tenant."""
    url = f"{GRAPH_BASE}/security/secureScoreControlProfiles"
    return list(_paginate(url, token))


# ═════════════════════════════════════════════════════════════════════════════
# Legacy raw-HTTP Compliance Manager endpoints (fallback if SDK unavailable)
# ═════════════════════════════════════════════════════════════════════════════

def get_compliance_assessments(token: str) -> list[dict]:
    """Return all Compliance Manager assessments via raw HTTP (fallback)."""
    preferred = f"{GRAPH_BETA}/security/complianceManager/assessments"
    try:
        return list(_paginate(preferred, token))
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            log.warning("complianceManager/assessments not available via HTTP, "
                        "trying alternative endpoint")
            alt = f"{GRAPH_BETA}/compliance/complianceManagement/assessments"
            try:
                return list(_paginate(alt, token))
            except requests.HTTPError:
                log.warning("No Compliance Manager assessment API available")
                return []
        raise


def get_assessment_controls(token: str, assessment_id: str) -> list[dict]:
    """Return all controls for a specific assessment via raw HTTP (fallback).
    Includes solution/remediation fields when available from the API."""
    # Request solution detail fields via $select to ensure they're returned
    select = ("id,displayName,controlFamily,controlCategory,"
              "implementationStatus,testStatus,score,maxScore,owner,actionUrl,"
              "implementationDetails,testPlan,managementResponse,"
              "evidenceOfCompletion,service,scoreImpact")
    url = (f"{GRAPH_BETA}/security/complianceManager/assessments/"
           f"{assessment_id}/controls?$select={select}")
    try:
        return list(_paginate(url, token))
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            alt = (f"{GRAPH_BETA}/compliance/complianceManagement/assessments/"
                   f"{assessment_id}/controls?$select={select}")
            try:
                return list(_paginate(alt, token))
            except requests.HTTPError:
                log.warning("Could not fetch controls for assessment %s",
                            assessment_id)
                return []
        raise


def get_compliance_score(token: str) -> dict | None:
    """Return the tenant's overall compliance score via raw HTTP (fallback)."""
    url = f"{GRAPH_BETA}/security/complianceManager/complianceScore"
    try:
        return _get(url, token)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            log.info("complianceScore endpoint unavailable via HTTP")
            return None
        raise


def get_compliance_score_breakdown(token: str) -> list[dict]:
    """Return compliance score by category via raw HTTP (fallback)."""
    url = f"{GRAPH_BETA}/security/complianceManager/complianceScore/categories"
    try:
        return list(_paginate(url, token))
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (404, 400):
            log.info("Compliance score category breakdown not available via HTTP")
            return []
        raise

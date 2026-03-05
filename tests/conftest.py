"""Root conftest.py — shared pytest fixtures for the compliance-advisor test suite."""
import sys
from unittest.mock import MagicMock

import pytest


# ── Environment variables ──────────────────────────────────────────────────────

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", ":memory:")
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://fake-search.search.windows.net")
    monkeypatch.setenv("AZURE_SEARCH_INDEX_NAME", "compliance-knowledge")


# ── SQL / SQLite ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_cursor():
    cursor = MagicMock()
    cursor.description = [("col1",)]
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    return conn


# ── AI Search ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_search_client():
    client = MagicMock()
    client.search.return_value = iter([])
    client.upload_documents.return_value = []
    return client


# ── Sample data ───────────────────────────────────────────────────────────────

@pytest.fixture
def sample_tenant():
    return {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "display_name": "Acme Corp",
        "region": "us-east",
        "department": "Finance",
        "department_head": "Jane Smith",
        "risk_tier": "High",
        "app_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "kv_secret_name": "tenant-acme-secret",
    }


@pytest.fixture
def sample_secure_score():
    return {
        "createdDateTime": "2026-02-22T00:00:00Z",
        "currentScore": 72.5,
        "maxScore": 100.0,
        "licensedUserCount": 500,
        "activeUserCount": 450,
        "controlScores": [
            {
                "controlName": "MFARegistrationV2",
                "controlCategory": "Identity",
                "score": 9.0,
                "maxScore": 9.0,
                "description": "MFA registration completed",
            }
        ],
        "averageComparativeScores": [
            {"basis": "Industry", "basisValue": "Technology", "averageScore": 68.0}
        ],
    }


@pytest.fixture
def sample_assessment():
    return {
        "id": "assess-001",
        "displayName": "NIST 800-53",
        "description": "NIST framework assessment",
        "status": "active",
        "regulation": "NIST 800-53",
        "complianceScore": 78.5,
        "passedControls": 120,
        "failedControls": 34,
        "totalControls": 154,
        "createdDateTime": "2026-01-01T00:00:00Z",
        "lastModifiedDateTime": "2026-02-20T00:00:00Z",
    }


@pytest.fixture
def sample_control():
    return {
        "id": "ctrl-001",
        "displayName": "Multi-Factor Authentication",
        "controlFamily": "Identity",
        "controlCategory": "Access Control",
        "implementationStatus": "implemented",
        "testStatus": "passed",
        "score": 8.0,
        "maxScore": 10.0,
        "scoreImpact": "high",
        "owner": "IT Security",
        "actionUrl": "https://compliance.microsoft.com/action/1",
        "implementationDetails": "MFA enforced via Conditional Access",
        "testPlan": "Verify CA policy",
        "managementResponse": "Accepted",
        "evidenceOfCompletion": "CA policy exported 2026-02-01",
        "service": "Azure AD",
    }

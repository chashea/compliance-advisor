"""Contract tests against Microsoft-published example Graph responses.

These tests defend against schema drift in the upstream Microsoft Graph
APIs. Each fixture is the canonical example response from the Microsoft
Learn docs for the endpoint at the time of the audit (May 2026 / PR #14
follow-up). When Microsoft changes a response shape, our parsers should
either (a) keep working because we extract via .get() with defaults, or
(b) fail loudly here so we notice before customers do.

We mock the HTTP layer (``_paginate`` / ``sess.get``) and feed the
fixture through the real parser to catch shape regressions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── Fixtures: canonical Graph API responses (from Microsoft Learn) ──


SENSITIVITY_LABEL_V1_FIXTURE = [
    # Mirrors the example body of /security/dataSecurityAndGovernance/sensitivityLabels
    # https://learn.microsoft.com/graph/api/tenantdatasecurityandgovernance-list-sensitivitylabels
    {
        "id": "abc-123",
        "name": "Confidential",
        "displayName": "Confidential",
        "description": "Used for confidential org data",
        "color": "#FF8C00",
        "isActive": True,
        "priority": 1,
        "toolTip": "Apply to confidential content",
        "hasProtection": True,
        "applicableTo": ["file", "email"],
        "applicationMode": "automatic",
        "isEndpointProtectionEnabled": True,
    },
    {
        "id": "abc-456",
        "name": "Public",
        "displayName": "Public",
        "isActive": True,
    },
]


ALERT_V2_FIXTURE = [
    # Mirrors /security/alerts_v2 example
    # https://learn.microsoft.com/graph/api/security-list-alerts_v2
    {
        "id": "alert-1",
        "title": "Suspicious file upload",
        "severity": "high",
        "status": "newAlert",
        "category": "ExfiltrationCustomPolicy",
        "createdDateTime": "2026-01-15T10:30:00Z",
        "resolvedDateTime": None,
        "description": "User uploaded sensitive file",
        "assignedTo": "alice@contoso.com",
        "classification": "truePositive",
        "determination": "malicious",
        "recommendedActions": "Review the alert",
        "incidentId": "incident-1",
        "mitreTechniques": ["T1567"],
        "evidence": [{"@odata.type": "#microsoft.graph.security.fileEvidence"}],
        "policyName": "DLP-financial-data",
        "serviceSource": "microsoftDataLossPrevention",
    },
]


INCIDENT_FIXTURE = [
    # https://learn.microsoft.com/graph/api/security-list-incidents
    {
        "id": "incident-1",
        "displayName": "Multi-stage incident on multiple endpoints",
        "severity": "high",
        "status": "active",
        "classification": "truePositive",
        "determination": "malware",
        "createdDateTime": "2026-02-10T12:00:00Z",
        "lastUpdateDateTime": "2026-02-10T15:00:00Z",
        "assignedTo": "soc@contoso.com",
        "alerts": [
            {"id": "alert-1", "serviceSource": "microsoftDataLossPrevention"},
            {"id": "alert-2", "serviceSource": "microsoftInsiderRiskManagement"},
        ],
    },
]


SECURE_SCORE_FIXTURE = {
    # GET /security/secureScores?$top=30 example
    # https://learn.microsoft.com/graph/api/security-list-securescores
    "value": [
        {
            "id": "score-1",
            "currentScore": 142.5,
            "maxScore": 500.0,
            "createdDateTime": "2026-03-01T00:00:00Z",
            "controlScores": [
                {
                    "controlCategory": "Data",
                    "controlName": "Sensitivity-label-policies",
                    "score": 8.0,
                },
                {
                    "controlCategory": "Identity",
                    "controlName": "MFA",
                    "score": 12.0,
                },
            ],
        }
    ]
}


SECURE_SCORE_PROFILES_FIXTURE = [
    # /security/secureScoreControlProfiles filtered by Data category
    {
        "id": "Sensitivity-label-policies",
        "controlCategory": "Data",
        "maxScore": 10.0,
        "title": "Configure sensitivity label policies",
    },
    {
        "id": "Retention-policies",
        "controlCategory": "Data",
        "maxScore": 15.0,
        "title": "Enable retention policies",
    },
]


HUNTING_QUERY_FIXTURE = {
    # POST /security/runHuntingQuery example
    # https://learn.microsoft.com/graph/api/security-security-runhuntingquery
    "schema": [
        {"name": "Timestamp", "type": "DateTime"},
        {"name": "DeviceName", "type": "String"},
        {"name": "ActionType", "type": "String"},
    ],
    "results": [
        {
            "Timestamp": "2026-04-01T12:00:00Z",
            "DeviceName": "DESKTOP-001",
            "ActionType": "FileUploaded",
        }
    ],
}


# ── Tests ─────────────────────────────────────────────────────────


class TestSensitivityLabels:
    def test_v1_response_parses_to_persist_shape(self):
        """Sensitivity labels from v1.0/dataSecurityAndGovernance must
        produce dicts that persist_payload accepts."""
        from collector import compliance_client

        with patch.object(compliance_client, "_paginate", return_value=SENSITIVITY_LABEL_V1_FIXTURE):
            labels = compliance_client.get_sensitivity_labels(token="fake")

        assert len(labels) == 2
        first = labels[0]
        # Required by persist._persist_sensitivity_labels
        assert first["label_id"] == "abc-123"
        assert first["name"] == "Confidential"
        assert first["color"] == "#FF8C00"
        assert first["has_protection"] is True
        assert first["applicable_to"] == "file, email"  # list → comma-joined
        assert first["application_mode"] == "automatic"

        second = labels[1]
        assert second["label_id"] == "abc-456"
        # Defaults applied for missing fields
        assert second["color"] == ""
        assert second["has_protection"] is False
        assert second["priority"] == 0


class TestAlertsV2:
    @pytest.fixture
    def patched_session(self):
        from collector import compliance_client

        # Build a fake response object
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"value": ALERT_V2_FIXTURE}
        fake_resp.status_code = 200
        fake_resp.raise_for_status.return_value = None

        with patch.object(compliance_client, "_paginate", return_value=ALERT_V2_FIXTURE):
            yield

    def test_dlp_alert_parses(self, patched_session):
        from collector import compliance_client

        alerts = compliance_client.get_dlp_alerts(token="fake")
        assert len(alerts) == 1
        a = alerts[0]
        assert a["alert_id"] == "alert-1"
        assert a["severity"] == "high"
        assert a["status"] == "newAlert"
        assert a["created"] == "2026-01-15T10:30:00Z"
        assert a["classification"] == "truePositive"
        assert a["incident_id"] == "incident-1"
        # MITRE techniques: list → string-ish form (parser dependent)
        assert "T1567" in str(a["mitre_techniques"])

    def test_irm_alert_parses(self):
        from collector import compliance_client

        irm_fixture = [{**ALERT_V2_FIXTURE[0], "serviceSource": "microsoftInsiderRiskManagement"}]
        with patch.object(compliance_client, "_paginate", return_value=irm_fixture):
            alerts = compliance_client.get_irm_alerts(token="fake")
        assert len(alerts) == 1
        assert alerts[0]["alert_id"] == "alert-1"


class TestIncidents:
    def test_purview_incident_parses(self):
        from collector import compliance_client

        # get_purview_incidents takes incidents AND alerts to correlate
        with patch.object(compliance_client, "_paginate", return_value=INCIDENT_FIXTURE):
            incidents = compliance_client.get_purview_incidents(
                token="fake",
                purview_alerts=[
                    {"alert_id": "alert-1"},
                    {"alert_id": "alert-2"},
                ],
            )
        assert len(incidents) == 1
        i = incidents[0]
        assert i["incident_id"] == "incident-1"
        assert i["severity"] == "high"
        assert i["status"] == "active"
        assert i["classification"] == "truePositive"
        # Both alerts in the fixture are Purview-correlated
        assert i["purview_alerts_count"] == 2


class TestSecureScores:
    def test_secure_score_with_data_category_breakdown(self):
        """Secure Score response must yield current_score + max_score
        plus the data_current_score / data_max_score derived fields."""
        from collector import compliance_client

        # Two HTTP calls under the hood: secureScores GET, then
        # secureScoreControlProfiles via _paginate.
        fake_resp = MagicMock()
        fake_resp.json.return_value = SECURE_SCORE_FIXTURE
        fake_resp.raise_for_status.return_value = None

        fake_session = MagicMock()
        fake_session.get.return_value = fake_resp

        with (
            patch.object(compliance_client, "_session", return_value=fake_session),
            patch.object(compliance_client, "_paginate", return_value=SECURE_SCORE_PROFILES_FIXTURE),
        ):
            scores = compliance_client.get_secure_scores(token="fake", days=1)

        assert len(scores) == 1
        s = scores[0]
        assert s["current_score"] == 142.5
        assert s["max_score"] == 500.0
        # Data category breakdown computed from controlScores ∩ profiles
        assert s["data_current_score"] == 8.0  # only Sensitivity-label-policies in Data category
        # data_max is the sum of ALL Data-category profile maxes (the achievable ceiling),
        # not just the controls present in the current score
        assert s["data_max_score"] == 25.0  # 10 + 15


class TestHuntingQueryResults:
    def test_run_hunting_query_parses(self):
        from collector.hunter.graph import run_hunting_query

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = HUNTING_QUERY_FIXTURE

        fake_session = MagicMock()
        fake_session.post.return_value = fake_resp

        with patch("collector.hunter.graph._build_session", return_value=fake_session):
            result = run_hunting_query(kql="DeviceProcessEvents", token="fake")

        assert result.row_count == 1
        assert result.results[0]["DeviceName"] == "DESKTOP-001"
        assert result.results[0]["ActionType"] == "FileUploaded"


# ── persist_payload happily ingests the parsed shapes ────────────


def test_persist_payload_accepts_parsed_fixtures():
    """End-to-end shape check: parsed Graph responses → persist_payload
    without raising. This is the contract that matters most."""
    from shared.persist import persist_payload

    from collector import compliance_client

    with patch.object(compliance_client, "_paginate", return_value=SENSITIVITY_LABEL_V1_FIXTURE):
        labels = compliance_client.get_sensitivity_labels(token="fake")
    with patch.object(compliance_client, "_paginate", return_value=ALERT_V2_FIXTURE):
        alerts = compliance_client.get_dlp_alerts(token="fake")
    with patch.object(compliance_client, "_paginate", return_value=INCIDENT_FIXTURE):
        incidents = compliance_client.get_purview_incidents(
            token="fake", purview_alerts=[{"alert_id": "alert-1"}, {"alert_id": "alert-2"}]
        )

    # Mock all the upserts so we don't touch PG
    from unittest.mock import MagicMock as M

    upsert_targets = [
        "upsert_tenant",
        "upsert_sensitivity_label",
        "upsert_dlp_alert",
        "upsert_purview_incident",
        "upsert_user_content_policies",
    ]
    mocks = {n: M() for n in upsert_targets}
    with patch.multiple("shared.persist", **mocks):
        counts = persist_payload(
            tenant_id="t1",
            snapshot_date="2026-05-15",
            sensitivity_labels=labels,
            dlp_alerts=alerts,
            purview_incidents=incidents,
        )

    assert counts["sensitivity_labels"] == 2
    assert counts["dlp_alerts"] == 1
    assert counts["purview_incidents"] == 1
    # Spot-check: upsert_dlp_alert was called with the fields persist needs
    mocks["upsert_dlp_alert"].assert_called_once()
    kwargs = mocks["upsert_dlp_alert"].call_args.kwargs
    assert kwargs["alert_id"] == "alert-1"
    assert kwargs["severity"] == "high"

"""Tests for the hunter Graph API client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from collector.hunter.graph import HuntingQueryError, HuntingQueryResult, run_hunting_query


@pytest.fixture
def mock_token():
    return "test-bearer-token"


@pytest.fixture
def sample_response():
    return {
        "schema": [
            {"Name": "Timestamp", "Type": "DateTime"},
            {"Name": "AccountUpn", "Type": "String"},
            {"Name": "ActionType", "Type": "String"},
        ],
        "results": [
            {
                "Timestamp": "2026-03-24T14:22:00Z",
                "AccountUpn": "jsmith@contoso.com",
                "ActionType": "SensitivityLabelDowngraded",
            },
            {
                "Timestamp": "2026-03-24T10:15:00Z",
                "AccountUpn": "jdoe@contoso.com",
                "ActionType": "SensitivityLabelDowngraded",
            },
        ],
    }


@patch("collector.hunter.graph._build_session")
def test_successful_query(mock_build_session, mock_token, sample_response):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_build_session.return_value = mock_session

    result = run_hunting_query("DataSecurityEvents | limit 10", mock_token)
    assert isinstance(result, HuntingQueryResult)
    assert result.row_count == 2
    assert result.column_names == ["Timestamp", "AccountUpn", "ActionType"]
    assert result.results[0]["AccountUpn"] == "jsmith@contoso.com"


@patch("collector.hunter.graph._build_session")
def test_empty_results(mock_build_session, mock_token):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"schema": [], "results": []}

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_build_session.return_value = mock_session

    result = run_hunting_query("DataSecurityEvents | limit 10", mock_token)
    assert result.row_count == 0
    assert result.results == []


@patch("collector.hunter.graph._build_session")
def test_invalid_kql_400(mock_build_session, mock_token):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Syntax error near line 1"
    mock_resp.json.return_value = {"error": {"message": "Syntax error near line 1"}}

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_build_session.return_value = mock_session

    with pytest.raises(HuntingQueryError) as exc_info:
        run_hunting_query("INVALID KQL", mock_token)
    assert exc_info.value.status_code == 400
    assert "Syntax error" in exc_info.value.kql_error


@patch("collector.hunter.graph._build_session")
def test_missing_permission_403(mock_build_session, mock_token):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_build_session.return_value = mock_session

    with pytest.raises(HuntingQueryError) as exc_info:
        run_hunting_query("DataSecurityEvents | limit 10", mock_token)
    assert exc_info.value.status_code == 403
    assert "ThreatHunting.Read.All" in str(exc_info.value)


@patch("collector.hunter.graph.time.sleep")
@patch("collector.hunter.graph._build_session")
def test_rate_limit_429_retry(mock_build_session, mock_sleep, mock_token, sample_response):
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.headers = {"Retry-After": "5"}

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = sample_response

    mock_session = MagicMock()
    mock_session.post.side_effect = [mock_resp_429, mock_resp_200]
    mock_build_session.return_value = mock_session

    result = run_hunting_query("DataSecurityEvents | limit 10", mock_token)
    assert result.row_count == 2
    mock_sleep.assert_called_once_with(5)


@patch("collector.hunter.graph._build_session")
def test_unexpected_status(mock_build_session, mock_token):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_build_session.return_value = mock_session

    with pytest.raises(HuntingQueryError) as exc_info:
        run_hunting_query("DataSecurityEvents | limit 10", mock_token)
    assert exc_info.value.status_code == 500


@patch("collector.hunter.graph._build_session")
def test_network_error(mock_build_session, mock_token):
    mock_session = MagicMock()
    mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")
    mock_build_session.return_value = mock_session

    with pytest.raises(HuntingQueryError) as exc_info:
        run_hunting_query("DataSecurityEvents | limit 10", mock_token)
    assert "Network error" in str(exc_info.value)


@patch("collector.hunter.graph._build_session")
def test_custom_base_url(mock_build_session, mock_token, sample_response):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_build_session.return_value = mock_session

    run_hunting_query("DataSecurityEvents | limit 10", mock_token, base_url="https://graph.microsoft.us/v1.0")
    call_args = mock_session.post.call_args
    assert "graph.microsoft.us" in call_args[0][0]

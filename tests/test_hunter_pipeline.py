"""Tests for the hunter pipeline orchestration."""

from unittest.mock import patch

import pytest

from collector.hunter.config import HunterSettings
from collector.hunter.graph import HuntingQueryError, HuntingQueryResult
from collector.hunter.pipeline import HuntResult, hunt


@pytest.fixture
def settings():
    return HunterSettings(
        AZURE_OPENAI_ENDPOINT="https://oai.test.com/",
        AZURE_OPENAI_DEPLOYMENT="gpt-4o",
        GRAPH_BASE_URL="https://graph.microsoft.com/v1.0",
        MAX_RETRIES=2,
        MAX_RESULTS=50,
        LOOKBACK_DAYS=30,
    )


@pytest.fixture
def mock_token():
    with patch("collector.hunter.pipeline._get_graph_token", return_value="test-token") as m:
        yield m


@pytest.fixture
def sample_query_result():
    return HuntingQueryResult(
        schema=[
            {"Name": "Timestamp", "Type": "DateTime"},
            {"Name": "AccountUpn", "Type": "String"},
        ],
        results=[
            {"Timestamp": "2026-03-24T14:22:00Z", "AccountUpn": "jsmith@contoso.com"},
        ],
    )


@patch("collector.hunter.pipeline.narrate_results", return_value="Found 1 result.")
@patch("collector.hunter.pipeline.run_hunting_query")
@patch("collector.hunter.pipeline.generate_kql", return_value="DataSecurityEvents | limit 10")
def test_full_pipeline_nl(mock_gen, mock_run, mock_narrate, settings, mock_token, sample_query_result):
    mock_run.return_value = sample_query_result

    result = hunt("show label downgrades", settings)

    assert isinstance(result, HuntResult)
    assert result.question == "show label downgrades"
    assert result.kql == "DataSecurityEvents | limit 10"
    assert result.row_count == 1
    assert result.narrative == "Found 1 result."
    assert result.retries == 0
    mock_gen.assert_called_once()
    mock_narrate.assert_called_once()


@patch("collector.hunter.pipeline.run_hunting_query")
def test_kql_override_skips_generation(mock_run, settings, mock_token, sample_query_result):
    mock_run.return_value = sample_query_result

    result = hunt("Raw query", settings, kql_override="DataSecurityEvents | limit 5", skip_narrate=True)

    assert result.kql == "DataSecurityEvents | limit 5"
    assert result.row_count == 1
    assert result.narrative == ""


@patch("collector.hunter.pipeline.narrate_results")
@patch("collector.hunter.pipeline.run_hunting_query")
@patch("collector.hunter.pipeline.generate_kql")
def test_skip_narrate(mock_gen, mock_run, mock_narrate, settings, mock_token, sample_query_result):
    mock_gen.return_value = "DataSecurityEvents | limit 10"
    mock_run.return_value = sample_query_result

    result = hunt("show stuff", settings, skip_narrate=True)

    assert result.narrative == ""
    mock_narrate.assert_not_called()


@patch("collector.hunter.pipeline.narrate_results", return_value="Fixed result.")
@patch("collector.hunter.pipeline.run_hunting_query")
@patch("collector.hunter.pipeline.fix_kql", return_value="DataSecurityEvents | where 1==1 | limit 10")
@patch("collector.hunter.pipeline.generate_kql", return_value="DataSecurityEvents | BAD SYNTAX")
def test_retry_on_invalid_kql(mock_gen, mock_fix, mock_run, mock_narrate, settings, mock_token, sample_query_result):
    # First call fails with 400, second succeeds
    mock_run.side_effect = [
        HuntingQueryError("Syntax error", status_code=400, kql_error="Syntax error near 'BAD'"),
        sample_query_result,
    ]

    result = hunt("show stuff", settings)

    assert result.retries == 1
    assert result.kql == "DataSecurityEvents | where 1==1 | limit 10"
    assert result.row_count == 1
    mock_fix.assert_called_once()
    assert "Syntax error" in result.errors[0]


@patch("collector.hunter.pipeline.run_hunting_query")
@patch("collector.hunter.pipeline.fix_kql")
@patch("collector.hunter.pipeline.generate_kql", return_value="BAD KQL")
def test_retry_exhausted(mock_gen, mock_fix, mock_run, settings, mock_token):
    error = HuntingQueryError("Syntax error", status_code=400, kql_error="Syntax error")
    mock_run.side_effect = error
    mock_fix.return_value = "STILL BAD KQL"

    with pytest.raises(HuntingQueryError):
        hunt("show stuff", settings)

    assert mock_fix.call_count == settings.MAX_RETRIES


@patch("collector.hunter.pipeline.run_hunting_query")
@patch("collector.hunter.pipeline.generate_kql", return_value="DataSecurityEvents | limit 10")
def test_no_retry_on_kql_override_400(mock_gen, mock_run, settings, mock_token):
    """When using kql_override, don't retry on 400 — the user provided bad KQL."""
    mock_run.side_effect = HuntingQueryError("Syntax error", status_code=400, kql_error="Syntax error")

    with pytest.raises(HuntingQueryError):
        hunt("raw query", settings, kql_override="BAD KQL")


@patch("collector.hunter.pipeline.run_hunting_query")
@patch("collector.hunter.pipeline.generate_kql", return_value="DataSecurityEvents | limit 10")
def test_403_not_retried(mock_gen, mock_run, settings, mock_token):
    mock_run.side_effect = HuntingQueryError("Forbidden", status_code=403)

    with pytest.raises(HuntingQueryError) as exc_info:
        hunt("show stuff", settings)
    assert exc_info.value.status_code == 403

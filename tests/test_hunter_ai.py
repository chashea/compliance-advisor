"""Tests for the hunter AI module."""

from unittest.mock import MagicMock, patch

import pytest

import collector.hunter.ai as ai_mod
from collector.hunter.ai import (
    KQL_SYSTEM_PROMPT,
    _format_results_for_prompt,
    fix_kql,
    generate_kql,
    narrate_results,
)


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset module-level singletons between tests."""
    ai_mod._client = None
    yield
    ai_mod._client = None


def _mock_completion(content: str) -> MagicMock:
    """Create a mock chat completion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


@patch("collector.hunter.ai._get_client")
def test_generate_kql(mock_get_client):
    expected_kql = "DataSecurityEvents\n| where Timestamp > ago(7d)\n| limit 50"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_completion(expected_kql)
    mock_get_client.return_value = mock_client

    result = generate_kql("show label downgrades this week", "https://oai.test.com/")
    assert result == expected_kql

    # Verify system prompt contains schema
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args[1]["messages"]
    assert messages[0]["role"] == "system"
    assert "DataSecurityEvents" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "label downgrades" in messages[1]["content"]


@patch("collector.hunter.ai._get_client")
def test_generate_kql_strips_markdown_fences(mock_get_client):
    fenced_kql = "```kql\nDataSecurityEvents | limit 10\n```"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_completion(fenced_kql)
    mock_get_client.return_value = mock_client

    result = generate_kql("test question", "https://oai.test.com/")
    assert "```" not in result
    assert "DataSecurityEvents | limit 10" in result


@patch("collector.hunter.ai._get_client")
def test_fix_kql(mock_get_client):
    fixed_kql = "DataSecurityEvents\n| where Timestamp > ago(7d)\n| limit 50"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_completion(fixed_kql)
    mock_get_client.return_value = mock_client

    result = fix_kql(
        question="show downgrades",
        failed_kql="DataSecurityEvents | where Bad = 'syntax'",
        error_message="Syntax error near '='",
        endpoint="https://oai.test.com/",
    )
    assert result == fixed_kql

    # Verify conversation includes the error context
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args[1]["messages"]
    assert len(messages) == 4  # system, user question, assistant (failed), user (error)
    assert "Syntax error" in messages[3]["content"]


@patch("collector.hunter.ai._get_client")
def test_narrate_results(mock_get_client):
    narrative = "**Summary**: Found 2 label downgrades."
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_completion(narrative)
    mock_get_client.return_value = mock_client

    results = [
        {"Timestamp": "2026-03-24", "AccountUpn": "jsmith@contoso.com"},
        {"Timestamp": "2026-03-23", "AccountUpn": "jdoe@contoso.com"},
    ]

    result = narrate_results(
        question="show downgrades",
        kql="DataSecurityEvents | limit 10",
        results=results,
        total_rows=2,
        endpoint="https://oai.test.com/",
    )
    assert "Summary" in result

    # Verify user message includes results
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args[1]["messages"]
    assert "jsmith@contoso.com" in messages[1]["content"]


@patch("collector.hunter.ai._get_client")
def test_narrate_empty_results(mock_get_client):
    narrative = "**Summary**: No results found."
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_completion(narrative)
    mock_get_client.return_value = mock_client

    result = narrate_results(
        question="show downgrades",
        kql="DataSecurityEvents | limit 10",
        results=[],
        total_rows=0,
        endpoint="https://oai.test.com/",
    )
    assert "No results" in result


def test_format_results_empty():
    assert _format_results_for_prompt([]) == "(No results)"


def test_format_results_with_data():
    results = [
        {"Col1": "a", "Col2": "b"},
        {"Col1": "c", "Col2": "d"},
    ]
    output = _format_results_for_prompt(results)
    assert "Col1" in output
    assert "Col2" in output
    assert "a" in output
    assert "d" in output


def test_system_prompt_has_placeholders():
    assert "{schema}" in KQL_SYSTEM_PROMPT
    assert "{examples}" in KQL_SYSTEM_PROMPT

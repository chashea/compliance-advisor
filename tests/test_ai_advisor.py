"""Tests for the AI advisor module."""

from unittest.mock import MagicMock, patch

import pytest
from shared.ai_advisor import AdvisorAIError, _build_context, ask_advisor, generate_briefing


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset module-level singletons between tests."""
    import shared.ai_advisor as mod

    mod._client = None
    mod._assistant_id = None
    yield
    mod._client = None
    mod._assistant_id = None


@patch("shared.ai_advisor.query")
def test_build_context_with_data(mock_query):
    mock_query.side_effect = [
        # tenants
        [{"tenant_id": "t1", "display_name": "Dept A", "department": "Finance", "risk_tier": "High"}],
        # ediscovery
        [{"display_name": "Case 1", "status": "Active", "custodian_count": 3}],
        # sensitivity labels
        [{"name": "Confidential", "is_active": True}],
        # dlp alerts
        [{"title": "DLP Alert 1", "severity": "High", "status": "New"}],
        # audit count
        [{"cnt": 42}],
        # secure scores
        [
            {
                "current_score": 100,
                "max_score": 200,
                "data_current_score": 30,
                "data_max_score": 50,
                "score_date": "2026-03-01",
            }
        ],
        # improvement actions
        [
            {
                "title": "Enable MFA",
                "current_score": 0,
                "max_score": 10,
                "state": "Default",
                "implementation_cost": "Low",
            }
        ],
    ]
    ctx = _build_context()
    assert "Dept A" in ctx
    assert "Case 1" in ctx
    assert "1 active" in ctx
    assert "DLP Alert 1" in ctx
    assert "42" in ctx
    assert "100/200" in ctx
    assert "Enable MFA" in ctx
    assert mock_query.call_count == 7


@patch("shared.ai_advisor.query")
def test_build_context_empty(mock_query):
    mock_query.return_value = []
    # The last query for audit count returns [] too, so handle that
    mock_query.side_effect = [[], [], [], [], [{"cnt": 0}], [], []]
    ctx = _build_context(department="NonExistent")
    assert "Tenants (0)" in ctx


@patch("shared.ai_advisor._get_client")
@patch("shared.ai_advisor._get_or_create_assistant_id", return_value="asst_123")
@patch("shared.ai_advisor._build_context", return_value="## Test Context")
def test_ask_advisor_success(mock_context, mock_asst, mock_client):
    mock_openai = MagicMock()
    mock_client.return_value = mock_openai

    # Thread create
    mock_thread = MagicMock()
    mock_thread.id = "thread_abc"
    mock_openai.beta.threads.create.return_value = mock_thread

    # Run
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_openai.beta.threads.runs.create_and_poll.return_value = mock_run

    # Messages
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text.value = "Here is your answer."
    mock_msg = MagicMock()
    mock_msg.role = "assistant"
    mock_msg.content = [mock_text_block]
    mock_messages = MagicMock()
    mock_messages.data = [mock_msg]
    mock_openai.beta.threads.messages.list.return_value = mock_messages

    result = ask_advisor("What is the compliance posture?")
    assert result == "Here is your answer."
    mock_openai.beta.threads.delete.assert_called_once_with("thread_abc")


@patch("shared.ai_advisor._get_client")
@patch("shared.ai_advisor._get_or_create_assistant_id", return_value="asst_123")
@patch("shared.ai_advisor._build_context", return_value="## Test Context")
def test_ask_advisor_failed_run(mock_context, mock_asst, mock_client):
    mock_openai = MagicMock()
    mock_client.return_value = mock_openai

    mock_thread = MagicMock()
    mock_thread.id = "thread_abc"
    mock_openai.beta.threads.create.return_value = mock_thread

    mock_run = MagicMock()
    mock_run.status = "failed"
    mock_openai.beta.threads.runs.create_and_poll.return_value = mock_run

    with pytest.raises(AdvisorAIError, match="failed"):
        ask_advisor("test question")

    mock_openai.beta.threads.delete.assert_called_once_with("thread_abc")


@patch("shared.ai_advisor.ask_advisor")
def test_generate_briefing_delegates(mock_ask):
    mock_ask.return_value = "Executive briefing content"
    result = generate_briefing(department="Finance")
    assert result == "Executive briefing content"
    mock_ask.assert_called_once()
    call_args = mock_ask.call_args
    assert call_args.kwargs["department"] == "Finance"
    assert "executive compliance briefing" in call_args.args[0].lower()


def test_ask_route_missing_question():
    """Test that the /advisor/ask route returns 400 for missing question."""
    import json

    import azure.functions as func
    from function_app import advisor_ask

    req = func.HttpRequest(
        method="POST",
        url="/api/advisor/ask",
        body=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = advisor_ask(req)
    assert resp.status_code == 400
    body = json.loads(resp.get_body())
    assert "question" in body["error"].lower()


def test_ask_route_empty_question():
    """Test that the /advisor/ask route returns 400 for empty question."""
    import json

    import azure.functions as func
    from function_app import advisor_ask

    req = func.HttpRequest(
        method="POST",
        url="/api/advisor/ask",
        body=json.dumps({"question": "   "}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = advisor_ask(req)
    assert resp.status_code == 400

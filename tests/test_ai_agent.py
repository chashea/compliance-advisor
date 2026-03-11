from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from shared.ai_agent import AdvisorAIError, ask_advisor


def test_ask_advisor_returns_structured_answer():
    mock_client = MagicMock()
    mock_client.agents.threads.create.return_value = SimpleNamespace(id="thread-1")
    mock_client.agents.runs.create_and_process.return_value = SimpleNamespace(
        status="completed",
        model="gpt-4o",
        usage=SimpleNamespace(prompt_tokens=123, completion_tokens=45),
    )
    mock_client.agents.messages.list.return_value = [
        SimpleNamespace(
            role="assistant",
            content=[SimpleNamespace(type="text", text=SimpleNamespace(value="Executive summary"))],
        )
    ]
    settings = SimpleNamespace(AZURE_FOUNDRY_AGENT_ID="agent-1", AZURE_FOUNDRY_MODEL_DEPLOYMENT="gpt-4o")

    with (
        patch("shared.ai_agent._build_context", return_value="context"),
        patch("shared.ai_agent._get_foundry_client", return_value=mock_client),
        patch("shared.ai_agent.get_settings", return_value=settings),
    ):
        result = ask_advisor("Generate briefing")

    assert result["answer"] == "Executive summary"
    assert result["model"] == "gpt-4o"
    assert result["usage"] == {"prompt_tokens": 123, "completion_tokens": 45}


def test_ask_advisor_raises_when_context_empty():
    with patch("shared.ai_agent._build_context", return_value=""):
        with pytest.raises(AdvisorAIError) as exc:
            ask_advisor("Generate briefing")

    assert exc.value.code == "ai_no_data"
    assert exc.value.status_code == 503


def test_ask_advisor_raises_on_context_build_failure():
    with patch("shared.ai_agent._build_context", side_effect=Exception("db connection refused")):
        with pytest.raises(AdvisorAIError) as exc:
            ask_advisor("Generate briefing")

    assert exc.value.code == "ai_context_error"
    assert exc.value.status_code == 500


def test_ask_advisor_raises_on_foundry_exception():
    mock_client = MagicMock()
    mock_client.agents.threads.create.return_value = SimpleNamespace(id="thread-1")
    mock_client.agents.runs.create_and_process.side_effect = Exception("upstream timeout")
    settings = SimpleNamespace(AZURE_FOUNDRY_AGENT_ID="agent-1", AZURE_FOUNDRY_MODEL_DEPLOYMENT="gpt-4o")

    with (
        patch("shared.ai_agent._build_context", return_value="context"),
        patch("shared.ai_agent._get_foundry_client", return_value=mock_client),
        patch("shared.ai_agent.get_settings", return_value=settings),
    ):
        with pytest.raises(AdvisorAIError) as exc:
            ask_advisor("Generate briefing")

    assert exc.value.code == "ai_service_error"
    assert exc.value.status_code == 502


def test_ask_advisor_raises_on_empty_ai_answer():
    mock_client = MagicMock()
    mock_client.agents.threads.create.return_value = SimpleNamespace(id="thread-1")
    mock_client.agents.runs.create_and_process.return_value = SimpleNamespace(
        status="completed",
        model="gpt-4o",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    mock_client.agents.messages.list.return_value = [SimpleNamespace(role="assistant", content=None)]
    settings = SimpleNamespace(AZURE_FOUNDRY_AGENT_ID="agent-1", AZURE_FOUNDRY_MODEL_DEPLOYMENT="gpt-4o")

    with (
        patch("shared.ai_agent._build_context", return_value="context"),
        patch("shared.ai_agent._get_foundry_client", return_value=mock_client),
        patch("shared.ai_agent.get_settings", return_value=settings),
    ):
        with pytest.raises(AdvisorAIError) as exc:
            ask_advisor("Generate briefing")

    assert exc.value.code == "ai_invalid_response"

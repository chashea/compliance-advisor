from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from shared.ai_agent import AdvisorAIError, ask_advisor


def test_ask_advisor_returns_structured_answer():
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Executive summary"))],
        model="gpt-4o",
        usage=SimpleNamespace(prompt_tokens=123, completion_tokens=45),
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = response
    settings = SimpleNamespace(AZURE_OPENAI_DEPLOYMENT="gpt-4o")

    with (
        patch("shared.ai_agent._build_context", return_value="context"),
        patch("shared.ai_agent._get_openai_client", return_value=mock_client),
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


def test_ask_advisor_raises_on_openai_exception():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("upstream timeout")
    settings = SimpleNamespace(AZURE_OPENAI_DEPLOYMENT="gpt-4o")

    with (
        patch("shared.ai_agent._build_context", return_value="context"),
        patch("shared.ai_agent._get_openai_client", return_value=mock_client),
        patch("shared.ai_agent.get_settings", return_value=settings),
    ):
        with pytest.raises(AdvisorAIError) as exc:
            ask_advisor("Generate briefing")

    assert exc.value.code == "ai_service_error"
    assert exc.value.status_code == 502


def test_ask_advisor_raises_on_empty_ai_answer():
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
        model="gpt-4o",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = response
    settings = SimpleNamespace(AZURE_OPENAI_DEPLOYMENT="gpt-4o")

    with (
        patch("shared.ai_agent._build_context", return_value="context"),
        patch("shared.ai_agent._get_openai_client", return_value=mock_client),
        patch("shared.ai_agent.get_settings", return_value=settings),
    ):
        with pytest.raises(AdvisorAIError) as exc:
            ask_advisor("Generate briefing")

    assert exc.value.code == "ai_invalid_response"

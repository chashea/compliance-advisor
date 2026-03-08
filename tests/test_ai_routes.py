import json
from unittest.mock import MagicMock, patch

from function_app import advisor_ask, advisor_briefing
from shared.ai_agent import AdvisorAIError


def _mock_request(body: dict):
    req = MagicMock()
    req.get_json.return_value = body
    return req


@patch("function_app.ask_advisor")
def test_advisor_briefing_returns_structured_ai_error(mock_ask):
    mock_ask.side_effect = AdvisorAIError(
        "ai_service_error",
        "AI service is unavailable right now. Please try again shortly.",
        status_code=502,
    )
    resp = advisor_briefing(_mock_request({}))
    payload = json.loads(resp.get_body().decode("utf-8"))

    assert resp.status_code == 502
    assert payload["code"] == "ai_service_error"
    assert "AI service is unavailable" in payload["error"]


@patch("function_app.ask_advisor")
def test_advisor_ask_returns_structured_ai_error(mock_ask):
    mock_ask.side_effect = AdvisorAIError(
        "ai_no_data",
        "No compliance data is available yet. Run data collection and try again.",
        status_code=503,
    )
    resp = advisor_ask(_mock_request({"question": "What changed?"}))
    payload = json.loads(resp.get_body().decode("utf-8"))

    assert resp.status_code == 503
    assert payload["code"] == "ai_no_data"
    assert "No compliance data is available yet" in payload["error"]

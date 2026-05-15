"""AI-advisor routes — separate from dashboard because they need rate
limiting and have a custom error mapping (``AdvisorAIError`` → HTTP 502)."""

from __future__ import annotations

import logging

import azure.functions as func
from shared.ai_advisor import AdvisorAIError, ask_advisor, generate_briefing
from shared.auth import get_auth_error_response, require_auth
from shared.rate_limit import get_rate_limiter

from routes._decorator import get_body, json_response

log = logging.getLogger(__name__)

bp = func.Blueprint()


def _client_ip(req: func.HttpRequest) -> str:
    forwarded = req.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return "unknown"


@bp.function_name("advisor_briefing")
@bp.route(route="advisor/briefing", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_briefing(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        if get_rate_limiter().is_rate_limited(_client_ip(req)):
            return json_response({"error": "Rate limit exceeded. Max 10 requests per minute."}, 429)
        body = get_body(req)
        briefing = generate_briefing(department=body.get("department"), tenant_id=body.get("tenant_id"))
        return json_response({"briefing": briefing})
    except AdvisorAIError as e:
        log.exception("advisor/briefing AI error: %s", e)
        return json_response({"error": str(e)}, 502)
    except Exception as e:
        log.exception("advisor/briefing error: %s", e)
        return json_response({"error": str(e)}, 500)


@bp.function_name("advisor_ask")
@bp.route(route="advisor/ask", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_ask(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        if get_rate_limiter().is_rate_limited(_client_ip(req)):
            return json_response({"error": "Rate limit exceeded. Max 10 requests per minute."}, 429)
        body = get_body(req)
        question = body.get("question", "").strip()
        if not question:
            return json_response({"error": "Missing required field: question"}, 400)
        answer = ask_advisor(question=question, department=body.get("department"), tenant_id=body.get("tenant_id"))
        return json_response({"answer": answer})
    except AdvisorAIError as e:
        log.exception("advisor/ask AI error: %s", e)
        return json_response({"error": str(e)}, 502)
    except Exception as e:
        log.exception("advisor/ask error: %s", e)
        return json_response({"error": str(e)}, 500)

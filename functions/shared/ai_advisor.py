"""
AI Advisor — Azure OpenAI Assistants API integration.

Provides executive briefings and Q&A using compliance data context
from PostgreSQL, powered by Azure OpenAI with managed identity auth.
"""

import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from shared.config import get_settings
from shared.db import query

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior government CISO compliance advisor. You analyze Microsoft 365 compliance
workload data across multiple agencies and provide executive-level insights, risk assessments,
and actionable recommendations.

Guidelines:
- Be concise and direct. Use bullet points for clarity.
- Highlight critical risks first, then opportunities for improvement.
- Reference specific data points (counts, scores, trends) from the provided context.
- Frame recommendations in terms of compliance posture impact.
- Use professional government/public-sector terminology.
- Never fabricate data — only reference what is provided in the context."""

_client: AzureOpenAI | None = None
_assistant_id: str | None = None


class AdvisorAIError(Exception):
    """Raised when the AI advisor encounters an error."""


def _get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.AZURE_OPENAI_ENDPOINT:
            raise AdvisorAIError("AZURE_OPENAI_ENDPOINT is not configured")
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        _client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            azure_ad_token_provider=token_provider,
            api_version="2024-05-01-preview",
        )
    return _client


def _get_or_create_assistant_id() -> str:
    global _assistant_id
    if _assistant_id is not None:
        return _assistant_id

    settings = get_settings()
    if settings.AZURE_OPENAI_ASSISTANT_ID:
        _assistant_id = settings.AZURE_OPENAI_ASSISTANT_ID
        return _assistant_id

    client = _get_client()
    assistant = client.beta.assistants.create(
        name="Compliance Advisor",
        instructions=SYSTEM_PROMPT,
        model=settings.AZURE_OPENAI_MODEL,
    )
    _assistant_id = assistant.id
    log.info("Auto-created assistant: %s — set AZURE_OPENAI_ASSISTANT_ID to persist", _assistant_id)
    return _assistant_id


def _build_context(department: str | None = None, tenant_id: str | None = None) -> str:
    dept_filter = ""
    tenant_filter = ""
    dept_params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        dept_params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        dept_params["tenant_id"] = tenant_id

    sections: list[str] = []

    # Tenants
    tenants = query(
        f"SELECT tenant_id, display_name, department, risk_tier FROM tenants t WHERE 1=1 {dept_filter} {tenant_filter}",
        dept_params,
    )
    sections.append(f"## Tenants ({len(tenants)})")
    for t in tenants:
        sections.append(f"- {t['display_name']} ({t['department']}) — risk: {t['risk_tier']}")

    # Sensitivity labels
    labels = query(
        f"""SELECT sl.name, sl.is_active
            FROM sensitivity_labels sl
            JOIN tenants t ON sl.tenant_id = t.tenant_id
            WHERE sl.snapshot_date = (SELECT MAX(snapshot_date) FROM sensitivity_labels WHERE tenant_id = sl.tenant_id)
            {dept_filter} {tenant_filter}""",
        dept_params,
    )
    active = sum(1 for lbl in labels if lbl["is_active"])
    sections.append(f"\n## Sensitivity Labels ({len(labels)} total, {active} active)")

    # DLP alerts
    dlp = query(
        f"""SELECT da.title, da.severity, da.status
            FROM dlp_alerts da
            JOIN tenants t ON da.tenant_id = t.tenant_id
            WHERE da.snapshot_date = (SELECT MAX(snapshot_date) FROM dlp_alerts WHERE tenant_id = da.tenant_id)
            {dept_filter} {tenant_filter}""",
        dept_params,
    )
    sections.append(f"\n## DLP Alerts ({len(dlp)})")
    for a in dlp[:20]:
        sections.append(f"- [{a['severity']}] {a['title']} — {a['status']}")
    if len(dlp) > 20:
        sections.append(f"- ... and {len(dlp) - 20} more")

    # Audit records
    audit_count = query(
        f"""SELECT COUNT(*)::int AS cnt
            FROM audit_records ar
            JOIN tenants t ON ar.tenant_id = t.tenant_id
            WHERE ar.snapshot_date = (SELECT MAX(snapshot_date) FROM audit_records WHERE tenant_id = ar.tenant_id)
            {dept_filter} {tenant_filter}""",
        dept_params,
    )
    sections.append(f"\n## Audit Records: {audit_count[0]['cnt'] if audit_count else 0}")

    # Secure scores
    scores = query(
        f"""SELECT ss.current_score, ss.max_score, ss.data_current_score, ss.data_max_score, ss.score_date
            FROM secure_scores ss
            JOIN tenants t ON ss.tenant_id = t.tenant_id
            WHERE ss.snapshot_date = (SELECT MAX(snapshot_date) FROM secure_scores WHERE tenant_id = ss.tenant_id)
            {dept_filter} {tenant_filter}
            ORDER BY ss.score_date DESC LIMIT 5""",
        dept_params,
    )
    sections.append(f"\n## Secure Scores ({len(scores)} entries)")
    for s in scores:
        pct = f"{(s['current_score'] / s['max_score'] * 100):.0f}%" if s["max_score"] else "N/A"
        data_pct = f"{(s['data_current_score'] / s['data_max_score'] * 100):.0f}%" if s["data_max_score"] else "N/A"
        sections.append(
            f"- Overall: {s['current_score']}/{s['max_score']} ({pct}) | "
            f"Data: {s['data_current_score']}/{s['data_max_score']} ({data_pct}) — {s['score_date']}"
        )

    # Improvement actions
    actions = query(
        f"""SELECT ia.title, ia.current_score, ia.max_score, ia.state, ia.implementation_cost
            FROM improvement_actions ia
            JOIN tenants t ON ia.tenant_id = t.tenant_id
            WHERE ia.snapshot_date = (SELECT MAX(snapshot_date) FROM improvement_actions WHERE tenant_id = ia.tenant_id)
            AND ia.deprecated = false
            {dept_filter}
            ORDER BY (ia.max_score - ia.current_score) DESC
            LIMIT 15""",
        dept_params,
    )
    sections.append("\n## Top Improvement Actions (by gap)")
    for a in actions:
        gap = a["max_score"] - a["current_score"]
        cost = a["implementation_cost"]
        state = a["state"]
        sections.append(f"- {a['title']}: {a['current_score']}/{a['max_score']} (gap: {gap}) — {state}, cost: {cost}")

    # Threat hunting findings
    hunt_findings = query(
        f"""SELECT hr.finding_type, hr.severity, hr.account_upn, hr.action_type, hr.detected_at::text
            FROM hunt_results hr
            JOIN tenants t ON hr.tenant_id = t.tenant_id
            WHERE hr.snapshot_date >= CURRENT_DATE - 7
            {dept_filter} {tenant_filter}
            ORDER BY hr.detected_at DESC NULLS LAST
            LIMIT 10""",
        dept_params,
    )
    if hunt_findings:
        sections.append(f"\n## Recent Threat Hunt Findings ({len(hunt_findings)})")
        for hf in hunt_findings:
            sections.append(
                f"- [{hf['severity']}] {hf['finding_type']}: {hf['account_upn'] or 'N/A'} "
                f"— {hf['action_type'] or ''} ({hf['detected_at'] or 'unknown'})"
            )

    return "\n".join(sections)


def ask_advisor(question: str, department: str | None = None, tenant_id: str | None = None) -> str:
    client = _get_client()
    assistant_id = _get_or_create_assistant_id()
    context = _build_context(department, tenant_id)

    thread = client.beta.threads.create()
    try:
        user_content = f"## Current Compliance Data\n\n{context}\n\n---\n\n## Question\n\n{question}"
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_content,
        )

        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant_id,
        )

        if run.status != "completed":
            raise AdvisorAIError(f"Assistant run failed with status: {run.status}")

        messages = client.beta.threads.messages.list(thread_id=thread.id, order="desc", limit=1)
        for msg in messages.data:
            if msg.role == "assistant":
                return "".join(block.text.value for block in msg.content if block.type == "text")

        raise AdvisorAIError("No assistant response found")
    finally:
        try:
            client.beta.threads.delete(thread.id)
        except Exception:
            log.warning("Failed to delete thread %s", thread.id)


def generate_briefing(department: str | None = None, tenant_id: str | None = None) -> str:
    return ask_advisor(
        "Provide an executive compliance briefing covering:\n"
        "1. Overall compliance posture and Secure Score trends\n"
        "2. Critical risks requiring immediate attention\n"
        "3. Top improvement opportunities (highest score gap)\n"
        "4. DLP alert status\n"
        "5. Recommended next steps",
        department=department,
        tenant_id=tenant_id,
    )

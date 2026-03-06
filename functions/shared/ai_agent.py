"""
AI Compliance Advisor Agent — Azure OpenAI (GPT-4o).

Reads compliance metadata from PostgreSQL and uses Azure OpenAI to generate
executive summaries and answer compliance questions.

Reads only metadata (scores, percentages, counts) — never PII or content.
"""

import json
import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from shared.config import get_settings
from shared.db import query

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an AI compliance advisor for a government CISO overseeing Microsoft
Purview Compliance Manager across multiple agencies in M365 GCC.

You analyze aggregated metadata (never PII or content) to:
1. Identify agencies with the lowest compliance scores and explain why they need attention
2. Highlight trends in compliance scores across agencies and departments
3. Recommend specific, actionable improvement actions prioritized by point impact
4. Generate executive summaries suitable for legislative/cabinet briefings

Data available (injected as context):
- Agency posture snapshots (compliance scores per tenant per day)
- Compliance Manager assessment summaries (per regulation per agency)
- Improvement actions with point values, implementation status, and ownership

Guidelines:
- Lead with the cross-agency compliance posture (average score and range)
- Call out any agency with compliance score below 50% as requiring immediate attention
- Reference specific numbers from the data — never fabricate metrics
- Keep executive summaries under 400 words
- Use bullet points for clarity
- Classify recommendations as Quick Win (< 1 week), Short-Term (1-4 weeks), Strategic (1-3 months)
- All scores referenced are native from Microsoft Purview Compliance Manager
- Scoring: Preventative mandatory = 27 pts, Preventative discretionary = 9 pts,
  Detective mandatory = 3 pts, Detective discretionary = 1 pt,
  Corrective mandatory = 3 pts, Corrective discretionary = 1 pt
"""


def _get_openai_client() -> AzureOpenAI:
    settings = get_settings()
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )


def _build_context(department: str | None = None) -> str:
    """Build the data context string from PostgreSQL."""
    parts = []

    # Latest snapshots per tenant
    dept_filter = ""
    params: tuple = ()
    if department:
        dept_filter = "WHERE t.department = %s"
        params = (department,)

    snapshots = query(
        f"""
        SELECT DISTINCT ON (ps.tenant_id)
            ps.tenant_id, t.display_name, t.department, t.risk_tier,
            ps.compliance_score, ps.max_score, ps.compliance_pct, ps.snapshot_date
        FROM posture_snapshots ps
        JOIN tenants t ON t.tenant_id = ps.tenant_id
        {dept_filter}
        ORDER BY ps.tenant_id, ps.snapshot_date DESC
        """,
        params,
    )

    if snapshots:
        scores = [s["compliance_pct"] for s in snapshots if s["compliance_pct"] is not None]
        if scores:
            parts.append(
                f"## Cross-Agency Summary\n"
                f"- Total agencies reporting: {len(snapshots)}\n"
                f"- Average compliance score: {sum(scores) / len(scores):.1f}%\n"
                f"- Range: {min(scores):.1f}% to {max(scores):.1f}%"
            )

    parts.append(
        f"## Agency Snapshots (sorted by score, lowest first)\n"
        f"{json.dumps(snapshots[:20], indent=2, default=str)}"
    )

    # Assessment summaries
    assessments = query(
        f"""
        SELECT a.assessment_name, a.regulation, t.display_name, t.department,
               a.compliance_score, a.pass_rate, a.passed_controls,
               a.failed_controls, a.total_controls
        FROM assessments a
        JOIN tenants t ON t.tenant_id = a.tenant_id
        {dept_filter}
        WHERE a.snapshot_date = (SELECT MAX(snapshot_date) FROM assessments)
        ORDER BY a.compliance_score ASC
        LIMIT 30
        """,
        params,
    )
    if assessments:
        parts.append(
            f"## Compliance Assessments\n{json.dumps(assessments, indent=2, default=str)}"
        )

    # Top gaps (unimplemented actions with highest point values)
    gaps = query(
        f"""
        SELECT ia.control_name, ia.control_family, ia.regulation,
               ia.implementation_status, ia.point_value, ia.owner, ia.service,
               t.display_name
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        {dept_filter}
        WHERE ia.implementation_status != 'implemented'
          AND ia.snapshot_date = (SELECT MAX(snapshot_date) FROM improvement_actions)
        ORDER BY ia.point_value DESC
        LIMIT 20
        """,
        params,
    )
    if gaps:
        parts.append(f"## Top Improvement Gaps\n{json.dumps(gaps, indent=2, default=str)}")

    return "\n\n".join(parts)


def ask_advisor(question: str, department: str | None = None) -> dict:
    """Query the AI compliance advisor.

    Args:
        question: The user's question or request.
        department: Optional department to scope the context.

    Returns:
        {"answer": str, "model": str, "usage": {"prompt_tokens": int, "completion_tokens": int}}
    """
    client = _get_openai_client()
    settings = get_settings()
    context = _build_context(department)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"DATA CONTEXT:\n{context}\n\nQUESTION: {question}"},
    ]

    response = client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=messages,
        temperature=0.2,
        max_tokens=2048,
    )

    return {
        "answer": response.choices[0].message.content,
        "model": response.model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        },
    }

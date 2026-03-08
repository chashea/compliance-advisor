"""
AI Compliance Advisor Agent — Azure OpenAI (GPT-4o).

Reads compliance workload metadata from PostgreSQL and uses Azure OpenAI to
generate executive summaries and answer compliance questions.

Reads only metadata (counts, statuses, labels) — never PII or content.
"""

import json
import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from shared.config import get_settings
from shared.db import query

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an AI compliance advisor for a government CISO overseeing Microsoft 365
compliance workloads across multiple agencies in M365 GCC.

You analyze aggregated metadata (never PII or content) to:
1. Summarize compliance posture across 6 workloads: eDiscovery, Information
   Protection, Records Management, Audit Log, DLP, and Data Security & Governance
2. Identify agencies with gaps in label coverage, open eDiscovery cases, or
   unresolved DLP alerts and explain why they need attention
3. Highlight trends in compliance activity across agencies and departments
4. Recommend specific, actionable steps prioritized by risk impact
5. Generate executive summaries suitable for legislative/cabinet briefings

Data available (injected as context):
- eDiscovery case summaries (case counts, statuses)
- Sensitivity and retention label inventories
- Audit log activity summaries (operation counts by service)
- DLP alert summaries (severity, policy, status)
- Data governance protection scope configurations

Guidelines:
- Lead with a cross-agency compliance overview
- Call out any agency with open high-severity DLP alerts as requiring immediate attention
- Call out agencies with no sensitivity labels configured as a coverage gap
- Reference specific numbers from the data — never fabricate metrics
- Keep executive summaries under 400 words
- Use bullet points for clarity
- Classify recommendations as Quick Win (< 1 week), Short-Term (1-4 weeks), Strategic (1-3 months)
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

    dept_filter = ""
    params: tuple = ()
    if department:
        dept_filter = "WHERE t.department = %s"
        params = (department,)

    and_dept = "AND t.department = %s" if department else ""

    # Tenant list
    tenants = query(
        f"""
        SELECT t.tenant_id, t.display_name, t.department
        FROM tenants t {dept_filter}
        ORDER BY t.display_name
        """,
        params,
    )
    if tenants:
        parts.append(f"## Tenants ({len(tenants)} reporting)\n{json.dumps(tenants[:20], indent=2, default=str)}")

    # eDiscovery summary
    ediscovery = query(
        f"""
        SELECT ec.status, COUNT(*)::int AS total, t.display_name
        FROM ediscovery_cases ec
        JOIN tenants t ON t.tenant_id = ec.tenant_id
        WHERE ec.snapshot_date = (SELECT MAX(snapshot_date) FROM ediscovery_cases)
          {and_dept}
        GROUP BY ec.status, t.display_name
        ORDER BY total DESC
        """,
        params,
    )
    if ediscovery:
        parts.append(f"## eDiscovery Cases\n{json.dumps(ediscovery, indent=2, default=str)}")

    # Sensitivity label counts per tenant
    sensitivity = query(
        f"""
        SELECT t.display_name, COUNT(*)::int AS label_count,
               COUNT(*) FILTER (WHERE sl.is_active)::int AS active_labels
        FROM sensitivity_labels sl
        JOIN tenants t ON t.tenant_id = sl.tenant_id
        WHERE sl.snapshot_date = (SELECT MAX(snapshot_date) FROM sensitivity_labels)
          {and_dept}
        GROUP BY t.display_name
        ORDER BY label_count
        """,
        params,
    )
    if sensitivity:
        parts.append(f"## Sensitivity Labels per Tenant\n{json.dumps(sensitivity, indent=2, default=str)}")

    # DLP alert summary
    dlp = query(
        f"""
        SELECT da.severity, COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE da.status != 'resolved')::int AS active
        FROM dlp_alerts da
        JOIN tenants t ON t.tenant_id = da.tenant_id
        WHERE da.snapshot_date = (SELECT MAX(snapshot_date) FROM dlp_alerts)
          {and_dept}
        GROUP BY da.severity
        ORDER BY
            CASE da.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END
        """,
        params,
    )
    if dlp:
        parts.append(f"## DLP Alert Summary\n{json.dumps(dlp, indent=2, default=str)}")

    # Audit activity summary
    audit = query(
        f"""
        SELECT ar.service, COUNT(*)::int AS total
        FROM audit_records ar
        JOIN tenants t ON t.tenant_id = ar.tenant_id
        WHERE ar.snapshot_date = (SELECT MAX(snapshot_date) FROM audit_records)
          {and_dept}
        GROUP BY ar.service
        ORDER BY total DESC
        LIMIT 10
        """,
        params,
    )
    if audit:
        parts.append(f"## Audit Activity by Service\n{json.dumps(audit, indent=2, default=str)}")

    # Retention label summary
    retention = query(
        f"""
        SELECT t.display_name, COUNT(*)::int AS label_count,
               COUNT(*) FILTER (WHERE rl.is_in_use)::int AS in_use
        FROM retention_labels rl
        JOIN tenants t ON t.tenant_id = rl.tenant_id
        WHERE rl.snapshot_date = (SELECT MAX(snapshot_date) FROM retention_labels)
          {and_dept}
        GROUP BY t.display_name
        ORDER BY label_count
        """,
        params,
    )
    if retention:
        parts.append(f"## Retention Labels per Tenant\n{json.dumps(retention, indent=2, default=str)}")

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

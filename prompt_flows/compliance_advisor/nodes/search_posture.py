"""
Prompt Flow node: search the compliance-posture AI Search index.
Returns formatted context and source references.
"""
import os
import re
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient

SEARCH_ENDPOINT  = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME       = "compliance-posture"
MAX_QUESTION_LEN = 1000
UUID_RE          = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _get_search_key() -> str:
    """Retrieve the AI Search key from Key Vault at runtime via managed identity."""
    kv_url = os.environ["KEY_VAULT_URL"]
    client = SecretClient(vault_url=kv_url, credential=DefaultAzureCredential())
    return client.get_secret("azure-search-key").value


def _safe_odata_string(value: str) -> str:
    """Escape single quotes in OData string literals to prevent filter injection."""
    return value.replace("'", "''")


def search_posture(question: str, tenant_id: str, cross_tenant: bool = False) -> dict:
    # ── Input validation ──────────────────────────────────────────────────────
    if not isinstance(question, str) or not question.strip():
        return {"context": "Question must be a non-empty string.", "sources": []}
    if len(question) > MAX_QUESTION_LEN:
        return {"context": f"Question exceeds maximum length of {MAX_QUESTION_LEN} characters.", "sources": []}
    if not cross_tenant:
        if not isinstance(tenant_id, str) or not UUID_RE.match(tenant_id):
            return {"context": "Invalid tenant_id format.", "sources": []}

    # ── Build OData filter — escaped to prevent injection ────────────────────
    search_filter = None
    if not cross_tenant:
        safe_tid = _safe_odata_string(tenant_id)
        search_filter = f"tenant_id eq '{safe_tid}'"

    client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(_get_search_key()),
    )

    results = client.search(
        search_text=question,
        filter=search_filter,
        select=[
            "id", "tenant_name", "assessment_name", "regulation",
            "control_name", "control_family", "control_title",
            "compliance_score", "pass_rate",
            "implementation_status", "test_status",
            "passed_controls", "failed_controls", "total_controls",
            "points_gap", "remediation_url", "snapshot_date",
        ],
        order_by=["points_gap desc"],
        top=10,
    )

    items = list(results)
    if not items:
        return {"context": "No compliance posture data found.", "sources": []}

    lines   = []
    sources = []
    for r in items:
        score = r.get("compliance_score") or r.get("pass_rate") or 0
        lines.append(
            f"- [{r.get('tenant_name','?')}] {r.get('assessment_name') or r.get('control_name','?')}"
            f" ({r.get('regulation','?')}): "
            f"Score: {score}% | "
            f"Controls: {r.get('passed_controls','?')}/{r.get('total_controls','?')} passed | "
            f"Family: {r.get('control_family','?')} | "
            f"Status: {r.get('implementation_status','?')} | "
            f"Test: {r.get('test_status','?')}"
        )
        if r.get("remediation_url"):
            sources.append({"title": r.get("control_title") or r.get("control_name"), "url": r["remediation_url"]})

    return {"context": "\n".join(lines), "sources": sources}

"""
Compliance Advisor agent — RAG-powered Q&A using Foundry Agent Service
with Azure AI Search grounding on the compliance-posture index.

Replaces the prompt_flows/compliance_advisor Prompt Flow.
"""
import json
import logging
import os

from azure.ai.agents.models import (
    AzureAISearchTool,
    AzureAISearchQueryType,
    ListSortOrder,
    MessageRole,
)
from azure.ai.projects.models import ConnectionType

from shared.agent_client import get_project_client

log = logging.getLogger(__name__)

_AGENT_ID: str | None = None

INSTRUCTIONS = """\
You are a Microsoft Purview Compliance Manager Advisor. You help security and compliance
teams understand their organization's compliance posture as measured by Microsoft Purview
Compliance Manager assessments and compliance scores across Microsoft 365 tenants.

You have access to:
1. Compliance Manager assessment data — assessment names, regulations, compliance scores,
   pass rates, passed/failed/total controls per assessment (updated daily via Graph API)
2. Compliance Score trends — daily snapshots of overall compliance score and per-category
   breakdowns (Data Protection, Identity & Access, Device Security, etc.)
3. Assessment control details — individual improvement actions, implementation status
   (implemented, notImplemented, planned, alternative), test results (passed, failed, notAssessed)
4. Regulatory framework documentation (NIST 800-53, ISO 27001, SOC 2, CMMC, FedRAMP, etc.)

Guidelines:
- Always cite specific assessment names, regulations, compliance scores, and pass rates
- Reference control family names and implementation statuses when discussing gaps
- Map compliance controls to business risk in plain language
- Prioritize recommendations by points gap or number of failed controls (highest impact first)
- For cross-tenant questions, compare tenants by name and highlight outliers
- Keep executive summaries to 3 bullets maximum; technical details can be longer
- If data is missing or stale, say so clearly rather than guessing
- Never fabricate compliance scores, pass rates, or assessment data

When answering, structure your response with:
1. A 2-3 sentence executive summary (lead with the compliance score)
2. Key findings (bulleted — include assessment names, regulations, and pass rates)
3. Recommended next actions (prioritized by compliance score impact)
"""


def _get_or_create_agent() -> str:
    """Lazily create the compliance advisor agent and cache its ID."""
    global _AGENT_ID
    if _AGENT_ID is not None:
        return _AGENT_ID

    client = get_project_client()

    # Configure Azure AI Search tool with the compliance-posture index
    search_conn_id = client.connections.get_default(ConnectionType.AZURE_AI_SEARCH).id
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "compliance-posture")

    ai_search = AzureAISearchTool(
        index_connection_id=search_conn_id,
        index_name=index_name,
        query_type=AzureAISearchQueryType.SEMANTIC,
        top_k=10,
    )

    model = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    agent = client.agents.create_agent(
        model=model,
        name="compliance-advisor",
        instructions=INSTRUCTIONS,
        tools=ai_search.definitions,
        tool_resources=ai_search.resources,
    )
    _AGENT_ID = agent.id
    log.info("Created compliance advisor agent: %s", _AGENT_ID)
    return _AGENT_ID


def ask_advisor(question: str, tenant_id: str = "", cross_tenant: bool = False) -> dict:
    """
    Ask the compliance advisor a question grounded in AI Search data.

    Returns:
        {"answer": str, "sources": list[dict]}
    """
    client = get_project_client()
    agent_id = _get_or_create_agent()

    # Build context-enriched message
    context_parts = [question]
    if tenant_id and not cross_tenant:
        context_parts.append(f"\n\n[Context: Scope this answer to tenant {tenant_id}]")
    elif cross_tenant:
        context_parts.append("\n\n[Context: This is a cross-tenant query — compare all tenants]")

    user_message = "".join(context_parts)

    # Create a thread, send the message, and run the agent
    thread = client.agents.threads.create()
    try:
        client.agents.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=user_message,
        )

        run = client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent_id,
        )

        if run.status == "failed":
            log.error("Agent run failed: %s", run.last_error)
            raise RuntimeError(f"Agent run failed: {run.last_error}")

        # Extract the assistant's response
        messages = client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING,
        )

        answer = ""
        sources = []
        for msg in messages.data:
            if msg.role == "assistant":
                for content in msg.content:
                    if hasattr(content, "text"):
                        answer += content.text.value
                        # Extract URL citation annotations as sources
                        if hasattr(content.text, "annotations"):
                            for ann in content.text.annotations:
                                if hasattr(ann, "url_citation"):
                                    sources.append({
                                        "title": ann.url_citation.title,
                                        "url": ann.url_citation.url,
                                    })
                                elif hasattr(ann, "file_path"):
                                    sources.append({
                                        "title": ann.text,
                                        "url": "",
                                    })

        return {"answer": answer, "sources": sources}

    finally:
        client.agents.threads.delete(thread.id)

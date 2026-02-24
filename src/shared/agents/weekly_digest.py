"""
Weekly Digest agent — generates enterprise compliance digest and posts to Teams
using Foundry Agent Service with custom function tools.

Replaces the prompt_flows/weekly_digest Prompt Flow.
"""
import json
import logging
import os

import requests as http_requests
from azure.ai.agents.models import (
    FunctionTool,
    ListSortOrder,
    MessageRole,
    RequiredFunctionToolCall,
    SubmitToolOutputsAction,
    ToolOutput,
)
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from shared.agent_client import get_project_client
from shared.sql_client import get_connection, set_admin_context

log = logging.getLogger(__name__)

_AGENT_ID: str | None = None

INSTRUCTIONS = """\
You are a Microsoft Purview Compliance Manager Advisor generating a weekly digest
report for a multi-tenant enterprise. Write for a mixed audience of security leaders,
department heads, and compliance managers. Be concise and action-oriented.
Focus on Compliance Manager assessments and compliance scores.
Flag any declining trends prominently.

To generate the digest:
1. Call the data retrieval tools to gather the latest compliance data
2. Generate a weekly digest with:
   - A 2-sentence executive summary (lead with the Compliance Score number)
   - Which tenants improved or declined this week, with percentage changes
   - Department/agency performance comparison (if data available)
   - Assessment coverage — which regulations are well-covered vs. at risk
   - The top 3 recommended actions to take this week (with business justification)
   - A closing sentence on overall compliance posture trend direction
3. Call the post_to_teams tool with the generated digest text

Keep the total length under 450 words. Use plain language — no technical jargon.
This report will be shared with organizational leadership.
Do not fabricate data — only reference numbers from tool call results.
"""

TOOL_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_compliance_scores",
            "description": "Get the latest compliance scores for all monitored tenants.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_changes",
            "description": "Get week-over-week compliance score changes for all tenants.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_department_rollup",
            "description": "Get aggregated compliance scores by department/agency.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_gaps",
            "description": "Get the top 10 assessment control gaps sorted by total points gap.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_to_teams",
            "description": "Post the generated digest summary to the Microsoft Teams compliance channel via webhook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "The weekly digest text to post to Teams.",
                    }
                },
                "required": ["summary"],
            },
        },
    },
]


# ── Tool handler functions ───────────────────────────────────────────────────

def _query_rows(sql: str) -> list[dict]:
    """Execute a SQL query with admin context and return rows as dicts."""
    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()
        cursor.execute(sql)
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]
    finally:
        conn.close()


def _post_to_teams(summary: str) -> dict:
    """Post digest to Teams via Incoming Webhook from Key Vault."""
    kv_url = os.environ["KEY_VAULT_URL"]
    kv_client = SecretClient(vault_url=kv_url, credential=DefaultAzureCredential())
    webhook_url = kv_client.get_secret("teams-webhook-url").value

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Weekly Compliance Digest",
                            "weight": "Bolder",
                            "size": "Medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": summary,
                            "wrap": True,
                        },
                    ],
                },
            }
        ],
    }

    resp = http_requests.post(
        webhook_url,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=15,
    )
    return {"success": resp.status_code == 200, "status_code": resp.status_code}


def _handle_tool_call(name: str, arguments: dict) -> str:
    """Dispatch a tool call to the appropriate handler and return JSON."""
    if name == "get_compliance_scores":
        rows = _query_rows(
            "SELECT * FROM v_latest_compliance_scores ORDER BY compliance_pct ASC"
        )
        return json.dumps(rows, default=str)

    elif name == "get_weekly_changes":
        rows = _query_rows(
            "SELECT * FROM v_compliance_weekly_change ORDER BY wow_change ASC"
        )
        return json.dumps(rows, default=str)

    elif name == "get_department_rollup":
        rows = _query_rows(
            "SELECT * FROM v_compliance_department_rollup ORDER BY avg_compliance_pct ASC"
        )
        return json.dumps(rows, default=str)

    elif name == "get_top_gaps":
        rows = _query_rows(
            "SELECT TOP 10 * FROM v_assessment_gaps ORDER BY total_gap DESC"
        )
        return json.dumps(rows, default=str)

    elif name == "post_to_teams":
        result = _post_to_teams(arguments["summary"])
        return json.dumps(result)

    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


# ── Agent lifecycle ──────────────────────────────────────────────────────────

def _get_or_create_agent() -> str:
    """Lazily create the weekly digest agent and cache its ID."""
    global _AGENT_ID
    if _AGENT_ID is not None:
        return _AGENT_ID

    client = get_project_client()
    model = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    functions = FunctionTool(functions=TOOL_FUNCTIONS)

    agent = client.agents.create_agent(
        model=model,
        name="weekly-digest",
        instructions=INSTRUCTIONS,
        tools=functions.definitions,
    )
    _AGENT_ID = agent.id
    log.info("Created weekly digest agent: %s", _AGENT_ID)
    return _AGENT_ID


def run_weekly_digest() -> dict:
    """
    Run the weekly digest: gather data, generate summary, post to Teams.

    Returns:
        {"summary": str, "posted": bool}
    """
    client = get_project_client()
    agent_id = _get_or_create_agent()

    thread = client.agents.threads.create()
    try:
        client.agents.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=(
                "Generate this week's compliance digest. Retrieve all the latest data, "
                "compose the digest, and then post it to the Teams channel."
            ),
        )

        run = client.agents.runs.create(
            thread_id=thread.id,
            agent_id=agent_id,
        )

        # Process tool calls in a loop until the run completes
        while run.status in ("queued", "in_progress", "requires_action"):
            if run.status == "requires_action" and isinstance(
                run.required_action, SubmitToolOutputsAction
            ):
                tool_outputs = []
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    if isinstance(tool_call, RequiredFunctionToolCall):
                        args = json.loads(tool_call.function.arguments)
                        result = _handle_tool_call(tool_call.function.name, args)
                        tool_outputs.append(
                            ToolOutput(tool_call_id=tool_call.id, output=result)
                        )

                run = client.agents.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )
            else:
                import time
                time.sleep(0.5)
                run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)

        if run.status == "failed":
            log.error("Weekly digest agent run failed: %s", run.last_error)
            raise RuntimeError(f"Agent run failed: {run.last_error}")

        # Extract the generated summary
        messages = client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING,
        )

        summary = ""
        for msg in messages.data:
            if msg.role == "assistant":
                for content in msg.content:
                    if hasattr(content, "text"):
                        summary += content.text.value

        return {"summary": summary, "posted": True}

    finally:
        client.agents.threads.delete(thread.id)

"""
Executive Briefing agent — generates CISO-ready compliance posture reports
using Foundry Agent Service with custom function tools for SQL data retrieval.

Replaces the prompt_flows/executive_briefing Prompt Flow.
"""
import json
import logging
import os

from azure.ai.agents.models import (
    FunctionTool,
    ListSortOrder,
    MessageRole,
    RequiredFunctionToolCall,
    SubmitToolOutputsAction,
    ToolOutput,
)

from shared.agent_client import get_project_client
from shared.sql_client import get_connection, set_admin_context

log = logging.getLogger(__name__)

_AGENT_ID: str | None = None

INSTRUCTIONS = """\
You are a Microsoft Purview Compliance Manager executive briefing generator for a
CISO. You produce clear, concise, and actionable compliance posture reports that
can be shared directly with organizational leadership and department/agency heads.

Write in a professional tone appropriate for a board audience. Avoid technical
jargon — translate compliance controls into business risk language. Use concrete
numbers and percentages. Flag anything that needs immediate attention.

To generate the briefing, call the available data retrieval tools to gather the
latest compliance posture data. Then structure your briefing as follows:
1. **Executive Summary** (3-4 sentences — lead with the compliance score, flag urgent risks)
2. **Trend Analysis** (Is the organization improving or declining? Call out specific movers)
3. **Department Scorecard** (Rank departments, highlight who needs support)
4. **Assessment Coverage** (Which regulations are well-covered vs. at risk)
5. **Top 5 Recommended Actions** (Prioritized by compliance score impact, with business justification)
6. **Risk Escalations** (Anything that needs leadership attention this week)

Keep total length under 600 words. This will be shared with non-technical executives.
Do not fabricate data — only reference numbers from tool call results.
"""

TOOL_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_latest_scores",
            "description": "Get the latest compliance scores for all monitored tenants, optionally filtered by department.",
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": "Optional department name to filter results.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_changes",
            "description": "Get week-over-week compliance score changes for all tenants, optionally filtered by department.",
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": "Optional department name to filter results.",
                    }
                },
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
            "name": "get_assessment_gaps",
            "description": "Get the top 10 compliance control gaps sorted by total points gap (highest impact first).",
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
            "name": "get_assessment_summary",
            "description": "Get assessment pass rates and compliance scores for all active assessments.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ── Tool handler functions ───────────────────────────────────────────────────

def _query_rows(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SQL query with admin context and return rows as dicts."""
    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]
    finally:
        conn.close()


def _handle_tool_call(name: str, arguments: dict) -> str:
    """Dispatch a tool call to the appropriate SQL query and return JSON."""
    department = arguments.get("department")

    if name == "get_latest_scores":
        if department:
            rows = _query_rows(
                "SELECT * FROM v_latest_compliance_scores WHERE department = ? ORDER BY compliance_pct ASC",
                (department,),
            )
        else:
            rows = _query_rows(
                "SELECT * FROM v_latest_compliance_scores ORDER BY compliance_pct ASC"
            )
        return json.dumps(rows, default=str)

    elif name == "get_weekly_changes":
        if department:
            rows = _query_rows(
                "SELECT * FROM v_compliance_weekly_change WHERE department = ? ORDER BY wow_change ASC",
                (department,),
            )
        else:
            rows = _query_rows(
                "SELECT * FROM v_compliance_weekly_change ORDER BY wow_change ASC"
            )
        return json.dumps(rows, default=str)

    elif name == "get_department_rollup":
        rows = _query_rows(
            "SELECT * FROM v_compliance_department_rollup ORDER BY avg_compliance_pct ASC"
        )
        return json.dumps(rows, default=str)

    elif name == "get_assessment_gaps":
        rows = _query_rows(
            "SELECT TOP 10 * FROM v_assessment_gaps ORDER BY total_gap DESC"
        )
        return json.dumps(rows, default=str)

    elif name == "get_assessment_summary":
        rows = _query_rows(
            "SELECT * FROM v_assessment_summary ORDER BY compliance_score ASC"
        )
        return json.dumps(rows, default=str)

    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


# ── Agent lifecycle ──────────────────────────────────────────────────────────

def _get_or_create_agent() -> str:
    """Lazily create the executive briefing agent and cache its ID."""
    global _AGENT_ID
    if _AGENT_ID is not None:
        return _AGENT_ID

    client = get_project_client()
    model = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    functions = FunctionTool(functions=TOOL_FUNCTIONS)

    agent = client.agents.create_agent(
        model=model,
        name="executive-briefing",
        instructions=INSTRUCTIONS,
        tools=functions.definitions,
    )
    _AGENT_ID = agent.id
    log.info("Created executive briefing agent: %s", _AGENT_ID)
    return _AGENT_ID


def generate_briefing(department: str | None = None) -> dict:
    """
    Generate an executive compliance briefing.

    The agent will call the SQL data retrieval tools automatically,
    then synthesize a structured briefing.

    Returns:
        {"briefing": str, "data": dict}
    """
    client = get_project_client()
    agent_id = _get_or_create_agent()

    prompt = "Generate an executive Compliance Manager posture briefing."
    if department:
        prompt += f" Focus on the {department} department."
    prompt += " Start by retrieving the latest data using the available tools."

    thread = client.agents.threads.create()
    try:
        client.agents.messages.create(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=prompt,
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
            log.error("Briefing agent run failed: %s", run.last_error)
            raise RuntimeError(f"Agent run failed: {run.last_error}")

        # Extract the briefing text
        messages = client.agents.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING,
        )

        briefing = ""
        for msg in messages.data:
            if msg.role == "assistant":
                for content in msg.content:
                    if hasattr(content, "text"):
                        briefing += content.text.value

        return {"briefing": briefing}

    finally:
        client.agents.threads.delete(thread.id)

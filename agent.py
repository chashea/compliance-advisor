#!/usr/bin/env python3
"""Compliance Advisor — Azure AI Foundry conversational agent (Responses API)."""
import json
import os
from dotenv import load_dotenv

load_dotenv()

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from pathlib import Path

import compliance_tools  # all 8 tool functions live here

MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
SYSTEM_PROMPT = Path("agents/system_prompt.txt").read_text()

# Use AzureCliCredential (az login) for Foundry.
# The service principal in .env is scoped to Microsoft Graph for sync.py only.
client = AIProjectClient(
    endpoint=os.environ["AIPROJECT_ENDPOINT"],
    credential=AzureCliCredential(),
)
oai = client.get_openai_client()

# --- Tool schemas ---
TOOLS = [
    {
        "type": "function",
        "name": "get_secure_score",
        "description": compliance_tools.get_secure_score.__doc__,
        "parameters": {"type": "object", "properties": {}, "required": []},
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_top_gaps",
        "description": compliance_tools.get_top_gaps.__doc__,
        "parameters": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of gaps to return (default 10)."},
            },
            "required": [],
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_weekly_change",
        "description": compliance_tools.get_weekly_change.__doc__,
        "parameters": {"type": "object", "properties": {}, "required": []},
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_compliance_score",
        "description": compliance_tools.get_compliance_score.__doc__,
        "parameters": {"type": "object", "properties": {}, "required": []},
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_assessments",
        "description": compliance_tools.get_assessments.__doc__,
        "parameters": {
            "type": "object",
            "properties": {
                "regulation": {"type": "string", "description": "Optional regulation name to filter by (e.g. 'NIST 800-53')."},
            },
            "required": [],
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_improvement_actions",
        "description": compliance_tools.get_improvement_actions.__doc__,
        "parameters": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of actions to return (default 10)."},
                "regulation": {"type": "string", "description": "Optional regulation name to filter by."},
            },
            "required": [],
        },
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_regulation_coverage",
        "description": compliance_tools.get_regulation_coverage.__doc__,
        "parameters": {"type": "object", "properties": {}, "required": []},
        "strict": False,
    },
    {
        "type": "function",
        "name": "get_category_breakdown",
        "description": compliance_tools.get_category_breakdown.__doc__,
        "parameters": {"type": "object", "properties": {}, "required": []},
        "strict": False,
    },
]

_TOOL_FUNCTIONS = {
    "get_secure_score": compliance_tools.get_secure_score,
    "get_top_gaps": compliance_tools.get_top_gaps,
    "get_weekly_change": compliance_tools.get_weekly_change,
    "get_compliance_score": compliance_tools.get_compliance_score,
    "get_assessments": compliance_tools.get_assessments,
    "get_improvement_actions": compliance_tools.get_improvement_actions,
    "get_regulation_coverage": compliance_tools.get_regulation_coverage,
    "get_category_breakdown": compliance_tools.get_category_breakdown,
}


def _execute_tools(response) -> list[dict]:
    """Execute any function calls in a response and return tool result items."""
    results = []
    for item in response.output:
        if item.type == "function_call":
            func = _TOOL_FUNCTIONS[item.name]
            args = json.loads(item.arguments) if item.arguments else {}
            output = func(**args)
            results.append({
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": output,
            })
    return results


def _respond(user_message: str, previous_response_id: str | None) -> tuple[str, str]:
    """Send a message, handle tool calls, return (reply_text, response_id)."""
    resp = oai.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=user_message,
        tools=TOOLS,
        previous_response_id=previous_response_id,
    )

    # Loop until no more tool calls
    while resp.status == "requires_action" or any(
        item.type == "function_call" for item in resp.output
    ):
        tool_results = _execute_tools(resp)
        if not tool_results:
            break
        resp = oai.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=tool_results,
            tools=TOOLS,
            previous_response_id=resp.id,
        )

    return resp.output_text, resp.id


def chat():
    print("Compliance Advisor ready. Type 'quit' to exit.\n")
    previous_id = None
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        reply, previous_id = _respond(user_input, previous_id)
        print(f"\nAdvisor: {reply}\n")


if __name__ == "__main__":
    chat()

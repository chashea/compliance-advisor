#!/usr/bin/env python3
"""Compliance Advisor — Azure AI Foundry conversational agent.

Registers a named Prompt Agent version in the Foundry project and then routes
chat turns through that registered agent using `agent_reference`.
"""
import argparse
import json
import os
from dotenv import load_dotenv

load_dotenv()

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
from azure.identity import AzureCliCredential
from pathlib import Path

import compliance_tools  # all 8 tool functions live here

MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AGENT_NAME = os.environ.get("FOUNDRY_AGENT_NAME", "compliance-advisor")
SYSTEM_PROMPT = Path("agents/system_prompt.txt").read_text(encoding="utf-8")

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
    {
        "type": "function",
        "name": "search_knowledge",
        "description": compliance_tools.search_knowledge.__doc__,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language knowledge search query."},
                "top": {"type": "integer", "description": "Maximum number of documents to return (default 5, max 20)."},
                "category": {"type": "string", "description": "Optional category filter such as NIST, ISO27001, SOC2, or RemediationGuide."},
            },
            "required": ["query"],
        },
        "strict": False,
    },
]


def _build_prompt_agent_definition() -> PromptAgentDefinition:
    function_tools = [
        FunctionTool(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
            strict=tool["strict"],
        )
        for tool in TOOLS
    ]
    return PromptAgentDefinition(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        tools=function_tools,
    )


def register_foundry_agent_version(agent_name: str = AGENT_NAME):
    """Create a new named Foundry agent version with prompt and tool schema."""
    definition = _build_prompt_agent_definition()
    return client.agents.create_version(
        agent_name=agent_name,
        definition=definition,
        description="Compliance Advisor prompt agent with SQL-backed compliance tools.",
    )

_TOOL_FUNCTIONS = {
    "get_secure_score": compliance_tools.get_secure_score,
    "get_top_gaps": compliance_tools.get_top_gaps,
    "get_weekly_change": compliance_tools.get_weekly_change,
    "get_compliance_score": compliance_tools.get_compliance_score,
    "get_assessments": compliance_tools.get_assessments,
    "get_improvement_actions": compliance_tools.get_improvement_actions,
    "get_regulation_coverage": compliance_tools.get_regulation_coverage,
    "get_category_breakdown": compliance_tools.get_category_breakdown,
    "search_knowledge": compliance_tools.search_knowledge,
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


def _respond(user_message: str, previous_response_id: str | None, agent_name: str) -> tuple[str, str]:
    """Send a message via the registered Foundry agent and process tool calls."""
    agent_reference = {"type": "agent_reference", "name": agent_name}
    resp = oai.responses.create(
        input=user_message,
        previous_response_id=previous_response_id,
        extra_body={"agent_reference": agent_reference},
    )

    # Loop until no more tool calls
    while resp.status == "requires_action" or any(
        item.type == "function_call" for item in resp.output
    ):
        tool_results = _execute_tools(resp)
        if not tool_results:
            break
        resp = oai.responses.create(
            input=tool_results,
            previous_response_id=resp.id,
            extra_body={"agent_reference": agent_reference},
        )

    return resp.output_text, resp.id


def chat(agent_name: str):
    agent = register_foundry_agent_version(agent_name=agent_name)
    print(
        f"Registered Foundry Agent: {agent.name} v{agent.version} (id: {agent.id})"
    )
    print("Compliance Advisor ready. Type 'quit' to exit.\n")
    previous_id = None
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        reply, previous_id = _respond(user_input, previous_id, agent_name=agent_name)
        print(f"\nAdvisor: {reply}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Register and run the Compliance Advisor Foundry agent."
    )
    parser.add_argument(
        "--register-only",
        action="store_true",
        help="Register a new Foundry agent version and exit.",
    )
    parser.add_argument(
        "--agent-name",
        default=AGENT_NAME,
        help="Foundry agent name to version (default: FOUNDRY_AGENT_NAME or compliance-advisor).",
    )
    args = parser.parse_args()

    agent = register_foundry_agent_version(agent_name=args.agent_name)
    print(f"Registered Foundry Agent: {agent.name} v{agent.version} (id: {agent.id})")

    if not args.register_only:
        print("Compliance Advisor ready. Type 'quit' to exit.\n")
        previous_id = None
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if not user_input:
                continue

            reply, previous_id = _respond(user_input, previous_id, agent_name=args.agent_name)
            print(f"\nAdvisor: {reply}\n")


if __name__ == "__main__":
    main()

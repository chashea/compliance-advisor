#!/usr/bin/env python3
"""Compliance Advisor — Azure OpenAI conversational agent.

Uses the OpenAI Python SDK with Azure AD token auth (AzureCliCredential)
to call a GPT-4o deployment. Function tools query the local SQLite database
via compliance_tools.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from openai import AzureOpenAI
from azure.identity import AzureCliCredential, get_bearer_token_provider

import compliance_tools

AZURE_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
SYSTEM_PROMPT = Path("agents/system_prompt.txt").read_text(encoding="utf-8")

token_provider = get_bearer_token_provider(AzureCliCredential(), "https://cognitiveservices.azure.com/.default")

client = AzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    azure_ad_token_provider=token_provider,
    api_version="2024-12-01-preview",
)

# --- Tool schemas (OpenAI function calling format) ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_secure_score",
            "description": compliance_tools.get_secure_score.__doc__,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_gaps",
            "description": compliance_tools.get_top_gaps.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of gaps to return (default 10)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_change",
            "description": compliance_tools.get_weekly_change.__doc__,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_compliance_score",
            "description": compliance_tools.get_compliance_score.__doc__,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_assessments",
            "description": compliance_tools.get_assessments.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "regulation": {
                        "type": "string",
                        "description": "Optional regulation name to filter by (e.g. 'NIST 800-53').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
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
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_regulation_coverage",
            "description": compliance_tools.get_regulation_coverage.__doc__,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_breakdown",
            "description": compliance_tools.get_category_breakdown.__doc__,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": compliance_tools.search_knowledge.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language knowledge search query."},
                    "top": {
                        "type": "integer",
                        "description": "Maximum number of documents to return (default 5, max 20).",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter such as NIST, ISO27001, SOC2, or RemediationGuide.",
                    },
                },
                "required": ["query"],
            },
        },
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
    "search_knowledge": compliance_tools.search_knowledge,
}


def _respond(user_message: str, messages: list[dict] | None = None) -> tuple[str, list[dict]]:
    """Send a message to Azure OpenAI and process tool calls. Returns (reply, updated messages)."""
    if messages is None:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    messages.append({"role": "user", "content": user_message})

    while True:
        resp = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        choice = resp.choices[0]

        if choice.finish_reason == "tool_calls" or choice.message.tool_calls:
            messages.append(choice.message)
            for tc in choice.message.tool_calls:
                func = _TOOL_FUNCTIONS[tc.function.name]
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                output = func(**args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": output,
                    }
                )
        else:
            messages.append(choice.message)
            return choice.message.content, messages


def chat():
    print("Compliance Advisor ready (Azure OpenAI). Type 'quit' to exit.\n")
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        reply, messages = _respond(user_input, messages)
        print(f"\nAdvisor: {reply}\n")


if __name__ == "__main__":
    chat()

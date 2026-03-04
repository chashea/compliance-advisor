#!/usr/bin/env python3
"""Compliance Advisor — Azure AI Foundry conversational agent."""
import os
from dotenv import load_dotenv

load_dotenv()

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, ToolSet, MessageRole
from azure.identity import DefaultAzureCredential
from pathlib import Path

import compliance_tools  # all 8 tool functions live here

AGENT_NAME = "Compliance Advisor"
MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
SYSTEM_PROMPT = Path("agents/system_prompt.txt").read_text()

client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str=os.environ["AIPROJECT_CONNECTION_STRING"],
)

# Register all tool functions
tool_set = ToolSet()
tool_set.add(FunctionTool(functions=[
    compliance_tools.get_secure_score,
    compliance_tools.get_top_gaps,
    compliance_tools.get_weekly_change,
    compliance_tools.get_compliance_score,
    compliance_tools.get_assessments,
    compliance_tools.get_improvement_actions,
    compliance_tools.get_regulation_coverage,
    compliance_tools.get_category_breakdown,
]))


def get_or_create_agent():
    """Return an existing Compliance Advisor agent or create a new one."""
    for a in client.agents.list_agents():
        if a.name == AGENT_NAME:
            return a
    return client.agents.create_agent(
        model=MODEL,
        name=AGENT_NAME,
        instructions=SYSTEM_PROMPT,
        tools=tool_set.definitions,
    )


def chat():
    agent = get_or_create_agent()
    thread = client.agents.create_thread()
    print(f"Compliance Advisor ready (agent: {agent.id}). Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        client.agents.create_message(
            thread_id=thread.id, role=MessageRole.USER, content=user_input
        )
        run = client.agents.create_and_process_run(
            thread_id=thread.id, agent_id=agent.id, tool_set=tool_set
        )

        messages = client.agents.list_messages(thread_id=thread.id)
        for msg in messages:
            if msg.role == MessageRole.AGENT:
                print(f"\nAdvisor: {msg.content[0].text.value}\n")
                break


if __name__ == "__main__":
    chat()

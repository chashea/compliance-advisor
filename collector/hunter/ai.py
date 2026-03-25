"""
AI module for the Purview threat hunter.

Uses Azure OpenAI chat completions (not Assistants API) for:
1. generate_kql() — Translate natural language questions to KQL
2. narrate_results() — Summarize query results in plain English
"""

import logging
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from collector.hunter.schemas import build_schema_prompt
from collector.hunter.templates import build_examples_prompt

log = logging.getLogger(__name__)

_client: AzureOpenAI | None = None

KQL_SYSTEM_PROMPT = """You are a KQL query generator for Microsoft Defender XDR Advanced Hunting,
specialized in Microsoft Purview compliance data.

You generate KQL queries that target four tables: DataSecurityEvents, CloudAppEvents, AlertInfo, AlertEvidence.

## Rules
- Return ONLY the KQL query. No markdown fencing, no explanation, no commentary.
- Use KQL syntax: pipe operators, ago() for time, == for equality, has/contains for partial string match.
- Always include `| limit N` at the end (default 50 unless the user specifies otherwise).
- Maximum lookback is 30 days (ago(30d)).
- Only reference the four allowed tables. Never reference tables that don't exist.
- For joins between AlertInfo and AlertEvidence, use: AlertInfo | join AlertEvidence on AlertId
- When the exact ActionType is uncertain, use `has` or `contains` instead of `==`.
- Use `isnotempty()` to filter for non-null dynamic columns.
- Use `summarize` with `count()`, `dcount()`, `make_set()` for aggregations.
- Use `project` to select only relevant columns.
- Order results by Timestamp desc unless the query is an aggregation.

## Table Schemas

{schema}

{examples}"""

NARRATE_SYSTEM_PROMPT = """You are a senior threat hunter analyzing Microsoft Purview / Defender XDR data.
Provide a clear, actionable analysis of the query results.

## Format
- **Summary**: 1-2 sentence overview of what was found (or not found).
- **Key Findings**: Bullet points highlighting notable patterns, anomalies, or high-risk items.
  Reference specific users, files, counts, and timestamps.
- **Recommendations**: 1-3 actionable next steps based on the findings.

## Guidelines
- Be concise and direct. No filler.
- If results are empty, say so clearly and suggest alternative queries or checks.
- Highlight deviations from normal patterns (volume spikes, unusual users, off-hours activity).
- Never fabricate data — only reference what is in the results."""


def _get_client(endpoint: str) -> AzureOpenAI:
    global _client
    if _client is None:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        _client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-06-01",
        )
    return _client


def generate_kql(
    question: str,
    endpoint: str,
    deployment: str = "gpt-4o",
) -> str:
    """Translate a natural language question to a KQL query.

    Args:
        question: The user's natural language question.
        endpoint: Azure OpenAI endpoint URL.
        deployment: Model deployment name.

    Returns:
        A KQL query string.
    """
    client = _get_client(endpoint)
    schema = build_schema_prompt()
    examples = build_examples_prompt()

    system_prompt = KQL_SYSTEM_PROMPT.format(schema=schema, examples=examples)

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=1024,
    )

    kql = response.choices[0].message.content.strip()
    # Strip markdown code fences if the model includes them despite instructions
    if kql.startswith("```"):
        lines = kql.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        kql = "\n".join(lines).strip()

    log.debug("Generated KQL:\n%s", kql)
    return kql


def fix_kql(
    question: str,
    failed_kql: str,
    error_message: str,
    endpoint: str,
    deployment: str = "gpt-4o",
) -> str:
    """Fix a KQL query that returned an error.

    Args:
        question: The original natural language question.
        failed_kql: The KQL that failed.
        error_message: The error from the API.
        endpoint: Azure OpenAI endpoint URL.
        deployment: Model deployment name.

    Returns:
        A corrected KQL query string.
    """
    client = _get_client(endpoint)
    schema = build_schema_prompt()
    examples = build_examples_prompt()

    system_prompt = KQL_SYSTEM_PROMPT.format(schema=schema, examples=examples)

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
            {"role": "assistant", "content": failed_kql},
            {
                "role": "user",
                "content": (
                    f"The query above returned an error:\n{error_message}\n\n"
                    "Fix the KQL query. Return ONLY the corrected query."
                ),
            },
        ],
        temperature=0,
        max_tokens=1024,
    )

    kql = response.choices[0].message.content.strip()
    if kql.startswith("```"):
        lines = kql.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        kql = "\n".join(lines).strip()

    log.debug("Fixed KQL:\n%s", kql)
    return kql


def narrate_results(
    question: str,
    kql: str,
    results: list[dict[str, Any]],
    total_rows: int,
    endpoint: str,
    deployment: str = "gpt-4o",
) -> str:
    """Generate an AI narrative summarizing query results.

    Args:
        question: The original question.
        kql: The KQL query that was executed.
        results: The result rows (may be truncated for context).
        total_rows: Total number of rows returned.
        endpoint: Azure OpenAI endpoint URL.
        deployment: Model deployment name.

    Returns:
        A markdown-formatted analysis string.
    """
    client = _get_client(endpoint)

    # Truncate results for context window — include first 30 rows
    display_results = results[:30]
    truncation_note = ""
    if total_rows > len(display_results):
        truncation_note = f"\n(Showing {len(display_results)} of {total_rows} total rows)"

    user_content = (
        f"## Question\n{question}\n\n"
        f"## KQL Query\n{kql}\n\n"
        f"## Results ({total_rows} rows){truncation_note}\n{_format_results_for_prompt(display_results)}"
    )

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": NARRATE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        max_tokens=2048,
    )

    return response.choices[0].message.content.strip()


def _format_results_for_prompt(results: list[dict[str, Any]]) -> str:
    """Format result rows as a readable text table for the LLM."""
    if not results:
        return "(No results)"

    # Use first row keys as headers
    headers = list(results[0].keys())
    lines = [" | ".join(headers)]
    lines.append(" | ".join("---" for _ in headers))
    for row in results:
        lines.append(" | ".join(str(row.get(h, "")) for h in headers))
    return "\n".join(lines)

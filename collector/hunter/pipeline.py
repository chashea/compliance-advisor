"""
Orchestrates the NL → KQL → Execute → Narrate pipeline.

Handles the retry loop for invalid KQL queries.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from collector.hunter.ai import fix_kql, generate_kql, narrate_results
from collector.hunter.config import HunterSettings
from collector.hunter.graph import HuntingQueryError, HuntingQueryResult, run_hunting_query

log = logging.getLogger(__name__)


@dataclass
class HuntResult:
    """Complete result of a hunt pipeline execution."""

    question: str
    kql: str
    results: list[dict[str, Any]]
    row_count: int
    narrative: str = ""
    retries: int = 0
    errors: list[str] = field(default_factory=list)


def _get_graph_token(settings: HunterSettings) -> str:
    """Acquire a Graph API token.

    Uses MSAL client credentials if CLIENT_ID/CLIENT_SECRET/TENANT_ID are set,
    otherwise falls back to DefaultAzureCredential (az login).
    """
    if settings.use_client_credentials:
        import msal

        authority = f"https://login.microsoftonline.com/{settings.TENANT_ID}"
        app = msal.ConfidentialClientApplication(
            client_id=settings.CLIENT_ID,
            client_credential=settings.CLIENT_SECRET,
            authority=authority,
        )
        result = app.acquire_token_for_client(scopes=[settings.graph_scope])
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown"))
            raise RuntimeError(f"MSAL auth failed: {error}")
        log.info("Authenticated via client credentials (tenant=%s)", settings.TENANT_ID)
        return result["access_token"]

    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token(settings.graph_scope)
    log.info("Authenticated via DefaultAzureCredential")
    return token.token


def hunt(
    question: str,
    settings: HunterSettings,
    kql_override: str | None = None,
    skip_narrate: bool = False,
) -> HuntResult:
    """Run the full hunt pipeline.

    Args:
        question: Natural language question or description.
        settings: Hunter configuration.
        kql_override: If provided, skip NL→KQL and use this KQL directly.
        skip_narrate: If True, skip the AI narrative step.

    Returns:
        HuntResult with query, results, and optional narrative.
    """
    token = _get_graph_token(settings)

    # Stage 1: Generate KQL (or use override)
    if kql_override:
        kql = kql_override
        log.info("Using provided KQL query")
    else:
        log.info("Generating KQL from question: %s", question)
        kql = generate_kql(
            question=question,
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        )

    result = HuntResult(question=question, kql=kql, results=[], row_count=0)

    # Stage 2: Execute KQL (with retry on invalid query)
    query_result: HuntingQueryResult | None = None
    for attempt in range(1 + settings.MAX_RETRIES):
        try:
            query_result = run_hunting_query(
                kql=result.kql,
                token=token,
                base_url=settings.GRAPH_BASE_URL,
            )
            break
        except HuntingQueryError as exc:
            if exc.status_code == 400 and attempt < settings.MAX_RETRIES and not kql_override:
                result.retries += 1
                result.errors.append(exc.kql_error)
                log.warning("KQL error (attempt %d/%d): %s", attempt + 1, settings.MAX_RETRIES + 1, exc.kql_error)

                # Stage 3: Fix KQL via AI
                result.kql = fix_kql(
                    question=question,
                    failed_kql=result.kql,
                    error_message=exc.kql_error,
                    endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    deployment=settings.AZURE_OPENAI_DEPLOYMENT,
                )
            else:
                raise

    if query_result is None:
        raise HuntingQueryError("All query attempts failed")

    result.results = query_result.results
    result.row_count = query_result.row_count

    # Check for empty DataSecurityEvents
    if result.row_count == 0 and "DataSecurityEvents" in result.kql:
        log.warning(
            "DataSecurityEvents returned 0 rows. " "Ensure Insider Risk Management data is opted in to Defender XDR."
        )

    # Stage 4: Narrate results
    if not skip_narrate:
        log.info("Generating AI narrative for %d results", result.row_count)
        result.narrative = narrate_results(
            question=question,
            kql=result.kql,
            results=result.results,
            total_rows=result.row_count,
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        )

    return result

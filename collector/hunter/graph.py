"""
Graph API client for Defender XDR Advanced Hunting.

Executes KQL queries via POST /security/runHuntingQuery.
"""

import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)


class HuntingQueryError(Exception):
    """Raised when runHuntingQuery fails."""

    def __init__(self, message: str, status_code: int = 0, kql_error: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.kql_error = kql_error


class HuntingQueryResult:
    """Parsed result from runHuntingQuery."""

    def __init__(self, schema: list[dict[str, str]], results: list[dict[str, Any]]):
        self.schema = schema
        self.results = results

    @property
    def row_count(self) -> int:
        return len(self.results)

    @property
    def column_names(self) -> list[str]:
        return [col["Name"] for col in self.schema]


def _build_session(token: str) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST"],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )
    return session


def run_hunting_query(kql: str, token: str, base_url: str = "https://graph.microsoft.com/v1.0") -> HuntingQueryResult:
    """Execute a KQL query via Graph API runHuntingQuery.

    Args:
        kql: The KQL query string.
        token: Bearer token with ThreatHunting.Read.All permission.
        base_url: Graph API base URL.

    Returns:
        HuntingQueryResult with schema and results.

    Raises:
        HuntingQueryError: On API errors (400 invalid KQL, 403 no permission, etc.)
    """
    url = f"{base_url}/security/runHuntingQuery"
    session = _build_session(token)

    log.debug("Executing KQL query:\n%s", kql)

    try:
        resp = session.post(url, json={"Query": kql}, timeout=210)
    except requests.exceptions.RequestException as exc:
        raise HuntingQueryError(f"Network error: {exc}") from exc

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "60"))
        log.warning("Rate limited by Graph API, waiting %d seconds", retry_after)
        time.sleep(retry_after)
        try:
            resp = session.post(url, json={"Query": kql}, timeout=210)
        except requests.exceptions.RequestException as exc:
            raise HuntingQueryError(f"Network error on retry: {exc}") from exc

    if resp.status_code == 403:
        raise HuntingQueryError(
            "Missing ThreatHunting.Read.All permission. "
            "Grant this permission to your app registration and ensure admin consent.",
            status_code=403,
        )

    if resp.status_code == 400:
        error_body = resp.text
        try:
            error_json = resp.json()
            error_msg = error_json.get("error", {}).get("message", error_body)
        except Exception:
            error_msg = error_body
        raise HuntingQueryError(
            f"Invalid KQL query: {error_msg}",
            status_code=400,
            kql_error=error_msg,
        )

    if resp.status_code != 200:
        raise HuntingQueryError(
            f"Unexpected status {resp.status_code}: {resp.text}",
            status_code=resp.status_code,
        )

    data = resp.json()
    schema = data.get("schema", [])
    results = data.get("results", [])

    log.info("Query returned %d rows", len(results))
    return HuntingQueryResult(schema=schema, results=results)

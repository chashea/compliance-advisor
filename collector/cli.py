"""
CLI entrypoint for the per-tenant compliance collector.

Usage:
    compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT>
    compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> --dry-run
"""

import json
import logging
import sys

import click

from collector.auth import get_compliance_token
from collector.compliance_client import (
    compute_score_from_actions,
    get_assessments,
    get_compliance_score,
    get_improvement_actions_detail,
)
from collector.config import CollectorSettings
from collector.payload import CompliancePayload
from collector.submit import submit_payload

log = logging.getLogger("collector")


@click.command()
@click.option("--tenant-id", envvar="TENANT_ID", help="Target tenant GUID")
@click.option("--agency-id", envvar="AGENCY_ID", help="Logical agency identifier")
@click.option("--department", envvar="DEPARTMENT", help="Department name for filtering")
@click.option("--display-name", envvar="DISPLAY_NAME", default="", help="Human-readable tenant name")
@click.option("--dry-run", is_flag=True, help="Collect and print payload without submitting")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(
    tenant_id: str,
    agency_id: str,
    department: str,
    display_name: str,
    dry_run: bool,
    verbose: bool,
):
    """Collect Compliance Manager data from a GCC tenant."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    overrides = {}
    if tenant_id:
        overrides["TENANT_ID"] = tenant_id
    if agency_id:
        overrides["AGENCY_ID"] = agency_id
    if department:
        overrides["DEPARTMENT"] = department
    if display_name:
        overrides["DISPLAY_NAME"] = display_name

    try:
        settings = CollectorSettings(**overrides)
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    click.echo(
        f"Collecting from tenant {settings.TENANT_ID} "
        f"(agency: {settings.AGENCY_ID}, dept: {settings.DEPARTMENT})"
    )

    # Authenticate via ROPC
    try:
        token = get_compliance_token(settings)
    except RuntimeError as e:
        click.echo(f"Authentication failed: {e}", err=True)
        sys.exit(1)

    base_url = settings.compliance_base
    click.echo(f"Authenticated. Using Compliance Manager API at {base_url}")

    # Collect data
    click.echo("Collecting compliance score...")
    score = get_compliance_score(base_url, token)

    click.echo("Collecting assessments...")
    assessments = get_assessments(base_url, token)

    click.echo("Collecting improvement actions...")
    actions = get_improvement_actions_detail(base_url, token)

    # Use self-calculated score if portal score is zero/unavailable
    if score["max_score"] == 0 and actions:
        click.echo("Portal score unavailable, computing from improvement actions...")
        score = compute_score_from_actions(actions)

    click.echo(
        f"Score: {score['current_score']:.0f}/{score['max_score']:.0f} "
        f"| Assessments: {len(assessments)} | Actions: {len(actions)}"
    )

    # Build payload
    payload = CompliancePayload(
        tenant_id=settings.TENANT_ID,
        agency_id=settings.AGENCY_ID,
        department=settings.DEPARTMENT,
        display_name=settings.DISPLAY_NAME or settings.AGENCY_ID,
        timestamp=CompliancePayload.now_iso(),
        compliance_score_current=score["current_score"],
        compliance_score_max=score["max_score"],
        assessments=assessments,
        improvement_actions=actions,
    )

    payload_dict = payload.to_dict()

    if dry_run:
        click.echo("\n--- DRY RUN: Payload (not submitted) ---")
        click.echo(json.dumps(payload_dict, indent=2, default=str))
        return

    # Submit to Function App
    click.echo("Submitting payload to Function App...")
    try:
        result = submit_payload(payload_dict, settings)
        click.echo(f"Success: {json.dumps(result)}")
    except Exception as e:
        click.echo(f"Submission failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

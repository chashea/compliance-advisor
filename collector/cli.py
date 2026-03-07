"""
CLI entrypoint for the per-tenant Purview data collector.

Usage:
    compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT>
    compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> --dry-run
"""

import json
import logging
import sys

import click

from collector.auth import get_graph_token
from collector.compliance_client import (
    get_control_profiles,
    get_control_scores,
    get_risky_users,
    get_secure_scores,
    get_security_alerts,
    get_security_incidents,
    get_service_health,
)
from collector.config import CollectorSettings
from collector.payload import PurviewPayload
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
    """Collect Purview security and compliance data from a tenant via Microsoft Graph."""
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
        token = get_graph_token(settings)
    except RuntimeError as e:
        click.echo(f"Authentication failed: {e}", err=True)
        sys.exit(1)

    click.echo("Authenticated. Collecting data from Microsoft Graph...")

    # Collect data
    click.echo("  Secure Scores...")
    secure_scores = get_secure_scores(token)

    click.echo("  Control Scores...")
    control_scores = get_control_scores(token)

    click.echo("  Control Profiles...")
    control_profiles = get_control_profiles(token)

    click.echo("  Security Alerts...")
    alerts = get_security_alerts(token)

    click.echo("  Security Incidents...")
    incidents = get_security_incidents(token)

    click.echo("  Risky Users...")
    risky_users = get_risky_users(token)

    click.echo("  Service Health...")
    service_health = get_service_health(token)

    # Current score from latest snapshot
    current_score = secure_scores[0]["current_score"] if secure_scores else 0.0
    max_score = secure_scores[0]["max_score"] if secure_scores else 0.0

    click.echo(
        f"\nScore: {current_score:.1f}/{max_score:.1f} "
        f"| Controls: {len(control_scores)} | Alerts: {len(alerts)} "
        f"| Incidents: {len(incidents)} | Risky Users: {len(risky_users)} "
        f"| Services: {len(service_health)}"
    )

    # Build payload
    payload = PurviewPayload(
        tenant_id=settings.TENANT_ID,
        agency_id=settings.AGENCY_ID,
        department=settings.DEPARTMENT,
        display_name=settings.DISPLAY_NAME or settings.AGENCY_ID,
        timestamp=PurviewPayload.now_iso(),
        secure_score_current=current_score,
        secure_score_max=max_score,
        secure_scores=secure_scores,
        control_scores=control_scores,
        control_profiles=control_profiles,
        security_alerts=alerts,
        security_incidents=incidents,
        risky_users=risky_users,
        service_health=service_health,
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

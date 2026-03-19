"""
CLI entrypoint for the per-tenant compliance data collector.

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
    get_audit_log_records,
    get_comm_compliance_policies,
    get_dlp_alerts,
    get_ediscovery_cases,
    get_improvement_actions,
    get_info_barrier_policies,
    get_irm_alerts,
    get_protection_scopes,
    get_retention_events,
    get_retention_labels,
    get_secure_scores,
    get_sensitivity_labels,
    get_subject_rights_requests,
    get_user_content_policies,
)
from collector.config import CollectorSettings
from collector.payload import CompliancePayload
from collector.submit import submit_payload
from collector.telemetry import track_event

log = logging.getLogger("collector")


@click.command()
@click.option("--tenant-id", envvar="TENANT_ID", help="Target tenant GUID")
@click.option("--agency-id", envvar="AGENCY_ID", help="Logical agency identifier")
@click.option("--department", envvar="DEPARTMENT", help="Department name for filtering")
@click.option("--display-name", envvar="DISPLAY_NAME", default="", help="Human-readable tenant name")
@click.option("--dry-run", is_flag=True, help="Collect and print payload without submitting")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option(
    "--actions-category",
    envvar="ACTIONS_CATEGORY",
    default="",
    help="Filter improvement actions by controlCategory (e.g. Data, Identity, Device). Default: all categories.",
)
def main(
    tenant_id: str,
    agency_id: str,
    department: str,
    display_name: str,
    dry_run: bool,
    verbose: bool,
    actions_category: str | None,
):
    """Collect compliance workload data from a tenant via Microsoft Graph."""
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
        f"Collecting from tenant {settings.TENANT_ID} " f"(agency: {settings.AGENCY_ID}, dept: {settings.DEPARTMENT})"
    )

    # Authenticate via ROPC
    try:
        token = get_graph_token(settings)
    except RuntimeError as e:
        click.echo(f"Authentication failed: {e}", err=True)
        track_event(
            settings.APPINSIGHTS_CONNECTION_STRING,
            "CollectorRun",
            {
                "tenant_id": settings.TENANT_ID,
                "agency_id": settings.AGENCY_ID,
                "status": "auth_failed",
                "error": str(e),
            },
        )
        sys.exit(1)

    click.echo("Authenticated. Collecting compliance data from Microsoft Graph...")

    # Collect data
    click.echo("  eDiscovery Cases...")
    ediscovery_cases = get_ediscovery_cases(token)

    click.echo("  Sensitivity Labels...")
    sensitivity_labels = get_sensitivity_labels(token)

    click.echo("  Retention Labels...")
    retention_labels = get_retention_labels(token)

    click.echo("  Retention Events...")
    retention_events = get_retention_events(token)

    click.echo("  Audit Log Records...")
    audit_records = get_audit_log_records(token, days=settings.AUDIT_LOG_DAYS)

    click.echo("  DLP Alerts...")
    dlp_alerts = get_dlp_alerts(token)

    click.echo("  IRM Alerts...")
    irm_alerts = get_irm_alerts(token)

    click.echo("  Subject Rights Requests...")
    subject_rights_requests = get_subject_rights_requests(token)

    click.echo("  Communication Compliance Policies...")
    comm_compliance_policies = get_comm_compliance_policies(token)

    click.echo("  Information Barrier Policies...")
    info_barrier_policies = get_info_barrier_policies(token)

    click.echo("  Protection Scopes...")
    protection_scopes = get_protection_scopes(token)

    click.echo("  Secure Score...")
    secure_scores = get_secure_scores(token)

    click.echo("  Improvement Actions...")
    improvement_actions = get_improvement_actions(token, category=actions_category or None)

    click.echo("  User Content Policies...")
    user_content_policies = get_user_content_policies(token)

    click.echo(
        f"\neDiscovery: {len(ediscovery_cases)} | Labels: {len(sensitivity_labels)} "
        f"| Retention: {len(retention_labels)} labels, {len(retention_events)} events "
        f"| Audit: {len(audit_records)} | DLP: {len(dlp_alerts)} | IRM: {len(irm_alerts)} "
        f"| SRR: {len(subject_rights_requests)} | CommCompliance: {len(comm_compliance_policies)} "
        f"| InfoBarriers: {len(info_barrier_policies)} "
        f"| Scopes: {len(protection_scopes)} | Secure Score: {len(secure_scores)} "
        f"| Improvement Actions: {len(improvement_actions)} "
        f"| UserContent: {len(user_content_policies)}"
    )

    # Build payload
    payload = CompliancePayload(
        tenant_id=settings.TENANT_ID,
        agency_id=settings.AGENCY_ID,
        department=settings.DEPARTMENT,
        display_name=settings.DISPLAY_NAME or settings.AGENCY_ID,
        timestamp=CompliancePayload.now_iso(),
        ediscovery_cases=ediscovery_cases,
        sensitivity_labels=sensitivity_labels,
        retention_labels=retention_labels,
        retention_events=retention_events,
        audit_records=audit_records,
        dlp_alerts=dlp_alerts,
        irm_alerts=irm_alerts,
        subject_rights_requests=subject_rights_requests,
        comm_compliance_policies=comm_compliance_policies,
        info_barrier_policies=info_barrier_policies,
        protection_scopes=protection_scopes,
        secure_scores=secure_scores,
        improvement_actions=improvement_actions,
        user_content_policies=user_content_policies,
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
        track_event(
            settings.APPINSIGHTS_CONNECTION_STRING,
            "CollectorRun",
            {
                "tenant_id": settings.TENANT_ID,
                "agency_id": settings.AGENCY_ID,
                "status": "success",
                "duplicate": result.get("duplicate", False),
                "ediscovery_cases": len(ediscovery_cases),
                "sensitivity_labels": len(sensitivity_labels),
                "dlp_alerts": len(dlp_alerts),
                "audit_records": len(audit_records),
            },
        )
    except Exception as e:
        click.echo(f"Submission failed: {e}", err=True)
        track_event(
            settings.APPINSIGHTS_CONNECTION_STRING,
            "CollectorRun",
            {
                "tenant_id": settings.TENANT_ID,
                "agency_id": settings.AGENCY_ID,
                "status": "submit_failed",
                "error": str(e),
            },
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

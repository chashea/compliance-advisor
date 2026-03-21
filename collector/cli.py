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
    get_compliance_assessments,
    get_dlp_alerts,
    get_dlp_policies,
    get_ediscovery_cases,
    get_improvement_actions,
    get_info_barrier_policies,
    get_irm_alerts,
    get_irm_policies,
    get_protection_scopes,
    get_purview_incidents,
    get_retention_event_types,
    get_retention_events,
    get_secure_scores,
    get_sensitive_info_types,
    get_sensitivity_labels,
    get_threat_assessment_requests,
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
    "--actions-service",
    envvar="ACTIONS_SERVICE",
    multiple=True,
    default=None,
    help="Filter improvement actions by product/service (repeatable). Uses Purview defaults if omitted.",
)
def main(
    tenant_id: str,
    agency_id: str,
    department: str,
    display_name: str,
    dry_run: bool,
    verbose: bool,
    actions_service: str | None,
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

    click.echo("  Retention Events...")
    retention_events = get_retention_events(token)

    click.echo("  Retention Event Types...")
    retention_event_types = get_retention_event_types(token)

    click.echo("  Audit Log Records...")
    audit_records = get_audit_log_records(token, days=settings.AUDIT_LOG_DAYS)

    click.echo("  DLP Alerts...")
    dlp_alerts = get_dlp_alerts(token)

    click.echo("  IRM Alerts...")
    irm_alerts = get_irm_alerts(token)

    click.echo("  Purview Incidents...")
    purview_incidents = get_purview_incidents(token, [*dlp_alerts, *irm_alerts])



    click.echo("  Information Barrier Policies...")
    info_barrier_policies = get_info_barrier_policies(token)

    click.echo("  Protection Scopes...")
    protection_scopes = get_protection_scopes(token)

    click.echo("  Secure Score...")
    secure_scores = get_secure_scores(token)

    click.echo("  Improvement Actions...")
    improvement_actions = get_improvement_actions(token, services=set(actions_service) if actions_service else None)

    click.echo("  User Content Policies...")
    user_content_policies = get_user_content_policies(token)

    click.echo("  DLP Policies...")
    dlp_policies = get_dlp_policies(token)

    click.echo("  IRM Policies...")
    irm_policies = get_irm_policies(token)

    click.echo("  Sensitive Info Types...")
    sensitive_info_types = get_sensitive_info_types(token)

    click.echo("  Compliance Assessments...")
    compliance_assessments = get_compliance_assessments(token)

    click.echo("  Threat Assessment Requests...")
    threat_assessment_requests = get_threat_assessment_requests(token)

    click.echo(
        f"\neDiscovery: {len(ediscovery_cases)} | Labels: {len(sensitivity_labels)} "
        f"| Retention Events: {len(retention_events)} "
        f"| Audit: {len(audit_records)} | DLP: {len(dlp_alerts)} | IRM: {len(irm_alerts)} "
        f"| InfoBarriers: {len(info_barrier_policies)} "
        f"| Scopes: {len(protection_scopes)} | Secure Score: {len(secure_scores)} "
        f"| Improvement Actions: {len(improvement_actions)} "
        f"| UserContent: {len(user_content_policies)} "
        f"| DLP Policies: {len(dlp_policies)} | IRM Policies: {len(irm_policies)} "
        f"| SIT: {len(sensitive_info_types)} | Assessments: {len(compliance_assessments)}"
        f" | Threats: {len(threat_assessment_requests)} | Incidents: {len(purview_incidents)}"
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
        retention_events=retention_events,
        retention_event_types=retention_event_types,
        audit_records=audit_records,
        dlp_alerts=dlp_alerts,
        irm_alerts=irm_alerts,
        info_barrier_policies=info_barrier_policies,
        protection_scopes=protection_scopes,
        secure_scores=secure_scores,
        improvement_actions=improvement_actions,
        user_content_policies=user_content_policies,
        dlp_policies=dlp_policies,
        irm_policies=irm_policies,
        sensitive_info_types=sensitive_info_types,
        compliance_assessments=compliance_assessments,
        threat_assessment_requests=threat_assessment_requests,
        purview_incidents=purview_incidents,
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

"""
Pre-built KQL query templates for common Purview threat hunting scenarios.

Each template serves two purposes:
1. Direct invocation via `purview-hunt --template <name>`
2. Few-shot examples in the NL→KQL system prompt
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HuntTemplate:
    name: str
    description: str
    table: str
    kql: str


TEMPLATES: list[HuntTemplate] = [
    HuntTemplate(
        name="label-downgrade",
        description="Users who downgraded sensitivity labels",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where ActionType == 'SensitivityLabelDowngraded'\n"
            "| project Timestamp, AccountUpn, ObjectName, SensitivityLabelId, PreviousSensitivityLabelId\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="label-removal",
        description="Users who removed sensitivity labels",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where ActionType == 'SensitivityLabelRemoved'\n"
            "| project Timestamp, AccountUpn, ObjectName, PreviousSensitivityLabelId\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="usb-exfil",
        description="Files copied to removable media (USB drives)",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where ActionType == 'FileCopiedToRemovableMedia'\n"
            "| project Timestamp, AccountUpn, DeviceName, ObjectName, SensitivityLabelId\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="cloud-upload",
        description="Files uploaded to cloud storage",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where ActionType == 'FileUploadedToCloud'\n"
            "| project Timestamp, AccountUpn, DeviceName, ObjectName, SensitivityLabelId, DestinationLocationType\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="print-sensitive",
        description="Printing of files with sensitivity labels",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where ActionType == 'FilePrinted'\n"
            "| where isnotempty(SensitivityLabelId)\n"
            "| project Timestamp, AccountUpn, DeviceName, ObjectName, SensitivityLabelId\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="dlp-violations",
        description="DLP policy violations grouped by enforcement mode",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where isnotempty(DlpPolicyMatchInfo)\n"
            "| project Timestamp, AccountUpn, ObjectName, ActionType, DlpPolicyMatchInfo, DlpPolicyEnforcementMode\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="irm-risky-users",
        description="Users with Insider Risk Management policy matches",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where isnotempty(IrmPolicyMatchInfo)\n"
            "| summarize EventCount = count(), Actions = make_set(ActionType) by AccountUpn\n"
            "| order by EventCount desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="external-sharing",
        description="Files shared with external users via SharePoint/OneDrive",
        table="CloudAppEvents",
        kql=(
            "CloudAppEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where Application in ('Microsoft SharePoint Online', 'Microsoft OneDrive for Business')\n"
            "| where ActionType has 'Sharing'\n"
            "| where isnotempty(ObjectName)\n"
            "| project Timestamp, AccountDisplayName, ActionType, ObjectName, IPAddress, CountryCode\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="admin-activity",
        description="Admin operations in cloud applications",
        table="CloudAppEvents",
        kql=(
            "CloudAppEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where IsAdminOperation == true\n"
            "| project Timestamp, AccountDisplayName, ActionType, Application, ObjectName, IPAddress\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="purview-alerts",
        description="Alerts sourced from Microsoft Purview services",
        table="AlertInfo",
        kql=(
            "AlertInfo\n"
            "| where Timestamp > ago({days}d)\n"
            "| where ServiceSource in ('Microsoft Data Loss Prevention', "
            "'Microsoft Insider Risk Management')\n"
            "| project Timestamp, AlertId, Title, Severity, ServiceSource, Category\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="high-severity",
        description="High and medium severity security alerts",
        table="AlertInfo",
        kql=(
            "AlertInfo\n"
            "| where Timestamp > ago({days}d)\n"
            "| where Severity in ('High', 'Medium')\n"
            "| project Timestamp, AlertId, Title, Severity, ServiceSource, Category\n"
            "| order by Severity asc, Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="alert-by-user",
        description="Alerts grouped by impacted user account",
        table="AlertEvidence",
        kql=(
            "AlertEvidence\n"
            "| where Timestamp > ago({days}d)\n"
            "| where EntityType == 'User'\n"
            "| summarize AlertCount = dcount(AlertId), Alerts = make_set(AlertId) by AccountUpn\n"
            "| order by AlertCount desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="email-dlp",
        description="DLP events on email messages",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where ObjectType == 'Email' or Application has 'Exchange' or Application has 'Outlook'\n"
            "| where isnotempty(DlpPolicyMatchInfo)\n"
            "| project Timestamp, AccountUpn, ObjectName, DlpPolicyMatchInfo, DlpPolicyEnforcementMode\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
    HuntTemplate(
        name="comm-compliance",
        description="Communication Compliance policy matches",
        table="DataSecurityEvents",
        kql=(
            "DataSecurityEvents\n"
            "| where Timestamp > ago({days}d)\n"
            "| where isnotempty(CcPolicyMatchInfo)\n"
            "| project Timestamp, AccountUpn, ObjectName, ObjectType, CcPolicyMatchInfo\n"
            "| order by Timestamp desc\n"
            "| limit {limit}"
        ),
    ),
]

TEMPLATES_BY_NAME: dict[str, HuntTemplate] = {t.name: t for t in TEMPLATES}


def get_template(name: str) -> HuntTemplate | None:
    return TEMPLATES_BY_NAME.get(name)


def render_template(template: HuntTemplate, days: int = 30, limit: int = 50) -> str:
    return template.kql.format(days=days, limit=limit)


def list_templates() -> list[HuntTemplate]:
    return list(TEMPLATES)


def build_examples_prompt() -> str:
    """Build few-shot examples from templates for the NL→KQL system prompt."""
    parts: list[str] = ["### Example Queries\n"]
    for t in TEMPLATES[:6]:
        parts.append(f"Question: {t.description}")
        parts.append(f"KQL:\n{render_template(t)}\n")
    return "\n".join(parts)

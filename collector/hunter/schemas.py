"""
Defender XDR Advanced Hunting table schemas for Purview-related tables.

Used to build the system prompt for NL→KQL translation.
Combined ~80 columns across 4 tables ≈ 2,000 tokens — fits in system prompt (no RAG needed).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str


# ---------------------------------------------------------------------------
# DataSecurityEvents (Preview) — Purview policy violations
# ---------------------------------------------------------------------------
DATA_SECURITY_EVENTS = {
    "name": "DataSecurityEvents",
    "description": (
        "User activities violating Microsoft Purview policies including DLP, "
        "Insider Risk Management, sensitivity labels, and Communication Compliance. "
        "Requires IRM opt-in to Defender XDR to populate."
    ),
    "columns": [
        Column("Timestamp", "datetime", "When the event was recorded"),
        Column("ActionType", "string", "Activity type that triggered the event"),
        Column("Application", "string", "Application that performed the action"),
        Column("AccountUpn", "string", "User principal name of the account"),
        Column("AccountObjectId", "string", "Entra ID object ID of the account"),
        Column("DeviceName", "string", "Device FQDN"),
        Column("DeviceId", "string", "Device unique identifier"),
        Column("ObjectName", "string", "Name of the file or object involved"),
        Column("ObjectType", "string", "Type of object (e.g., File, Email)"),
        Column("SourceLocationType", "int", "Source location type enum"),
        Column("DestinationLocationType", "int", "Destination location type enum"),
        Column("SensitivityLabelId", "string", "Current sensitivity label GUID"),
        Column("PreviousSensitivityLabelId", "string", "Previous sensitivity label GUID (for label changes)"),
        Column("SensitiveInfoTypeInfo", "dynamic", "JSON array of detected sensitive info types"),
        Column("DlpPolicyMatchInfo", "dynamic", "JSON array of matched DLP policies"),
        Column("DlpPolicyRuleMatchInfo", "dynamic", "JSON array of matched DLP rules"),
        Column("DlpPolicyEnforcementMode", "int", "DLP enforcement mode enum"),
        Column("IrmPolicyMatchInfo", "dynamic", "JSON array of matched IRM policies"),
        Column("IrmActionCategory", "string", "IRM activity category"),
        Column("CcPolicyMatchInfo", "dynamic", "JSON array of Communication Compliance policy matches"),
        Column("SharepointSiteId", "string", "SharePoint site GUID"),
        Column("SharepointSiteUrl", "string", "SharePoint site URL"),
        Column("EvidenceInfo", "dynamic", "Additional evidence details (JSON)"),
        Column("AdditionalFields", "dynamic", "Additional event properties (JSON)"),
    ],
}

DATA_SECURITY_EVENTS_ACTION_TYPES = [
    "SensitivityLabelApplied",
    "SensitivityLabelChanged",
    "SensitivityLabelDowngraded",
    "SensitivityLabelRemoved",
    "SensitivityLabelUpgraded",
    "FileUploadedToCloud",
    "FileCopiedToRemovableMedia",
    "FileCopiedToNetworkShare",
    "FileCopiedToClipboard",
    "FilePrinted",
    "FileAccessedByUnallowedApp",
    "FileCreated",
    "FileModified",
    "FileDeleted",
    "FileRenamed",
    "FileCopied",
    "FileMoved",
    "FileDownloaded",
    "BrowseToUrl",
    "PasteToClipboard",
]

DATA_SECURITY_EVENTS_ENUMS = {
    "DlpPolicyEnforcementMode": {
        0: "None",
        1: "Audit",
        2: "Warn",
        3: "WarnAndBypass",
        4: "Block",
        5: "Allow",
    },
    "SourceLocationType": {
        0: "Unknown",
        1: "Local",
        2: "Remote",
        3: "Removable",
        4: "Cloud",
        5: "FileShare",
    },
    "DestinationLocationType": {
        0: "Unknown",
        1: "Local",
        2: "Remote",
        3: "Removable",
        4: "Cloud",
        5: "FileShare",
    },
}

# ---------------------------------------------------------------------------
# CloudAppEvents — Multi-workload audit logs
# ---------------------------------------------------------------------------
CLOUD_APP_EVENTS = {
    "name": "CloudAppEvents",
    "description": (
        "Audit logs across SharePoint, OneDrive, Exchange, Teams, and Devices. "
        "Contains Microsoft Purview activity data including file operations, sharing, "
        "and admin actions."
    ),
    "columns": [
        Column("Timestamp", "datetime", "When the event was recorded"),
        Column("ActionType", "string", "Type of activity"),
        Column("Application", "string", "Application that performed the action"),
        Column("AccountId", "string", "Account identifier"),
        Column("AccountType", "string", "Type of account (User, Admin, System)"),
        Column("AccountDisplayName", "string", "Display name of the account"),
        Column("AccountObjectId", "string", "Entra ID object ID"),
        Column("IPAddress", "string", "IP address of the client"),
        Column("IsAdminOperation", "bool", "Whether this was an admin operation"),
        Column("DeviceType", "string", "Type of device"),
        Column("OSPlatform", "string", "Operating system platform"),
        Column("CountryCode", "string", "Two-letter country code"),
        Column("City", "string", "City from IP geolocation"),
        Column("ObjectName", "string", "Name of the object the action was applied to"),
        Column("ObjectType", "string", "Type of object"),
        Column("ObjectId", "string", "Unique identifier of the object"),
        Column("ActivityType", "string", "Broader activity classification"),
        Column("ActivityObjects", "dynamic", "JSON list of objects involved"),
        Column("RawEventData", "dynamic", "Full event data from source (JSON)"),
        Column("AdditionalFields", "dynamic", "Additional event properties (JSON)"),
    ],
}

# ---------------------------------------------------------------------------
# AlertInfo — Security alerts from Defender solutions
# ---------------------------------------------------------------------------
ALERT_INFO = {
    "name": "AlertInfo",
    "description": (
        "Security alerts from Microsoft Defender solutions including alerts "
        "sourced from Microsoft Purview (DLP, IRM). Join with AlertEvidence "
        "on AlertId for entity details."
    ),
    "columns": [
        Column("Timestamp", "datetime", "When the alert was generated"),
        Column("AlertId", "string", "Unique alert identifier"),
        Column("Title", "string", "Alert title"),
        Column("Category", "string", "Threat category (e.g., DataLossPrevention)"),
        Column("Severity", "string", "Alert severity (Informational, Low, Medium, High)"),
        Column("ServiceSource", "string", "Source service (e.g., Microsoft Data Loss Prevention)"),
        Column("DetectionSource", "string", "Detection technology"),
        Column("AttackTechniques", "string", "MITRE ATT&CK techniques"),
    ],
}

ALERT_INFO_SERVICE_SOURCES = [
    "Microsoft Data Loss Prevention",
    "Microsoft Insider Risk Management",
    "Microsoft Defender for Cloud Apps",
    "Microsoft Defender for Office 365",
    "Microsoft Defender for Endpoint",
    "Microsoft Defender for Identity",
]

# ---------------------------------------------------------------------------
# AlertEvidence — Entities associated with alerts
# ---------------------------------------------------------------------------
ALERT_EVIDENCE = {
    "name": "AlertEvidence",
    "description": (
        "Entities (users, files, IPs, devices) associated with security alerts. "
        "Join with AlertInfo on AlertId for alert metadata."
    ),
    "columns": [
        Column("Timestamp", "datetime", "When the evidence was recorded"),
        Column("AlertId", "string", "Alert identifier (join key to AlertInfo)"),
        Column("EntityType", "string", "Type of entity (User, File, Ip, Mailbox, Process, etc.)"),
        Column("EvidenceRole", "string", "Role in alert (Impacted, Related, Source)"),
        Column("EvidenceDirection", "string", "Direction (Inbound, Outbound)"),
        Column("AccountUpn", "string", "User principal name"),
        Column("AccountObjectId", "string", "Entra ID object ID"),
        Column("FileName", "string", "File name"),
        Column("FolderPath", "string", "Folder path"),
        Column("SHA256", "string", "SHA-256 hash of the file"),
        Column("RemoteIP", "string", "Remote IP address"),
        Column("RemoteUrl", "string", "Remote URL"),
        Column("DeviceName", "string", "Device name"),
        Column("DeviceId", "string", "Device identifier"),
        Column("AdditionalFields", "dynamic", "Additional evidence properties (JSON)"),
    ],
}

# ---------------------------------------------------------------------------
# All tables for prompt building
# ---------------------------------------------------------------------------
ALL_TABLES = [DATA_SECURITY_EVENTS, CLOUD_APP_EVENTS, ALERT_INFO, ALERT_EVIDENCE]


def build_schema_prompt() -> str:
    """Build the full schema context string for the NL→KQL system prompt."""
    parts: list[str] = []

    for table in ALL_TABLES:
        parts.append(f"### {table['name']}")
        parts.append(f"{table['description']}\n")
        parts.append("| Column | Type | Description |")
        parts.append("|--------|------|-------------|")
        for col in table["columns"]:
            parts.append(f"| {col.name} | {col.type} | {col.description} |")
        parts.append("")

    # ActionType values for DataSecurityEvents
    parts.append("### DataSecurityEvents ActionType Values")
    parts.append(", ".join(f"`{a}`" for a in DATA_SECURITY_EVENTS_ACTION_TYPES))
    parts.append("")

    # Enum values
    parts.append("### Enum Reference")
    for enum_name, values in DATA_SECURITY_EVENTS_ENUMS.items():
        mapping = ", ".join(f"{k}={v}" for k, v in values.items())
        parts.append(f"- **{enum_name}**: {mapping}")
    parts.append("")

    # AlertInfo ServiceSource values
    parts.append("### AlertInfo ServiceSource Values")
    parts.append(", ".join(f"`{s}`" for s in ALERT_INFO_SERVICE_SOURCES))

    return "\n".join(parts)

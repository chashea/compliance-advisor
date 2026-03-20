import type {
  StatusResponse,
  OverviewResponse,
  Tenant,
  EDiscoveryResponse,
  EDiscoveryCase,
  LabelsResponse,
  SensitivityLabel,
  RetentionLabel,
  RetentionEvent,
  AuditResponse,
  AuditRecord,
  DLPResponse,
  DLPAlert,
  IRMResponse,
  IRMAlert,
  SubjectRightsResponse,
  SubjectRightsRequest,
  CommComplianceResponse,
  CommCompliancePolicy,
  TrendResponse,
  TrendPoint,
  ActionsResponse,
  ImprovementAction,
  DLPPoliciesResponse,
  DLPPolicy,
  IRMPoliciesResponse,
  IRMPolicy,
  SensitiveInfoTypesResponse,
  SensitiveInfoType,
  AssessmentsResponse,
  Assessment,
} from "../types";

// --- Tenants ---

const TENANTS: Tenant[] = [
  { tenant_id: "t-contoso", display_name: "Contoso Ltd", department: "Legal" },
  { tenant_id: "t-fabrikam", display_name: "Fabrikam Inc", department: "Legal" },
  { tenant_id: "t-northwind", display_name: "Northwind Traders", department: "Finance" },
];

const DEPT_TENANTS: Record<string, string[]> = {
  Legal: ["Contoso Ltd", "Fabrikam Inc"],
  Finance: ["Northwind Traders"],
};

function filterByDept<T extends { tenant_name: string }>(items: T[], department?: string): T[] {
  if (!department) return items;
  const names = DEPT_TENANTS[department] ?? [];
  return items.filter((i) => names.includes(i.tenant_name));
}

// --- Helpers ---

function daysAgo(n: number): string {
  const d = new Date(2026, 2, 14); // 2026-03-14
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

// --- Static data ---

const ediscoveryCases: EDiscoveryCase[] = [
  { case_id: "ec-1", display_name: "Merger Review 2026", status: "Active", created: "2026-01-10", closed: null, external_id: "EXT-001", custodian_count: 4, tenant_name: "Contoso Ltd" },
  { case_id: "ec-2", display_name: "IP Dispute — Widget Patent", status: "Active", created: "2025-11-03", closed: null, external_id: "EXT-002", custodian_count: 2, tenant_name: "Contoso Ltd" },
  { case_id: "ec-3", display_name: "Regulatory Inquiry Q4", status: "Closed", created: "2025-08-15", closed: "2025-12-20", external_id: "EXT-003", custodian_count: 3, tenant_name: "Fabrikam Inc" },
  { case_id: "ec-4", display_name: "Internal Investigation — HR", status: "Active", created: "2026-02-01", closed: null, external_id: "EXT-004", custodian_count: 1, tenant_name: "Fabrikam Inc" },
  { case_id: "ec-5", display_name: "Vendor Contract Dispute", status: "Closed", created: "2025-06-22", closed: "2025-10-10", external_id: "EXT-005", custodian_count: 5, tenant_name: "Northwind Traders" },
  { case_id: "ec-6", display_name: "SOX Audit Hold", status: "Active", created: "2026-03-01", closed: null, external_id: "EXT-006", custodian_count: 2, tenant_name: "Northwind Traders" },
];

const sensitivityLabels: SensitivityLabel[] = [
  { label_id: "sl-1", name: "Confidential", description: "Internal confidential data", color: "#d32f2f", is_active: true, parent_id: "", priority: 1, tooltip: "Restricted access", tenant_name: "Contoso Ltd" },
  { label_id: "sl-2", name: "Public", description: "Safe for external sharing", color: "#388e3c", is_active: true, parent_id: "", priority: 3, tooltip: "No restrictions", tenant_name: "Contoso Ltd" },
  { label_id: "sl-3", name: "Highly Confidential", description: "Executive-only", color: "#b71c1c", is_active: true, parent_id: "", priority: 0, tooltip: "Top secret", tenant_name: "Fabrikam Inc" },
  { label_id: "sl-4", name: "Internal", description: "General internal use", color: "#1976d2", is_active: true, parent_id: "", priority: 2, tooltip: "Internal only", tenant_name: "Northwind Traders" },
];

const retentionLabels: RetentionLabel[] = [
  { label_id: "rl-1", display_name: "7-Year Financial", retention_duration: "P2555D", retention_trigger: "DateCreated", action_after_retention: "Delete", is_in_use: true, status: "Active", tenant_name: "Contoso Ltd" },
  { label_id: "rl-2", display_name: "3-Year HR Records", retention_duration: "P1095D", retention_trigger: "DateCreated", action_after_retention: "Delete", is_in_use: true, status: "Active", tenant_name: "Fabrikam Inc" },
  { label_id: "rl-3", display_name: "1-Year Transient", retention_duration: "P365D", retention_trigger: "DateModified", action_after_retention: "Delete", is_in_use: false, status: "Active", tenant_name: "Northwind Traders" },
];

const retentionEvents: RetentionEvent[] = [
  { event_id: "re-1", display_name: "Employee Departure — J. Smith", event_type: "EmployeeTermination", created: "2026-02-15", event_status: "Published", tenant_name: "Contoso Ltd" },
  { event_id: "re-2", display_name: "Contract Expiry — Vendor A", event_type: "ContractExpiration", created: "2026-01-20", event_status: "Published", tenant_name: "Northwind Traders" },
];

const auditRecords: AuditRecord[] = [
  { record_id: "ar-1", record_type: "SharePoint", operation: "FileAccessed", service: "SharePoint", user_id: "user1@contoso.com", created: daysAgo(1), tenant_name: "Contoso Ltd" },
  { record_id: "ar-2", record_type: "AzureAD", operation: "UserLoggedIn", service: "Azure AD", user_id: "user2@contoso.com", created: daysAgo(1), tenant_name: "Contoso Ltd" },
  { record_id: "ar-3", record_type: "Exchange", operation: "MailItemsAccessed", service: "Exchange", user_id: "admin@fabrikam.com", created: daysAgo(2), tenant_name: "Fabrikam Inc" },
  { record_id: "ar-4", record_type: "SharePoint", operation: "FileModified", service: "SharePoint", user_id: "user1@northwind.com", created: daysAgo(0), tenant_name: "Northwind Traders" },
  { record_id: "ar-5", record_type: "AzureAD", operation: "Add member to role", service: "Azure AD", user_id: "admin@northwind.com", created: daysAgo(3), tenant_name: "Northwind Traders" },
];

const dlpAlerts: DLPAlert[] = [
  { alert_id: "dlp-1", title: "Credit card numbers shared externally", severity: "High", status: "Active", category: "DataLoss", policy_name: "PCI-DSS Protection", created: daysAgo(2), resolved: null, tenant_name: "Contoso Ltd" },
  { alert_id: "dlp-2", title: "SSN detected in email attachment", severity: "High", status: "Resolved", category: "DataLoss", policy_name: "PII Protection", created: daysAgo(10), resolved: daysAgo(8), tenant_name: "Contoso Ltd" },
  { alert_id: "dlp-3", title: "Bulk file download to USB", severity: "Medium", status: "Active", category: "DataExfiltration", policy_name: "Endpoint DLP", created: daysAgo(1), resolved: null, tenant_name: "Fabrikam Inc" },
  { alert_id: "dlp-4", title: "Confidential label shared via Teams", severity: "Low", status: "Active", category: "DataLoss", policy_name: "Teams DLP", created: daysAgo(5), resolved: null, tenant_name: "Northwind Traders" },
  { alert_id: "dlp-5", title: "Financial report uploaded to personal OneDrive", severity: "Medium", status: "Resolved", category: "DataExfiltration", policy_name: "PCI-DSS Protection", created: daysAgo(15), resolved: daysAgo(12), tenant_name: "Northwind Traders" },
];

const irmAlerts: IRMAlert[] = [
  { alert_id: "irm-1", title: "Unusual volume of file deletions", severity: "High", status: "Active", category: "InsiderRisk", policy_name: "Data Theft — Departing Employee", created: daysAgo(3), resolved: null, tenant_name: "Contoso Ltd" },
  { alert_id: "irm-2", title: "Sequence of exfiltration activities", severity: "Medium", status: "Active", category: "InsiderRisk", policy_name: "General Data Leaks", created: daysAgo(7), resolved: null, tenant_name: "Fabrikam Inc" },
  { alert_id: "irm-3", title: "Anomalous access pattern detected", severity: "Low", status: "Resolved", category: "InsiderRisk", policy_name: "Security Policy Violations", created: daysAgo(20), resolved: daysAgo(14), tenant_name: "Northwind Traders" },
];

const subjectRightsRequests: SubjectRightsRequest[] = [
  { request_id: "sr-1", display_name: "GDPR Erasure — J. Doe", request_type: "Delete", status: "Active", created: "2026-02-20", closed: null, data_subject_type: "Customer", tenant_name: "Contoso Ltd" },
  { request_id: "sr-2", display_name: "DSAR Export — A. Patel", request_type: "Export", status: "Closed", created: "2026-01-05", closed: "2026-01-25", data_subject_type: "Employee", tenant_name: "Fabrikam Inc" },
  { request_id: "sr-3", display_name: "Access Request — M. Chen", request_type: "Access", status: "Active", created: "2026-03-05", closed: null, data_subject_type: "Customer", tenant_name: "Northwind Traders" },
];

const commCompliancePolicies: CommCompliancePolicy[] = [
  { policy_id: "cc-1", display_name: "Offensive Language Detection", status: "Active", policy_type: "OffensiveLanguage", review_pending_count: 12, tenant_name: "Contoso Ltd" },
  { policy_id: "cc-2", display_name: "Regulatory Compliance — FINRA", status: "Active", policy_type: "RegulatoryCompliance", review_pending_count: 3, tenant_name: "Fabrikam Inc" },
  { policy_id: "cc-3", display_name: "Conflict of Interest", status: "Inactive", policy_type: "CustomPolicy", review_pending_count: 0, tenant_name: "Northwind Traders" },
];

const improvementActions: ImprovementAction[] = [
  { control_id: "ia-1", title: "Turn on audit data recording", control_category: "Data", max_score: 10, current_score: 10, implementation_cost: "Low", user_impact: "Low", tier: "Tier 1", service: "Microsoft 365", threats: "Data exfiltration", remediation: "Enable unified audit logging in the compliance portal.", state: "Completed", rank: 1, tenant_name: "Contoso Ltd" },
  { control_id: "ia-2", title: "Enable DLP policies for sensitive info", control_category: "Data", max_score: 10, current_score: 5, implementation_cost: "Moderate", user_impact: "Moderate", tier: "Tier 2", service: "Microsoft 365", threats: "Data leakage", remediation: "Create DLP policies targeting PII and PCI data types.", state: "InProgress", rank: 2, tenant_name: "Contoso Ltd" },
  { control_id: "ia-3", title: "Apply sensitivity labels to content", control_category: "Data", max_score: 10, current_score: 0, implementation_cost: "High", user_impact: "Moderate", tier: "Tier 2", service: "Microsoft 365", threats: "Unauthorized access", remediation: "Deploy auto-labeling policies across SharePoint and Exchange.", state: "NotStarted", rank: 3, tenant_name: "Fabrikam Inc" },
  { control_id: "ia-4", title: "Enable retention policies for Teams", control_category: "Data", max_score: 10, current_score: 7, implementation_cost: "Low", user_impact: "Low", tier: "Tier 1", service: "Microsoft Teams", threats: "Data loss", remediation: "Configure retention policies for Teams chats and channels.", state: "InProgress", rank: 4, tenant_name: "Fabrikam Inc" },
  { control_id: "ia-5", title: "Configure insider risk management", control_category: "Data", max_score: 10, current_score: 10, implementation_cost: "Moderate", user_impact: "Low", tier: "Tier 3", service: "Microsoft 365", threats: "Insider threat", remediation: "Enable departing employee and data theft policy templates.", state: "Completed", rank: 5, tenant_name: "Northwind Traders" },
  { control_id: "ia-6", title: "Set up communication compliance", control_category: "Data", max_score: 10, current_score: 0, implementation_cost: "Moderate", user_impact: "Moderate", tier: "Tier 3", service: "Microsoft 365", threats: "Regulatory violation", remediation: "Create policies for offensive language and regulatory compliance.", state: "NotStarted", rank: 6, tenant_name: "Northwind Traders" },
];

const dlpPolicies: DLPPolicy[] = [
  { policy_id: "dp-1", display_name: "PCI-DSS Protection", status: "Enabled", policy_type: "DLP", rules_count: 5, created: "2025-06-15", modified: daysAgo(10), mode: "Enforce", tenant_name: "Contoso Ltd" },
  { policy_id: "dp-2", display_name: "PII Protection", status: "Enabled", policy_type: "DLP", rules_count: 3, created: "2025-08-01", modified: daysAgo(5), mode: "Enforce", tenant_name: "Contoso Ltd" },
  { policy_id: "dp-3", display_name: "Endpoint DLP", status: "TestWithNotifications", policy_type: "DLP", rules_count: 2, created: "2026-01-10", modified: daysAgo(2), mode: "TestWithNotifications", tenant_name: "Fabrikam Inc" },
  { policy_id: "dp-4", display_name: "Teams DLP", status: "Enabled", policy_type: "DLP", rules_count: 4, created: "2025-09-20", modified: daysAgo(15), mode: "Enforce", tenant_name: "Northwind Traders" },
];

const irmPolicies: IRMPolicy[] = [
  { policy_id: "ip-1", display_name: "Data Theft — Departing Employee", status: "Active", policy_type: "DataTheft", created: "2025-07-01", triggers: "HR connector, resignation event", tenant_name: "Contoso Ltd" },
  { policy_id: "ip-2", display_name: "General Data Leaks", status: "Active", policy_type: "DataLeaks", created: "2025-09-15", triggers: "DLP policy match", tenant_name: "Fabrikam Inc" },
  { policy_id: "ip-3", display_name: "Security Policy Violations", status: "Active", policy_type: "SecurityPolicyViolation", created: "2026-01-05", triggers: "Defender alert", tenant_name: "Northwind Traders" },
  { policy_id: "ip-4", display_name: "Patient Data Misuse", status: "Inactive", policy_type: "DataTheft", created: "2025-11-20", triggers: "Sensitivity label match", tenant_name: "Contoso Ltd" },
];

const sensitiveInfoTypes: SensitiveInfoType[] = [
  { type_id: "sit-1", name: "U.S. Social Security Number (SSN)", description: "Detects US SSNs", is_custom: false, category: "PII", scope: "Tenant", state: "Enabled", tenant_name: "Contoso Ltd" },
  { type_id: "sit-2", name: "Credit Card Number", description: "Detects major credit card formats", is_custom: false, category: "Financial", scope: "Tenant", state: "Enabled", tenant_name: "Contoso Ltd" },
  { type_id: "sit-3", name: "Contoso Employee ID", description: "Custom pattern for Contoso employee IDs", is_custom: true, category: "HR", scope: "Tenant", state: "Enabled", tenant_name: "Contoso Ltd" },
  { type_id: "sit-4", name: "IBAN", description: "International Bank Account Number", is_custom: false, category: "Financial", scope: "Tenant", state: "Enabled", tenant_name: "Fabrikam Inc" },
  { type_id: "sit-5", name: "Northwind Case Number", description: "Custom case tracking number", is_custom: true, category: "Legal", scope: "Tenant", state: "Enabled", tenant_name: "Northwind Traders" },
];

const complianceAssessments: Assessment[] = [
  { assessment_id: "ca-1", display_name: "NIST 800-53 Assessment", status: "Active", framework: "NIST 800-53", completion_percentage: 72, created: "2025-10-01", category: "Security", tenant_name: "Contoso Ltd" },
  { assessment_id: "ca-2", display_name: "CJIS Security Policy", status: "Active", framework: "CJIS", completion_percentage: 85, created: "2025-11-15", category: "Criminal Justice", tenant_name: "Contoso Ltd" },
  { assessment_id: "ca-3", display_name: "ISO 27001 Readiness", status: "Active", framework: "ISO 27001", completion_percentage: 60, created: "2026-01-20", category: "Security", tenant_name: "Fabrikam Inc" },
  { assessment_id: "ca-4", display_name: "NIST 800-53 Assessment", status: "Completed", framework: "NIST 800-53", completion_percentage: 100, created: "2025-06-01", category: "Security", tenant_name: "Northwind Traders" },
  { assessment_id: "ca-5", display_name: "SOC 2 Type II", status: "Active", framework: "SOC 2", completion_percentage: 45, created: "2026-02-10", category: "Compliance", tenant_name: "Northwind Traders" },
];

// Trend: 30 days counting back from 2026-03-14
const trendData: TrendPoint[] = Array.from({ length: 30 }, (_, i) => {
  const day = 29 - i;
  return {
    snapshot_date: daysAgo(day),
    ediscovery_cases: 4 + Math.floor(i / 10),
    sensitivity_labels: 4,
    retention_labels: 3,
    dlp_alerts: 3 + (i % 3),
    audit_records: 80 + (i % 20),
    tenant_count: 3,
  };
});

const BRIEFING = `## Compliance Briefing — Demo

**Active Tenants:** 3 across 2 departments (Legal, Finance)

### Key Highlights
- **4 active eDiscovery cases** — Merger Review 2026 is the highest-priority hold
- **2 high-severity DLP alerts** require attention (credit card sharing, SSN in attachments)
- **1 high-severity insider risk alert** — unusual file deletions at Contoso
- **Secure Score: 62%** (32/52 data points achieved)
- **3 subject rights requests** — 2 active, 1 closed

### Recommendations
1. Resolve the active high-severity DLP alert (credit card numbers shared externally)
2. Investigate the insider risk alert for departing employee activity
3. Deploy auto-labeling policies to improve the sensitivity labels score
4. Close the outstanding GDPR erasure request approaching SLA`;

const ASK_ANSWER = "This is a demo environment with static data. In production, I would query your compliance database and provide a detailed, data-driven answer to your question using Azure OpenAI.";

// --- Main export ---

export function getDemoData(endpoint: string, body?: Record<string, unknown>): unknown {
  const dept = (body?.department as string) || "";

  switch (endpoint) {
    case "status":
      return { active_tenants: 3, newest_sync: "2026-03-14T08:00:00Z" } satisfies StatusResponse;

    case "overview": {
      const tenants = dept ? TENANTS.filter((t) => t.department === dept) : TENANTS;
      const cases = filterByDept(ediscoveryCases, dept || undefined);
      const dlp = filterByDept(dlpAlerts, dept || undefined);
      const sl = filterByDept(sensitivityLabels, dept || undefined);
      const rl = filterByDept(retentionLabels, dept || undefined);
      const ar = filterByDept(auditRecords, dept || undefined);
      return {
        tenants,
        ediscovery_summary: { total_cases: cases.length, active_cases: cases.filter((c) => c.status === "Active").length },
        labels_summary: { sensitivity_labels: sl.length, retention_labels: rl.length },
        dlp_summary: {
          total_dlp_alerts: dlp.length,
          high_alerts: dlp.filter((a) => a.severity === "High").length,
          medium_alerts: dlp.filter((a) => a.severity === "Medium").length,
          active_alerts: dlp.filter((a) => a.status === "Active").length,
        },
        audit_summary: { total_records: ar.length },
      } satisfies OverviewResponse;
    }

    case "ediscovery": {
      const cases = filterByDept(ediscoveryCases, dept || undefined);
      const breakdown: Record<string, number> = {};
      cases.forEach((c) => { breakdown[c.status] = (breakdown[c.status] ?? 0) + 1; });
      return {
        cases,
        status_breakdown: Object.entries(breakdown).map(([status, total]) => ({ status, total })),
      } satisfies EDiscoveryResponse;
    }

    case "labels":
      return {
        sensitivity_labels: filterByDept(sensitivityLabels, dept || undefined),
        retention_labels: filterByDept(retentionLabels, dept || undefined),
        retention_events: filterByDept(retentionEvents, dept || undefined),
      } satisfies LabelsResponse;

    case "audit": {
      const records = filterByDept(auditRecords, dept || undefined);
      const svc: Record<string, number> = {};
      const ops: Record<string, number> = {};
      records.forEach((r) => {
        svc[r.service] = (svc[r.service] ?? 0) + 1;
        ops[r.operation] = (ops[r.operation] ?? 0) + 1;
      });
      return {
        records,
        service_breakdown: Object.entries(svc).map(([service, total]) => ({ service, total })),
        operation_breakdown: Object.entries(ops).map(([operation, total]) => ({ operation, total })),
      } satisfies AuditResponse;
    }

    case "dlp": {
      const alerts = filterByDept(dlpAlerts, dept || undefined);
      const sev: Record<string, { total: number; active: number }> = {};
      const pol: Record<string, number> = {};
      alerts.forEach((a) => {
        if (!sev[a.severity]) sev[a.severity] = { total: 0, active: 0 };
        sev[a.severity].total++;
        if (a.status === "Active") sev[a.severity].active++;
        pol[a.policy_name] = (pol[a.policy_name] ?? 0) + 1;
      });
      return {
        alerts,
        severity_breakdown: Object.entries(sev).map(([severity, v]) => ({ severity, ...v })),
        policy_breakdown: Object.entries(pol).map(([policy_name, total]) => ({ policy_name, total })),
      } satisfies DLPResponse;
    }

    case "irm": {
      const alerts = filterByDept(irmAlerts, dept || undefined);
      const sev: Record<string, { total: number; active: number }> = {};
      alerts.forEach((a) => {
        if (!sev[a.severity]) sev[a.severity] = { total: 0, active: 0 };
        sev[a.severity].total++;
        if (a.status === "Active") sev[a.severity].active++;
      });
      return {
        alerts,
        severity_breakdown: Object.entries(sev).map(([severity, v]) => ({ severity, ...v })),
      } satisfies IRMResponse;
    }

    case "subject-rights": {
      const requests = filterByDept(subjectRightsRequests, dept || undefined);
      const breakdown: Record<string, number> = {};
      requests.forEach((r) => { breakdown[r.status] = (breakdown[r.status] ?? 0) + 1; });
      return {
        requests,
        status_breakdown: Object.entries(breakdown).map(([status, total]) => ({ status, total })),
      } satisfies SubjectRightsResponse;
    }

    case "comm-compliance":
      return {
        policies: filterByDept(commCompliancePolicies, dept || undefined),
      } satisfies CommComplianceResponse;

    case "trend":
      return { trend: trendData } satisfies TrendResponse;

    case "dlp-policies": {
      const policies = filterByDept(dlpPolicies, dept || undefined);
      const breakdown: Record<string, number> = {};
      policies.forEach((p) => { breakdown[p.status] = (breakdown[p.status] ?? 0) + 1; });
      return {
        policies,
        status_breakdown: Object.entries(breakdown).map(([status, total]) => ({ status, total })),
      } satisfies DLPPoliciesResponse;
    }

    case "irm-policies":
      return {
        policies: filterByDept(irmPolicies, dept || undefined),
      } satisfies IRMPoliciesResponse;

    case "sensitive-info-types": {
      const types = filterByDept(sensitiveInfoTypes, dept || undefined);
      return {
        types,
        custom_count: types.filter((t) => t.is_custom).length,
        builtin_count: types.filter((t) => !t.is_custom).length,
      } satisfies SensitiveInfoTypesResponse;
    }

    case "assessments": {
      const assessments = filterByDept(complianceAssessments, dept || undefined);
      const fwMap: Record<string, number> = {};
      assessments.forEach((a) => { fwMap[a.framework] = (fwMap[a.framework] ?? 0) + 1; });
      return {
        assessments,
        framework_breakdown: Object.entries(fwMap).map(([framework, total]) => ({ framework, total })),
      } satisfies AssessmentsResponse;
    }

    case "actions": {
      const actions = filterByDept(improvementActions, dept || undefined);
      const currentTotal = actions.reduce((s, a) => s + a.current_score, 0);
      const maxTotal = actions.reduce((s, a) => s + a.max_score, 0);
      const catMap: Record<string, { total: number; total_max_score: number }> = {};
      actions.forEach((a) => {
        if (!catMap[a.control_category]) catMap[a.control_category] = { total: 0, total_max_score: 0 };
        catMap[a.control_category].total++;
        catMap[a.control_category].total_max_score += a.max_score;
      });
      return {
        secure_score: {
          current_score: currentTotal,
          max_score: maxTotal,
          score_date: "2026-03-14",
          data_current_score: currentTotal,
          data_max_score: maxTotal,
        },
        actions,
        category_breakdown: Object.entries(catMap).map(([control_category, v]) => ({ control_category, ...v })),
      } satisfies ActionsResponse;
    }

    case "briefing":
      return { briefing: BRIEFING };

    case "ask":
      return { answer: ASK_ANSWER };

    default:
      return {};
  }
}

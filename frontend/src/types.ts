// /api/advisor/status
export interface StatusResponse {
  active_tenants: number;
  newest_sync: string | null;
}

// /api/advisor/overview
export interface Tenant {
  tenant_id: string;
  display_name: string;
  department: string;
}

export interface OverviewResponse {
  tenants: Tenant[];
  labels_summary: { sensitivity_labels: number; protected_labels: number };
  dlp_summary: { total_dlp_alerts: number; high_alerts: number; medium_alerts: number; active_alerts: number };
  audit_summary: { total_records: number };
  threat_summary: { total_requests: number; spam: number; phishing: number; malware: number };
}

export interface StatusBreakdown {
  status: string;
  total: number;
}

// /api/advisor/labels
export interface SensitivityLabel {
  label_id: string;
  name: string;
  description: string;
  color: string;
  is_active: boolean;
  parent_id: string;
  priority: number;
  tooltip: string;
  has_protection: boolean;
  applicable_to: string;
  application_mode: string;
  is_endpoint_protection_enabled: boolean;
  tenant_name: string;
}

export interface RetentionEvent {
  event_id: string;
  display_name: string;
  event_type: string;
  created: string;
  event_status: string;
  tenant_name: string;
}

export interface RetentionLabel {
  label_id: string;
  name: string;
  description: string;
  is_in_use: boolean;
  retention_duration: string;
  action_after: string;
  default_record_behavior: string;
  created: string;
  modified: string;
  tenant_name: string;
}

export interface LabelsResponse {
  sensitivity_labels: SensitivityLabel[];
  retention_labels: RetentionLabel[];
  retention_events: RetentionEvent[];
}

// /api/advisor/audit
export interface AuditRecord {
  record_id: string;
  record_type: string;
  operation: string;
  service: string;
  user_id: string;
  created: string;
  tenant_name: string;
}

export interface CountBreakdown {
  [key: string]: string | number;
  total: number;
}

export interface AuditResponse {
  records: AuditRecord[];
  service_breakdown: CountBreakdown[];
  operation_breakdown: CountBreakdown[];
}

// /api/advisor/dlp
export interface AlertEvidence {
  type: string;
  remediation_status: string;
  verdict: string;
  roles: string[];
  detailed_roles: string[];
}

export interface EvidenceSummary {
  remediation_breakdown: { status: string; count: number }[];
  verdict_breakdown: { verdict: string; count: number }[];
  evidence_type_breakdown: { type: string; count: number }[];
  total_evidence_items: number;
}

export interface ClassificationBreakdown {
  classification: string;
  count: number;
}

export interface DLPAlert {
  alert_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  policy_name: string;
  created: string;
  resolved: string | null;
  tenant_name: string;
  classification: string;
  determination: string;
  recommended_actions: string;
  incident_id: string;
  mitre_techniques: string;
  evidence: AlertEvidence[];
}

export interface SeverityBreakdown {
  severity: string;
  total: number;
  active: number;
}

export interface PolicyBreakdown {
  policy_name: string;
  total: number;
}

export interface DLPResponse {
  alerts: DLPAlert[];
  severity_breakdown: SeverityBreakdown[];
  policy_breakdown: PolicyBreakdown[];
  evidence_summary: EvidenceSummary;
  classification_breakdown: ClassificationBreakdown[];
}

// /api/advisor/irm
export interface IRMAlert {
  alert_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  policy_name: string;
  created: string;
  resolved: string | null;
  tenant_name: string;
  classification: string;
  determination: string;
  recommended_actions: string;
  incident_id: string;
  mitre_techniques: string;
  evidence: AlertEvidence[];
}

export interface IRMResponse {
  alerts: IRMAlert[];
  severity_breakdown: SeverityBreakdown[];
  evidence_summary: EvidenceSummary;
  classification_breakdown: ClassificationBreakdown[];
}

// /api/advisor/purview-incidents
export interface PurviewIncident {
  incident_id: string;
  display_name: string;
  severity: string;
  status: string;
  classification: string;
  determination: string;
  created: string;
  last_update: string;
  assigned_to: string;
  alerts_count: number;
  purview_alerts_count: number;
  tenant_name: string;
}

export interface PurviewIncidentsResponse {
  incidents: PurviewIncident[];
  severity_breakdown: SeverityBreakdown[];
  status_breakdown: StatusBreakdown[];
}

// /api/advisor/trend
export interface TrendPoint {
  snapshot_date: string;
  sensitivity_labels: number;
  dlp_alerts: number;
  audit_records: number;
  tenant_count: number;
}

export interface TrendResponse {
  trend: TrendPoint[];
}





// /api/advisor/actions
export interface SecureScore {
  current_score: number;
  max_score: number;
  score_date: string | null;
  data_current_score: number;
  data_max_score: number;
}

export interface ImprovementAction {
  control_id: string;
  title: string;
  control_category: string;
  max_score: number;
  current_score: number;
  implementation_cost: string;
  user_impact: string;
  tier: string;
  service: string;
  threats: string;
  remediation: string;
  state: string;
  rank: number;
  tenant_name: string;
}

export interface CategoryBreakdown {
  control_category: string;
  total: number;
  total_max_score: number;
}

export interface ActionsResponse {
  secure_score: SecureScore;
  actions: ImprovementAction[];
  category_breakdown: CategoryBreakdown[];
}

// /api/advisor/dlp-policies
export interface DLPPolicy {
  policy_id: string;
  display_name: string;
  status: string;
  policy_type: string;
  rules_count: number;
  created: string;
  modified: string;
  mode: string;
  tenant_name: string;
}

export interface DLPPoliciesResponse {
  policies: DLPPolicy[];
  status_breakdown: StatusBreakdown[];
}

// /api/advisor/irm-policies
export interface IRMPolicy {
  policy_id: string;
  display_name: string;
  status: string;
  policy_type: string;
  created: string;
  triggers: string;
  tenant_name: string;
}

export interface IRMPoliciesResponse {
  policies: IRMPolicy[];
}

// /api/advisor/assessments
export interface Assessment {
  assessment_id: string;
  display_name: string;
  status: string;
  framework: string;
  completion_percentage: number;
  created: string;
  category: string;
  tenant_name: string;
}

export interface FrameworkBreakdown {
  framework: string;
  total: number;
}

export interface AssessmentsResponse {
  assessments: Assessment[];
  framework_breakdown: FrameworkBreakdown[];
}

// /api/advisor/threat-assessments
export interface ThreatAssessmentRequest {
  request_id: string;
  category: string;
  content_type: string;
  status: string;
  created: string;
  result_type: string;
  result_message: string;
  tenant_name: string;
}

export interface ThreatCategoryBreakdown {
  category: string;
  total: number;
}

export interface ThreatAssessmentsResponse {
  requests: ThreatAssessmentRequest[];
  status_breakdown: StatusBreakdown[];
  category_breakdown: ThreatCategoryBreakdown[];
}

// /api/advisor/purview-insights
export interface RepeatOffender {
  owner: string;
  total_alerts: number;
  open_alerts: number;
  high_severity: number;
  avg_age_days: number;
}

export interface CoverageBreakdown {
  applicable_to: string;
  total: number;
  protected: number;
}

export interface PolicyDriftPoint {
  snapshot_date: string;
  dlp_alerts: number;
  active_incidents: number;
  policy_changes: number;
  data_score_pct: number;
  risk_spike: boolean;
  correlated_change: boolean;
  secure_score_delta: number;
}

export interface ControlEvidenceLink {
  label: string;
  url: string;
}

export interface MappedControl {
  framework: string;
  control_id: string;
  control_title: string;
  status: string;
  priority: string;
  owner: string;
  completion_percentage: number;
  evidence_links: ControlEvidenceLink[];
}

export interface OwnerLoad {
  owner: string;
  open_alerts: number;
  high_severity: number;
  active_incidents: number;
  avg_age_days: number;
}

export interface PriorityAction {
  action_type: string;
  title: string;
  owner: string;
  priority: string;
  risk_reduction_score: number;
  tenant_name: string;
  evidence_link: string;
}

export interface TenantCollectionHealth {
  tenant_id: string;
  display_name: string;
  department: string;
  last_collected_at: string | null;
  last_snapshot_date: string | null;
  last_payload_at: string | null;
  is_stale: boolean;
  completeness_pct: number;
  missing_datasets: string[];
}

export interface PurviewInsightsResponse {
  effectiveness: {
    total_alerts: number;
    resolved_alerts: number;
    active_alerts: number;
    closure_rate_pct: number;
    true_positive_rate_pct: number;
    mttr_hours: number;
    repeat_offenders: RepeatOffender[];
  };
  classification_coverage: {
    total_labels: number;
    protected_labels: number;
    coverage_pct: number;
    breakdown: CoverageBreakdown[];
  };
  policy_drift: {
    window_days: number;
    timeline: PolicyDriftPoint[];
    summary: {
      total_policy_changes: number;
      risk_spike_days: number;
      correlated_days: number;
    };
  };
  data_at_risk: {
    score: number;
    risk_level: string;
    components: {
      unresolved_high_alerts: number;
      unresolved_medium_alerts: number;
      active_incidents: number;
      unprotected_labels: number;
    };
    weighted_points: {
      high_alert_weighted: number;
      medium_alert_weighted: number;
      active_incident_weighted: number;
      unprotected_label_weighted: number;
    };
  };
  control_mapping: {
    framework_summary: {
      framework: string;
      total_assessments: number;
      avg_completion: number;
      estimated_gap_count: number;
    }[];
    controls: MappedControl[];
  };
  owner_actions: {
    owners: OwnerLoad[];
    priority_actions: PriorityAction[];
  };
  collection_health: {
    required_datasets: string[];
    newest_sync: string | null;
    stale_tenants: number;
    complete_tenants: number;
    tenant_health: TenantCollectionHealth[];
  };
}

// /api/advisor/hunt-results
export interface HuntFinding {
  id: string;
  finding_type: string;
  severity: string;
  account_upn: string | null;
  object_name: string | null;
  action_type: string | null;
  evidence: Record<string, unknown> | null;
  detected_at: string | null;
  snapshot_date: string;
  question: string | null;
  template_name: string | null;
  kql_query: string;
}

export interface HuntRun {
  id: number;
  template_name: string | null;
  question: string | null;
  result_count: number;
  run_at: string;
  ai_narrative: string | null;
}

export interface HuntResultsResponse {
  results: HuntFinding[];
  summary: {
    total: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
  recent_runs: HuntRun[];
}

// /api/advisor/briefing
export interface BriefingResponse {
  briefing: string;
}

// /api/advisor/ask
export interface AskResponse {
  answer: string;
}

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
  ediscovery_summary: { total_cases: number; active_cases: number };
  labels_summary: { sensitivity_labels: number; retention_labels: number };
  dlp_summary: { total_dlp_alerts: number; high_alerts: number; medium_alerts: number; active_alerts: number };
  audit_summary: { total_records: number };
  threat_summary: { total_requests: number; spam: number; phishing: number; malware: number };
}

// /api/advisor/ediscovery
export interface EDiscoveryCase {
  case_id: string;
  display_name: string;
  status: string;
  created: string;
  closed: string | null;
  external_id: string;
  custodian_count: number;
  tenant_name: string;
}

export interface StatusBreakdown {
  status: string;
  total: number;
}

export interface EDiscoveryResponse {
  cases: EDiscoveryCase[];
  status_breakdown: StatusBreakdown[];
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
  tenant_name: string;
}

export interface RetentionLabel {
  label_id: string;
  display_name: string;
  retention_duration: string;
  retention_trigger: string;
  action_after_retention: string;
  is_in_use: boolean;
  status: string;
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
}

export interface IRMResponse {
  alerts: IRMAlert[];
  severity_breakdown: SeverityBreakdown[];
}

// /api/advisor/trend
export interface TrendPoint {
  snapshot_date: string;
  ediscovery_cases: number;
  sensitivity_labels: number;
  retention_labels: number;
  dlp_alerts: number;
  audit_records: number;
  tenant_count: number;
}

export interface TrendResponse {
  trend: TrendPoint[];
}

// /api/advisor/subject-rights
export interface SubjectRightsRequest {
  request_id: string;
  display_name: string;
  request_type: string;
  status: string;
  created: string;
  closed: string | null;
  data_subject_type: string;
  tenant_name: string;
}

export interface SubjectRightsResponse {
  requests: SubjectRightsRequest[];
  status_breakdown: StatusBreakdown[];
}

// /api/advisor/comm-compliance
export interface CommCompliancePolicy {
  policy_id: string;
  display_name: string;
  status: string;
  policy_type: string;
  review_pending_count: number;
  tenant_name: string;
}

export interface CommComplianceResponse {
  policies: CommCompliancePolicy[];
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

// /api/advisor/sensitive-info-types
export interface SensitiveInfoType {
  type_id: string;
  name: string;
  description: string;
  is_custom: boolean;
  category: string;
  scope: string;
  state: string;
  tenant_name: string;
}

export interface SensitiveInfoTypesResponse {
  types: SensitiveInfoType[];
  custom_count: number;
  builtin_count: number;
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

// /api/advisor/briefing
export interface BriefingResponse {
  briefing: string;
}

// /api/advisor/ask
export interface AskResponse {
  answer: string;
}

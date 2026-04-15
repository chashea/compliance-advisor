import { useState } from "react";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import KPICard from "../components/KPICard";
import LineChart from "../components/LineChart";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import { useTenant } from "../hooks/useTenant";
import type {
  ActionsResponse,
  AssessmentsResponse,
  DLPResponse,
  LabelsResponse,
  MappedControl,
  OwnerLoad,
  OverviewResponse,
  PriorityAction,
  PurviewIncidentsResponse,
  PurviewInsightsResponse,
  StatusResponse,
  TenantCollectionHealth,
  TrendResponse,
  IRMResponse,
} from "../types";

const RANGES = [7, 30, 90] as const;

const IconShield = (
  <svg className="h-5 w-5 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3l8 3v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6l8-3z" />
  </svg>
);

const IconChart = (
  <svg className="h-5 w-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18M7 13l4-4 3 3 4-6" />
  </svg>
);

const IconPolicy = (
  <svg className="h-5 w-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6M7 4h10a2 2 0 012 2v12a2 2 0 01-2 2H7a2 2 0 01-2-2V6a2 2 0 012-2z" />
  </svg>
);

const IconFresh = (
  <svg className="h-5 w-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v6h6M20 20v-6h-6M20 9a8 8 0 10-2 8" />
  </svg>
);

function fmtPct(value: number): string {
  return `${value.toFixed(1)}%`;
}

function riskBadge(level: string): string {
  const low = "bg-emerald-600/20 text-emerald-400";
  if (level === "Critical") return "bg-red-600/20 text-red-400";
  if (level === "High") return "bg-amber-600/20 text-amber-400";
  if (level === "Medium") return "bg-sky-600/20 text-sky-400";
  return low;
}

function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function isResolved(status: string): boolean {
  const s = status.toLowerCase();
  return s === "resolved" || s === "dismissed";
}

function isNotFoundError(error: string | null): boolean {
  if (!error) return false;
  const text = error.toLowerCase();
  return text.includes("404") || text.includes("not found");
}

function buildFallbackInsights(args: {
  days: number;
  status: StatusResponse;
  overview: OverviewResponse;
  dlp: DLPResponse;
  irm: IRMResponse;
  incidents: PurviewIncidentsResponse;
  labels: LabelsResponse;
  assessments: AssessmentsResponse;
  actions: ActionsResponse;
  trend: TrendResponse;
}): PurviewInsightsResponse {
  const { days, status, overview, dlp, irm, incidents, labels, assessments, actions, trend } = args;
  const now = new Date();
  const alertRows = [...dlp.alerts, ...irm.alerts];
  const totalAlerts = alertRows.length;
  const resolvedAlerts = alertRows.filter((a) => isResolved(a.status)).length;
  const activeAlerts = totalAlerts - resolvedAlerts;
  const truePositiveAlerts = alertRows.filter((a) => a.classification === "truePositive").length;

  let mttrSum = 0;
  let mttrCount = 0;
  for (const alert of alertRows) {
    if (!alert.resolved) continue;
    const created = parseDate(alert.created);
    const resolved = parseDate(alert.resolved);
    if (!created || !resolved) continue;
    const hours = (resolved.getTime() - created.getTime()) / (1000 * 60 * 60);
    if (hours >= 0) {
      mttrSum += hours;
      mttrCount += 1;
    }
  }
  const mttrHours = mttrCount ? mttrSum / mttrCount : 0;

  const incidentOwnerById: Record<string, string> = {};
  for (const incident of incidents.incidents) {
    incidentOwnerById[incident.incident_id] = incident.assigned_to || "Compliance Team";
  }

  const ownerMap: Record<string, { owner: string; total_alerts: number; open_alerts: number; high_severity: number; active_incidents: number; age_sum: number; age_count: number }> = {};
  const ensureOwner = (owner: string) => {
    if (!ownerMap[owner]) {
      ownerMap[owner] = {
        owner,
        total_alerts: 0,
        open_alerts: 0,
        high_severity: 0,
        active_incidents: 0,
        age_sum: 0,
        age_count: 0,
      };
    }
    return ownerMap[owner];
  };

  for (const alert of alertRows) {
    const owner = (alert.incident_id && incidentOwnerById[alert.incident_id]) || "Compliance Team";
    const row = ensureOwner(owner);
    row.total_alerts += 1;
    if (!isResolved(alert.status)) {
      row.open_alerts += 1;
      if (alert.severity.toLowerCase() === "high") row.high_severity += 1;
      const created = parseDate(alert.created);
      if (created) {
        row.age_sum += Math.max(0, (now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24));
        row.age_count += 1;
      }
    }
  }

  for (const incident of incidents.incidents) {
    if (!isResolved(incident.status)) {
      const owner = incident.assigned_to || "Compliance Team";
      ensureOwner(owner).active_incidents += 1;
    }
  }

  const ownerLoads = Object.values(ownerMap)
    .map((r) => ({
      owner: r.owner,
      open_alerts: r.open_alerts,
      high_severity: r.high_severity,
      active_incidents: r.active_incidents,
      avg_age_days: r.age_count ? Number((r.age_sum / r.age_count).toFixed(1)) : 0,
    }))
    .sort((a, b) => (b.open_alerts + b.active_incidents) - (a.open_alerts + a.active_incidents));

  const repeatOffenders = Object.values(ownerMap)
    .map((r) => ({
      owner: r.owner,
      total_alerts: r.total_alerts,
      open_alerts: r.open_alerts,
      high_severity: r.high_severity,
      avg_age_days: r.age_count ? Number((r.age_sum / r.age_count).toFixed(1)) : 0,
    }))
    .sort((a, b) => b.open_alerts - a.open_alerts);

  const coverageMap: Record<string, { applicable_to: string; total: number; protected: number }> = {};
  for (const label of labels.sensitivity_labels) {
    const key = label.applicable_to || "unspecified";
    if (!coverageMap[key]) coverageMap[key] = { applicable_to: key, total: 0, protected: 0 };
    coverageMap[key].total += 1;
    if (label.has_protection) coverageMap[key].protected += 1;
  }
  const coverageBreakdown = Object.values(coverageMap).sort((a, b) => b.total - a.total);
  const totalLabels = labels.sensitivity_labels.length;
  const protectedLabels = labels.sensitivity_labels.filter((l) => l.has_protection).length;
  const coveragePct = totalLabels ? (protectedLabels / totalLabels) * 100 : 0;

  const scorePct = actions.secure_score.data_max_score
    ? (actions.secure_score.data_current_score / actions.secure_score.data_max_score) * 100
    : 0;
  const timeline = trend.trend.map((point, idx) => {
    const history = trend.trend.slice(Math.max(0, idx - 7), idx).map((p) => p.dlp_alerts);
    const baseline = history.length ? history.reduce((s, n) => s + n, 0) / history.length : 0;
    const riskSpike = baseline > 0 ? point.dlp_alerts >= baseline * 1.25 && point.dlp_alerts - baseline >= 2 : point.dlp_alerts >= 3;
    return {
      snapshot_date: point.snapshot_date,
      dlp_alerts: point.dlp_alerts,
      active_incidents: incidents.incidents.filter((i) => !isResolved(i.status)).length,
      policy_changes: 0,
      data_score_pct: Number(scorePct.toFixed(2)),
      risk_spike: riskSpike,
      correlated_change: false,
      secure_score_delta: 0,
    };
  });

  const unresolvedHighAlerts = alertRows.filter((a) => !isResolved(a.status) && a.severity.toLowerCase() === "high").length;
  const unresolvedMediumAlerts = alertRows.filter((a) => !isResolved(a.status) && a.severity.toLowerCase() === "medium").length;
  const activeIncidents = incidents.incidents.filter((i) => !isResolved(i.status)).length;
  const unprotectedLabels = Math.max(totalLabels - protectedLabels, 0);
  const weightedPoints = {
    high_alert_weighted: unresolvedHighAlerts * 5,
    medium_alert_weighted: unresolvedMediumAlerts * 3,
    active_incident_weighted: activeIncidents * 4,
    unprotected_label_weighted: unprotectedLabels * 2,
  };
  const weightedTotal =
    weightedPoints.high_alert_weighted +
    weightedPoints.medium_alert_weighted +
    weightedPoints.active_incident_weighted +
    weightedPoints.unprotected_label_weighted;
  const riskScore = Math.min(100, Number((weightedTotal * 1.5).toFixed(1)));
  const riskLevel = riskScore >= 80 ? "Critical" : riskScore >= 60 ? "High" : riskScore >= 35 ? "Medium" : "Low";

  const assessmentsByFramework: Record<string, { framework: string; total_assessments: number; avg_sum: number; estimated_gap_count: number }> = {};
  for (const assessment of assessments.assessments) {
    const key = assessment.framework || "Unspecified";
    if (!assessmentsByFramework[key]) {
      assessmentsByFramework[key] = { framework: key, total_assessments: 0, avg_sum: 0, estimated_gap_count: 0 };
    }
    assessmentsByFramework[key].total_assessments += 1;
    assessmentsByFramework[key].avg_sum += assessment.completion_percentage;
    if (assessment.completion_percentage < 80) assessmentsByFramework[key].estimated_gap_count += 1;
  }
  const frameworkSummary = Object.values(assessmentsByFramework).map((f) => ({
    framework: f.framework,
    total_assessments: f.total_assessments,
    avg_completion: Number((f.avg_sum / Math.max(f.total_assessments, 1)).toFixed(1)),
    estimated_gap_count: f.estimated_gap_count,
  }));
  const preferredFramework =
    frameworkSummary.find((f) => f.framework.toLowerCase().includes("cjis"))?.framework ||
    frameworkSummary.find((f) => f.framework.toLowerCase().includes("nist"))?.framework ||
    frameworkSummary[0]?.framework ||
    "NIST 800-53";

  const openActions = actions.actions.filter((a) => a.max_score > a.current_score);
  const controls = openActions.slice(0, 10).map((a) => ({
    framework: preferredFramework,
    control_id: a.control_id,
    control_title: a.title,
    status: a.state,
    priority: a.max_score - a.current_score >= 8 ? "High" : "Medium",
    owner: ownerLoads[0]?.owner ?? "Compliance Team",
    completion_percentage: frameworkSummary.find((f) => f.framework === preferredFramework)?.avg_completion ?? 0,
    evidence_links: [
      {
        label: "Secure Score Action",
        url: `https://security.microsoft.com/securescore?viewid=actions&control=${a.control_id}`,
      },
      {
        label: "Purview Compliance Manager",
        url: `https://purview.microsoft.com/compliancemanager/assessments/${a.control_id}`,
      },
    ],
  }));

  const priorityActions = [
    ...openActions.slice(0, 10).map((a) => ({
      action_type: "Secure Score Improvement",
      title: a.title,
      owner: ownerLoads[0]?.owner ?? "Compliance Team",
      priority: a.max_score - a.current_score >= 8 ? "High" : "Medium",
      risk_reduction_score: Number((a.max_score - a.current_score).toFixed(2)),
      tenant_name: a.tenant_name,
      evidence_link: `https://security.microsoft.com/securescore?viewid=actions&control=${a.control_id}`,
    })),
    ...incidents.incidents
      .filter((i) => !isResolved(i.status))
      .slice(0, 5)
      .map((i) => ({
        action_type: "Incident Triage",
        title: i.display_name,
        owner: i.assigned_to || "Compliance Team",
        priority: i.severity.toLowerCase() === "high" || i.severity.toLowerCase() === "critical" ? "High" : "Medium",
        risk_reduction_score: i.severity.toLowerCase() === "critical" ? 9 : i.severity.toLowerCase() === "high" ? 7 : 5,
        tenant_name: i.tenant_name,
        evidence_link: `https://purview.microsoft.com/insiderriskmanagement?view=alerts&incidentId=${i.incident_id}`,
      })),
  ].sort((a, b) => b.risk_reduction_score - a.risk_reduction_score);

  const requiredDatasets = [
    "dlp_alerts",
    "irm_alerts",
    "purview_incidents",
    "sensitivity_labels",
    "compliance_assessments",
    "improvement_actions",
    "trend_points",
  ];

  const countForTenant = (tenant: string) => ({
    dlp_alerts: dlp.alerts.filter((r) => r.tenant_name === tenant).length,
    irm_alerts: irm.alerts.filter((r) => r.tenant_name === tenant).length,
    purview_incidents: incidents.incidents.filter((r) => r.tenant_name === tenant).length,
    sensitivity_labels: labels.sensitivity_labels.filter((r) => r.tenant_name === tenant).length,
    compliance_assessments: assessments.assessments.filter((r) => r.tenant_name === tenant).length,
    improvement_actions: actions.actions.filter((r) => r.tenant_name === tenant).length,
    trend_points: trend.trend.length,
  });

  const newestSync = status.newest_sync;
  const newestSyncDate = parseDate(newestSync);
  const stale = newestSyncDate ? now.getTime() - newestSyncDate.getTime() > 48 * 60 * 60 * 1000 : true;
  const tenantHealth = overview.tenants.map((tenant) => {
    const counts = countForTenant(tenant.display_name);
    const missing = requiredDatasets.filter((k) => (counts as Record<string, number>)[k] <= 0);
    const completenessPct = ((requiredDatasets.length - missing.length) / requiredDatasets.length) * 100;
    return {
      tenant_id: tenant.tenant_id,
      display_name: tenant.display_name,
      department: tenant.department,
      last_collected_at: newestSync,
      last_snapshot_date: trend.trend.at(-1)?.snapshot_date ?? null,
      last_payload_at: newestSync,
      is_stale: stale,
      completeness_pct: Number(completenessPct.toFixed(1)),
      missing_datasets: missing,
    };
  });

  return {
    effectiveness: {
      total_alerts: totalAlerts,
      resolved_alerts: resolvedAlerts,
      active_alerts: activeAlerts,
      closure_rate_pct: totalAlerts ? Number(((resolvedAlerts / totalAlerts) * 100).toFixed(1)) : 0,
      true_positive_rate_pct: totalAlerts ? Number(((truePositiveAlerts / totalAlerts) * 100).toFixed(1)) : 0,
      mttr_hours: Number(mttrHours.toFixed(2)),
      repeat_offenders: repeatOffenders,
    },
    classification_coverage: {
      total_labels: totalLabels,
      protected_labels: protectedLabels,
      coverage_pct: Number(coveragePct.toFixed(1)),
      breakdown: coverageBreakdown,
    },
    policy_drift: {
      window_days: days,
      timeline,
      summary: {
        total_policy_changes: 0,
        risk_spike_days: timeline.filter((p) => p.risk_spike).length,
        correlated_days: 0,
      },
    },
    data_at_risk: {
      score: riskScore,
      risk_level: riskLevel,
      components: {
        unresolved_high_alerts: unresolvedHighAlerts,
        unresolved_medium_alerts: unresolvedMediumAlerts,
        active_incidents: activeIncidents,
        unprotected_labels: unprotectedLabels,
      },
      weighted_points: weightedPoints,
    },
    control_mapping: {
      framework_summary: frameworkSummary,
      controls,
    },
    owner_actions: {
      owners: ownerLoads,
      priority_actions: priorityActions,
    },
    collection_health: {
      required_datasets: requiredDatasets,
      newest_sync: newestSync,
      stale_tenants: tenantHealth.filter((t) => t.is_stale).length,
      complete_tenants: tenantHealth.filter((t) => t.missing_datasets.length === 0).length,
      tenant_health: tenantHealth,
    },
  };
}

export default function PurviewInsights() {
  const { tenantId } = useTenant();
  const [days, setDays] = useState<number>(30);
  const baseBody: Record<string, unknown> = {};
  if (tenantId) baseBody.tenant_id = tenantId;
  const insightsBody: Record<string, unknown> = { ...baseBody, days };
  const insights = useApi<PurviewInsightsResponse>("purview-insights", insightsBody, [tenantId, days]);
  const status = useApi<StatusResponse>("status", {}, []);
  const overview = useApi<OverviewResponse>("overview", baseBody, [tenantId]);
  const dlp = useApi<DLPResponse>("dlp", baseBody, [tenantId]);
  const irm = useApi<IRMResponse>("irm", baseBody, [tenantId]);
  const incidents = useApi<PurviewIncidentsResponse>("purview-incidents", baseBody, [tenantId]);
  const labels = useApi<LabelsResponse>("labels", baseBody, [tenantId]);
  const assessments = useApi<AssessmentsResponse>("assessments", baseBody, [tenantId]);
  const actions = useApi<ActionsResponse>("actions", baseBody, [tenantId]);
  const trend = useApi<TrendResponse>("trend", insightsBody, [tenantId, days]);

  const compatibilityMode = isNotFoundError(insights.error);
  const fallbackLoading =
    status.loading ||
    overview.loading ||
    dlp.loading ||
    irm.loading ||
    incidents.loading ||
    labels.loading ||
    assessments.loading ||
    actions.loading ||
    trend.loading;
  const fallbackError = status.error || overview.error || dlp.error || irm.error || incidents.error || labels.error || assessments.error || actions.error || trend.error;

  if (insights.loading) return <Loading />;
  if (!insights.data && !compatibilityMode) return <ErrorBanner message={insights.error ?? "Failed to load Purview insights"} />;
  if (!insights.data && compatibilityMode && fallbackLoading) return <Loading />;
  if (!insights.data && compatibilityMode && fallbackError) {
    return <ErrorBanner message={`Purview Insights endpoint not available and compatibility mode failed: ${fallbackError}`} />;
  }

  const data =
    insights.data ??
    buildFallbackInsights({
      days,
      status: status.data!,
      overview: overview.data!,
      dlp: dlp.data!,
      irm: irm.data!,
      incidents: incidents.data!,
      labels: labels.data!,
      assessments: assessments.data!,
      actions: actions.data!,
      trend: trend.data!,
    });

  const effectiveness = data.effectiveness;
  const coverage = data.classification_coverage;
  const drift = data.policy_drift;
  const risk = data.data_at_risk;
  const mapping = data.control_mapping;
  const ownerActions = data.owner_actions;
  const health = data.collection_health;

  const coverageChart = coverage.breakdown.map((row) => ({
    surface: row.applicable_to,
    total: row.total,
    protected: row.protected,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Purview Insights</h2>
          <p className="text-sm text-navy-300">Advanced Purview analytics: effectiveness, drift, risk, controls, ownership, and data freshness.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-navy-800 p-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setDays(r)}
                className={`rounded-md px-3 py-1 text-sm ${days === r ? "bg-gold-500 text-white" : "text-navy-300 hover:text-white"}`}
              >
                {r}d
              </button>
            ))}
          </div>
          <button
            onClick={() => {
              insights.refetch();
              if (compatibilityMode) {
                status.refetch();
                overview.refetch();
                dlp.refetch();
                irm.refetch();
                incidents.refetch();
                labels.refetch();
                assessments.refetch();
                actions.refetch();
                trend.refetch();
              }
            }}
            className="rounded-lg border border-navy-600 px-3 py-1.5 text-sm text-navy-200 hover:bg-navy-700"
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {compatibilityMode && (
        <div className="rounded-lg border border-amber-600/40 bg-amber-900/20 px-4 py-2 text-sm text-amber-300">
          {"`purview-insights` endpoint was not found on this backend. Showing compatibility mode using existing dashboard APIs."}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KPICard
          icon={IconShield}
          iconBg="bg-red-600/20"
          value={risk.score}
          label="Data at Risk Score"
          delta={risk.risk_level}
          deltaUp={risk.risk_level === "Low"}
        />
        <KPICard
          icon={IconChart}
          iconBg="bg-sky-600/20"
          value={fmtPct(effectiveness.closure_rate_pct)}
          label="Alert Closure Rate"
          delta={`${effectiveness.mttr_hours.toFixed(1)}h MTTR`}
          deltaUp
        />
        <KPICard
          icon={IconPolicy}
          iconBg="bg-amber-600/20"
          value={drift.summary.total_policy_changes}
          label="Policy Changes"
          delta={`${drift.summary.correlated_days} correlated spikes`}
          deltaUp={false}
        />
        <KPICard
          icon={IconFresh}
          iconBg="bg-emerald-600/20"
          value={`${health.complete_tenants}/${health.tenant_health.length}`}
          label="Complete Tenants"
          delta={`${health.stale_tenants} stale`}
          deltaUp={health.stale_tenants === 0}
        />
      </div>

      <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
        <div className="mb-3 flex items-center gap-3">
          <h3 className="text-sm font-semibold text-navy-100">Weighted Data-at-Risk Model</h3>
          <span className={`rounded px-2 py-0.5 text-xs font-semibold ${riskBadge(risk.risk_level)}`}>{risk.risk_level}</span>
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm lg:grid-cols-4">
          <div>
            <p className="text-navy-400">Unresolved high</p>
            <p className="text-lg font-semibold text-red-400">{risk.components.unresolved_high_alerts}</p>
          </div>
          <div>
            <p className="text-navy-400">Unresolved medium</p>
            <p className="text-lg font-semibold text-amber-400">{risk.components.unresolved_medium_alerts}</p>
          </div>
          <div>
            <p className="text-navy-400">Active incidents</p>
            <p className="text-lg font-semibold text-sky-400">{risk.components.active_incidents}</p>
          </div>
          <div>
            <p className="text-navy-400">Unprotected labels</p>
            <p className="text-lg font-semibold text-teal-400">{risk.components.unprotected_labels}</p>
          </div>
          {(risk.components.hunt_high_findings ?? 0) > 0 && (
            <div>
              <p className="text-navy-400">Hunt findings (high)</p>
              <p className="text-lg font-semibold text-red-400">{risk.components.hunt_high_findings}</p>
            </div>
          )}
          {(risk.components.hunt_medium_findings ?? 0) > 0 && (
            <div>
              <p className="text-navy-400">Hunt findings (medium)</p>
              <p className="text-lg font-semibold text-amber-400">{risk.components.hunt_medium_findings}</p>
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <h3 className="mb-3 text-sm font-semibold text-navy-100">Policy Drift vs Risk Spikes</h3>
          <LineChart
            data={drift.timeline}
            xKey="snapshot_date"
            series={[
              { key: "dlp_alerts", color: "#dc2626", label: "DLP Alerts" },
              { key: "active_incidents", color: "#0ea5e9", label: "Active Incidents" },
              { key: "policy_changes", color: "#f59e0b", label: "Policy Changes" },
              { key: "data_score_pct", color: "#14b8a6", label: "Data Score %" },
            ]}
            height={320}
          />
        </div>
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <h3 className="mb-3 text-sm font-semibold text-navy-100">Classification Coverage</h3>
          <p className="mb-3 text-xs text-navy-300">
            Protected labels: <span className="font-semibold text-emerald-400">{coverage.protected_labels}</span> / {coverage.total_labels} ({fmtPct(coverage.coverage_pct)})
          </p>
          {coverageChart.length > 0 ? (
            <BarChart data={coverageChart} xKey="surface" yKey="protected" color="#14b8a6" height={280} />
          ) : (
            <p className="text-sm text-navy-400">No label coverage data available.</p>
          )}
        </div>
      </div>

      {data.threat_hunting && data.threat_hunting.summary.total > 0 && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <h3 className="mb-3 text-sm font-semibold text-navy-100">Threat Hunting</h3>
          <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-navy-400">Total Findings</p>
              <p className="mt-1 text-2xl font-bold text-white">{data.threat_hunting.summary.total}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-navy-400">High</p>
              <p className="mt-1 text-2xl font-bold text-red-400">{data.threat_hunting.summary.high}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-navy-400">Medium</p>
              <p className="mt-1 text-2xl font-bold text-amber-400">{data.threat_hunting.summary.medium}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-navy-400">Low / Info</p>
              <p className="mt-1 text-2xl font-bold text-sky-400">{data.threat_hunting.summary.low + data.threat_hunting.summary.info}</p>
            </div>
          </div>
          {data.threat_hunting.top_findings.length > 0 && (
            <DataTable<(typeof data.threat_hunting.top_findings)[number] & Record<string, unknown>>
              columns={[
                { key: "severity", label: "Severity" },
                { key: "finding_type", label: "Type" },
                { key: "account_upn", label: "User" },
                { key: "object_name", label: "Object" },
                { key: "tenant_name", label: "Tenant" },
                { key: "detected_at", label: "Detected" },
              ]}
              data={data.threat_hunting.top_findings as ((typeof data.threat_hunting.top_findings)[number] & Record<string, unknown>)[]}
              keyField="detected_at"
            />
          )}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-semibold text-navy-100">Owner Prioritization</h3>
          <DataTable<OwnerLoad & Record<string, unknown>>
            columns={[
              { key: "owner", label: "Owner" },
              { key: "open_alerts", label: "Open Alerts" },
              { key: "high_severity", label: "High Severity" },
              { key: "active_incidents", label: "Active Incidents" },
              { key: "avg_age_days", label: "Avg Age (Days)" },
            ]}
            data={ownerActions.owners as (OwnerLoad & Record<string, unknown>)[]}
            keyField="owner"
          />
        </div>
        <div>
          <h3 className="mb-3 text-sm font-semibold text-navy-100">Priority Actions</h3>
          <DataTable<PriorityAction & Record<string, unknown>>
            columns={[
              { key: "action_type", label: "Type" },
              { key: "title", label: "Action" },
              { key: "owner", label: "Owner" },
              {
                key: "priority",
                label: "Priority",
                render: (v) => {
                  const p = String(v);
                  const cls = p === "High" ? "bg-red-600/20 text-red-400" : p === "Medium" ? "bg-amber-600/20 text-amber-400" : "bg-emerald-600/20 text-emerald-400";
                  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${cls}`}>{p}</span>;
                },
              },
              { key: "risk_reduction_score", label: "Risk Reduction" },
              {
                key: "evidence_link",
                label: "Evidence",
                render: (v) => (
                  <a href={String(v)} target="_blank" rel="noreferrer" className="text-sky-400 underline">
                    Open
                  </a>
                ),
              },
            ]}
            data={ownerActions.priority_actions as (PriorityAction & Record<string, unknown>)[]}
            keyField="title"
          />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-semibold text-navy-100">CJIS / NIST Framework Summary</h3>
          <DataTable<(PurviewInsightsResponse["control_mapping"]["framework_summary"][number] & Record<string, unknown>)>
            columns={[
              { key: "framework", label: "Framework" },
              { key: "total_assessments", label: "Assessments" },
              { key: "avg_completion", label: "Avg Completion %" },
              { key: "estimated_gap_count", label: "Estimated Gaps" },
            ]}
            data={mapping.framework_summary as (PurviewInsightsResponse["control_mapping"]["framework_summary"][number] & Record<string, unknown>)[]}
            keyField="framework"
          />
        </div>
        <div>
          <h3 className="mb-3 text-sm font-semibold text-navy-100">Mapped Controls + Evidence</h3>
          <DataTable<MappedControl & Record<string, unknown>>
            columns={[
              { key: "framework", label: "Framework" },
              { key: "control_id", label: "Control ID" },
              { key: "control_title", label: "Control" },
              { key: "priority", label: "Priority" },
              { key: "owner", label: "Owner" },
              {
                key: "evidence_links",
                label: "Evidence",
                render: (v) => {
                  const links = (v as { label: string; url: string }[]) || [];
                  if (links.length === 0) return <span className="text-navy-400">—</span>;
                  return (
                    <div className="flex flex-col gap-1">
                      {links.slice(0, 2).map((link) => (
                        <a key={link.url} href={link.url} target="_blank" rel="noreferrer" className="text-xs text-sky-400 underline">
                          {link.label}
                        </a>
                      ))}
                    </div>
                  );
                },
              },
            ]}
            data={mapping.controls as (MappedControl & Record<string, unknown>)[]}
            keyField="control_id"
          />
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-navy-100">Collection Freshness & Completeness</h3>
        <DataTable<TenantCollectionHealth & Record<string, unknown>>
          columns={[
            { key: "display_name", label: "Tenant" },
            { key: "department", label: "Department" },
            { key: "last_collected_at", label: "Last Collected" },
            { key: "last_snapshot_date", label: "Snapshot Date" },
            {
              key: "is_stale",
              label: "Freshness",
              render: (v) => {
                const stale = Boolean(v);
                return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${stale ? "bg-red-600/20 text-red-400" : "bg-emerald-600/20 text-emerald-400"}`}>{stale ? "Stale" : "Fresh"}</span>;
              },
            },
            { key: "completeness_pct", label: "Completeness %" },
            {
              key: "missing_datasets",
              label: "Missing Datasets",
              render: (v) => {
                const missing = (v as string[]) || [];
                return missing.length > 0 ? missing.slice(0, 3).join(", ") : "None";
              },
            },
          ]}
          data={health.tenant_health as (TenantCollectionHealth & Record<string, unknown>)[]}
          keyField="tenant_id"
        />
      </div>
    </div>
  );
}

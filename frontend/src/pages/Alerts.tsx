import { useState } from "react";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useTenant } from "../hooks/useTenant";
import { useApi } from "../hooks/useApi";
import type {
  DLPAlert,
  DLPPoliciesResponse,
  DLPPolicy,
  DLPResponse,
  EvidenceSummary,
  IRMAlert,
  IRMPoliciesResponse,
  IRMPolicy,
  IRMResponse,
  PurviewIncident,
  PurviewIncidentsResponse,
} from "../types";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-red-500",
  high: "text-red-400",
  medium: "text-amber-400",
  low: "text-navy-400",
};

const CLASSIFICATION_COLORS: Record<string, string> = {
  truePositive: "bg-red-500/20 text-red-400",
  falsePositive: "bg-emerald-500/20 text-emerald-400",
  informationalExpectedActivity: "bg-sky-500/20 text-sky-400",
  unknown: "bg-navy-600/40 text-navy-300",
};

function EvidenceSummaryPanel({ summary }: { summary: EvidenceSummary }) {
  if (summary.total_evidence_items === 0) return null;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {summary.verdict_breakdown.length > 0 && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <h3 className="mb-3 text-sm font-semibold text-navy-200">Evidence by Verdict</h3>
          <BarChart data={summary.verdict_breakdown} xKey="verdict" yKey="count" color="#8b5cf6" height={200} />
        </div>
      )}
      {summary.remediation_breakdown.length > 0 && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <h3 className="mb-3 text-sm font-semibold text-navy-200">Remediation Status</h3>
          <BarChart data={summary.remediation_breakdown} xKey="status" yKey="count" color="#10b981" height={200} />
        </div>
      )}
      {summary.evidence_type_breakdown.length > 0 && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <h3 className="mb-3 text-sm font-semibold text-navy-200">Evidence Types</h3>
          <BarChart data={summary.evidence_type_breakdown} xKey="type" yKey="count" color="#06b6d4" height={200} />
        </div>
      )}
    </div>
  );
}

type Tab = "purview-incidents" | "dlp-alerts" | "dlp-policies" | "irm-alerts" | "irm-policies";

export default function Alerts() {
  const [tab, setTab] = useState<Tab>("purview-incidents");
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;

  const incidents = useApi<PurviewIncidentsResponse>("purview-incidents", body, [tenantId]);
  const dlpAlerts = useApi<DLPResponse>("dlp", body, [tenantId]);
  const dlpPolicies = useApi<DLPPoliciesResponse>("dlp-policies", body, [tenantId]);
  const irmAlerts = useApi<IRMResponse>("irm", body, [tenantId]);
  const irmPolicies = useApi<IRMPoliciesResponse>("irm-policies", body, [tenantId]);

  if (incidents.loading || dlpAlerts.loading || dlpPolicies.loading || irmAlerts.loading || irmPolicies.loading) {
    return <Loading />;
  }
  if (incidents.error) return <ErrorBanner message={incidents.error} />;
  if (dlpAlerts.error) return <ErrorBanner message={dlpAlerts.error} />;
  if (irmAlerts.error) return <ErrorBanner message={irmAlerts.error} />;

  const pi = incidents.data;
  const da = dlpAlerts.data;
  const dp = dlpPolicies.data;
  const ia = irmAlerts.data;
  const ip = irmPolicies.data;

  const incidentHigh = pi?.severity_breakdown.find((s) => s.severity === "high" || s.severity === "critical")?.total ?? 0;
  const dlpHigh = da?.severity_breakdown.find((s) => s.severity === "high")?.total ?? 0;
  const irmHigh = ia?.severity_breakdown.find((s) => s.severity === "high")?.total ?? 0;

  const tabs: [Tab, string][] = [
    ["purview-incidents", `Purview Incidents${pi ? ` (${pi.incidents.length})` : ""}`],
    ["dlp-alerts", `DLP Alerts${da ? ` (${da.alerts.length})` : ""}`],
    ["dlp-policies", `DLP Policies${dp ? ` (${dp.policies.length})` : ""}`],
    ["irm-alerts", `IRM Alerts${ia ? ` (${ia.alerts.length})` : ""}`],
    ["irm-policies", `IRM Policies${ip ? ` (${ip.policies.length})` : ""}`],
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Security Alerts</h2>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
          <p className="text-2xl font-bold text-violet-400">{pi?.incidents.length ?? 0}</p>
          <p className="text-xs text-navy-300">Purview Incidents</p>
          {incidentHigh > 0 && <p className="mt-1 text-xs text-red-400">{incidentHigh} high/critical</p>}
        </div>
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
          <p className="text-2xl font-bold text-red-400">{da?.alerts.length ?? 0}</p>
          <p className="text-xs text-navy-300">DLP Alerts</p>
          {dlpHigh > 0 && <p className="mt-1 text-xs text-red-400">{dlpHigh} high severity</p>}
        </div>
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
          <p className="text-2xl font-bold text-sky-400">{dp?.policies.length ?? 0}</p>
          <p className="text-xs text-navy-300">DLP Policies</p>
        </div>
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
          <p className="text-2xl font-bold text-amber-400">{ia?.alerts.length ?? 0}</p>
          <p className="text-xs text-navy-300">IRM Alerts</p>
          {irmHigh > 0 && <p className="mt-1 text-xs text-red-400">{irmHigh} high severity</p>}
        </div>
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
          <p className="text-2xl font-bold text-emerald-400">{ip?.policies.length ?? 0}</p>
          <p className="text-xs text-navy-300">IRM Policies</p>
        </div>
      </div>

      <div className="flex w-fit gap-1 rounded-lg bg-navy-800 p-1">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === key ? "bg-gold-500 text-white" : "text-navy-300 hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "purview-incidents" && pi && (
        <>
          <DataTable<PurviewIncident & Record<string, unknown>>
            columns={[
              { key: "display_name", label: "Incident" },
              {
                key: "severity",
                label: "Severity",
                render: (v) => (
                  <span className={`font-medium ${SEVERITY_COLORS[String(v).toLowerCase()] ?? ""}`}>{String(v)}</span>
                ),
              },
              { key: "status", label: "Status" },
              { key: "purview_alerts_count", label: "Purview Alerts" },
              { key: "last_update", label: "Last Update" },
              { key: "tenant_name", label: "Tenant" },
            ]}
            data={pi.incidents as (PurviewIncident & Record<string, unknown>)[]}
            keyField="incident_id"
          />
          {pi.severity_breakdown.length > 0 && (
            <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
              <h3 className="mb-3 text-sm font-semibold text-navy-200">Purview Incidents by Severity</h3>
              <BarChart data={pi.severity_breakdown} xKey="severity" yKey="total" color="#8b5cf6" height={250} />
            </div>
          )}
          {pi.status_breakdown.length > 0 && (
            <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
              <h3 className="mb-3 text-sm font-semibold text-navy-200">Purview Incidents by Status</h3>
              <BarChart data={pi.status_breakdown} xKey="status" yKey="total" color="#0ea5e9" height={250} />
            </div>
          )}
        </>
      )}

      {tab === "dlp-alerts" && da && (
        <>
          <DataTable<DLPAlert & Record<string, unknown>>
            columns={[
              { key: "title", label: "Title" },
              {
                key: "severity",
                label: "Severity",
                render: (v) => (
                  <span className={`font-medium ${SEVERITY_COLORS[String(v).toLowerCase()] ?? ""}`}>{String(v)}</span>
                ),
              },
              { key: "status", label: "Status" },
              {
                key: "classification",
                label: "Classification",
                render: (v) => {
                  const cls = String(v || "");
                  if (!cls) return <span className="text-navy-500">—</span>;
                  return (
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${CLASSIFICATION_COLORS[cls] ?? "bg-navy-600/40 text-navy-300"}`}
                    >
                      {cls}
                    </span>
                  );
                },
              },
              { key: "policy_name", label: "Policy" },
              { key: "created", label: "Created" },
              { key: "tenant_name", label: "Tenant" },
            ]}
            data={da.alerts as (DLPAlert & Record<string, unknown>)[]}
            keyField="alert_id"
          />
          {da.severity_breakdown.length > 0 && (
            <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
              <h3 className="mb-3 text-sm font-semibold text-navy-200">DLP Alerts by Severity</h3>
              <BarChart data={da.severity_breakdown} xKey="severity" yKey="total" color="#dc2626" height={250} />
            </div>
          )}
          {da.policy_breakdown.length > 0 && (
            <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
              <h3 className="mb-3 text-sm font-semibold text-navy-200">DLP Alerts by Policy</h3>
              <BarChart data={da.policy_breakdown} xKey="policy_name" yKey="total" color="#3b82f6" height={250} />
            </div>
          )}
          {da.evidence_summary && <EvidenceSummaryPanel summary={da.evidence_summary} />}
        </>
      )}

      {tab === "dlp-policies" && dp && (
        <>
          {dp.status_breakdown.length > 0 && (
            <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
              <h3 className="mb-3 text-sm font-semibold text-navy-200">DLP Policies by Status</h3>
              <BarChart data={dp.status_breakdown} xKey="status" yKey="total" color="#3b82f6" height={250} />
            </div>
          )}
          <DataTable<DLPPolicy & Record<string, unknown>>
            columns={[
              { key: "display_name", label: "Policy" },
              { key: "status", label: "Status" },
              { key: "policy_type", label: "Type" },
              { key: "rules_count", label: "Rules" },
              { key: "mode", label: "Mode" },
              { key: "created", label: "Created" },
              { key: "tenant_name", label: "Tenant" },
            ]}
            data={dp.policies as (DLPPolicy & Record<string, unknown>)[]}
            keyField="policy_id"
          />
        </>
      )}

      {tab === "irm-alerts" && ia && (
        <>
          <DataTable<IRMAlert & Record<string, unknown>>
            columns={[
              { key: "title", label: "Title" },
              {
                key: "severity",
                label: "Severity",
                render: (v) => (
                  <span className={`font-medium ${SEVERITY_COLORS[String(v).toLowerCase()] ?? ""}`}>{String(v)}</span>
                ),
              },
              { key: "status", label: "Status" },
              {
                key: "classification",
                label: "Classification",
                render: (v) => {
                  const cls = String(v || "");
                  if (!cls) return <span className="text-navy-500">—</span>;
                  return (
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${CLASSIFICATION_COLORS[cls] ?? "bg-navy-600/40 text-navy-300"}`}
                    >
                      {cls}
                    </span>
                  );
                },
              },
              { key: "policy_name", label: "Policy" },
              { key: "created", label: "Created" },
              { key: "tenant_name", label: "Tenant" },
            ]}
            data={ia.alerts as (IRMAlert & Record<string, unknown>)[]}
            keyField="alert_id"
          />
          {ia.severity_breakdown.length > 0 && (
            <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
              <h3 className="mb-3 text-sm font-semibold text-navy-200">IRM Alerts by Severity</h3>
              <BarChart data={ia.severity_breakdown} xKey="severity" yKey="total" color="#f59e0b" height={250} />
            </div>
          )}
          {ia.evidence_summary && <EvidenceSummaryPanel summary={ia.evidence_summary} />}
        </>
      )}

      {tab === "irm-policies" && ip && (
        <DataTable<IRMPolicy & Record<string, unknown>>
          columns={[
            { key: "display_name", label: "Policy" },
            { key: "status", label: "Status" },
            { key: "policy_type", label: "Type" },
            { key: "triggers", label: "Triggers" },
            { key: "created", label: "Created" },
            { key: "tenant_name", label: "Tenant" },
          ]}
          data={ip.policies as (IRMPolicy & Record<string, unknown>)[]}
          keyField="policy_id"
        />
      )}
    </div>
  );
}

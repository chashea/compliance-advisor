import { useState } from "react";
import { useTenant } from "../hooks/useTenant";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type {
  DLPAlert, DLPResponse, DLPPolicy, DLPPoliciesResponse,
  IRMAlert, IRMResponse, IRMPolicy, IRMPoliciesResponse,
} from "../types";

const SEVERITY_COLORS: Record<string, string> = {
  high: "text-red-400",
  medium: "text-amber-400",
  low: "text-navy-400",
};

type Tab = "dlp-alerts" | "dlp-policies" | "irm-alerts" | "irm-policies";

export default function Alerts() {
  const [tab, setTab] = useState<Tab>("dlp-alerts");
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;

  const dlpAlerts = useApi<DLPResponse>("dlp", body, [tenantId]);
  const dlpPolicies = useApi<DLPPoliciesResponse>("dlp-policies", body, [tenantId]);
  const irmAlerts = useApi<IRMResponse>("irm", body, [tenantId]);
  const irmPolicies = useApi<IRMPoliciesResponse>("irm-policies", body, [tenantId]);

  if (dlpAlerts.loading || dlpPolicies.loading || irmAlerts.loading || irmPolicies.loading) return <Loading />;
  if (dlpAlerts.error) return <ErrorBanner message={dlpAlerts.error} />;
  if (irmAlerts.error) return <ErrorBanner message={irmAlerts.error} />;

  const da = dlpAlerts.data;
  const dp = dlpPolicies.data;
  const ia = irmAlerts.data;
  const ip = irmPolicies.data;

  const dlpHigh = da?.severity_breakdown.find((s) => s.severity === "high")?.total ?? 0;
  const irmHigh = ia?.severity_breakdown.find((s) => s.severity === "high")?.total ?? 0;

  const tabs: [Tab, string][] = [
    ["dlp-alerts", `DLP Alerts${da ? ` (${da.alerts.length})` : ""}`],
    ["dlp-policies", `DLP Policies${dp ? ` (${dp.policies.length})` : ""}`],
    ["irm-alerts", `IRM Alerts${ia ? ` (${ia.alerts.length})` : ""}`],
    ["irm-policies", `IRM Policies${ip ? ` (${ip.policies.length})` : ""}`],
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Security Alerts</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
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

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-navy-800 p-1 w-fit">
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

      {/* DLP Alerts */}
      {tab === "dlp-alerts" && da && (
        <>
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
              { key: "policy_name", label: "Policy" },
              { key: "created", label: "Created" },
              { key: "tenant_name", label: "Tenant" },
            ]}
            data={da.alerts as (DLPAlert & Record<string, unknown>)[]}
            keyField="alert_id"
          />
        </>
      )}

      {/* DLP Policies */}
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

      {/* IRM Alerts */}
      {tab === "irm-alerts" && ia && (
        <>
          {ia.severity_breakdown.length > 0 && (
            <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
              <h3 className="mb-3 text-sm font-semibold text-navy-200">IRM Alerts by Severity</h3>
              <BarChart data={ia.severity_breakdown} xKey="severity" yKey="total" color="#f59e0b" height={250} />
            </div>
          )}
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
              { key: "policy_name", label: "Policy" },
              { key: "created", label: "Created" },
              { key: "tenant_name", label: "Tenant" },
            ]}
            data={ia.alerts as (IRMAlert & Record<string, unknown>)[]}
            keyField="alert_id"
          />
        </>
      )}

      {/* IRM Policies */}
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

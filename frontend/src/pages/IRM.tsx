import { useState } from "react";
import { useTenant } from "../hooks/useTenant";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { IRMAlert, IRMResponse, IRMPolicy, IRMPoliciesResponse } from "../types";

const SEVERITY_COLORS: Record<string, string> = { high: "text-red-600", medium: "text-amber-600", low: "text-navy-500" };

type Tab = "alerts" | "policies";

export default function IRM() {
  const [tab, setTab] = useState<Tab>("alerts");
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;

  const alerts = useApi<IRMResponse>("irm", body, [tenantId]);
  const policies = useApi<IRMPoliciesResponse>("irm-policies", body, [tenantId]);

  if (alerts.loading || policies.loading) return <Loading />;
  if (alerts.error) return <ErrorBanner message={alerts.error} />;
  if (policies.error) return <ErrorBanner message={policies.error} />;

  const a = alerts.data;
  const p = policies.data;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Insider Risk Management</h2>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-navy-800 p-1 w-fit">
        {([
          ["alerts", `Alerts${a ? ` (${a.alerts.length})` : ""}`],
          ["policies", `Policies${p ? ` (${p.policies.length})` : ""}`],
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === key
                ? "bg-gold-500 text-white"
                : "text-navy-300 hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Alerts tab */}
      {tab === "alerts" && a && (
        <>
          {a.severity_breakdown.length > 0 && (
            <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
              <h3 className="mb-3 text-sm font-semibold text-navy-200">By Severity</h3>
              <BarChart data={a.severity_breakdown} xKey="severity" yKey="total" color="#3b82f6" height={250} />
            </div>
          )}

          <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
            <DataTable<IRMAlert & Record<string, unknown>>
              columns={[
                { key: "title", label: "Title" },
                {
                  key: "severity",
                  label: "Severity",
                  render: (v) => (
                    <span className={`font-medium ${SEVERITY_COLORS[String(v).toLowerCase()] ?? ""}`}>
                      {String(v)}
                    </span>
                  ),
                },
                { key: "status", label: "Status" },
                { key: "policy_name", label: "Policy" },
                { key: "created", label: "Created" },
                { key: "tenant_name", label: "Tenant" },
              ]}
              data={a.alerts as (IRMAlert & Record<string, unknown>)[]}
              keyField="alert_id"
            />
          </div>
        </>
      )}

      {/* Policies tab */}
      {tab === "policies" && p && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <DataTable<IRMPolicy & Record<string, unknown>>
            columns={[
              { key: "display_name", label: "Policy" },
              { key: "status", label: "Status" },
              { key: "policy_type", label: "Type" },
              { key: "triggers", label: "Triggers" },
              { key: "created", label: "Created" },
              { key: "tenant_name", label: "Tenant" },
            ]}
            data={p.policies as (IRMPolicy & Record<string, unknown>)[]}
            keyField="policy_id"
          />
        </div>
      )}
    </div>
  );
}

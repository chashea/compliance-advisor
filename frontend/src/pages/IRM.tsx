import { useDepartment } from "../hooks/useDepartment";
import { useTenant } from "../hooks/useTenant";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { IRMAlert, IRMResponse } from "../types";

const SEVERITY_COLORS: Record<string, string> = { high: "text-red-600", medium: "text-amber-600", low: "text-navy-500" };

export default function IRM() {
  const { department } = useDepartment();
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (department) body.department = department;
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<IRMResponse>("irm", body, [department, tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Insider Risk Management ({data.alerts.length})</h2>

      {data.severity_breakdown.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">By Severity</h3>
          <BarChart data={data.severity_breakdown} xKey="severity" yKey="total" color="#486581" height={250} />
        </div>
      )}

      <DataTable<IRMAlert & Record<string, unknown>>
        columns={[
          { key: "title", label: "Title" },
          {
            key: "severity",
            label: "Severity",
            render: (v) => <span className={`font-medium ${SEVERITY_COLORS[String(v).toLowerCase()] ?? ""}`}>{String(v)}</span>,
          },
          { key: "status", label: "Status" },
          { key: "policy_name", label: "Policy" },
          { key: "created", label: "Created" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.alerts as (IRMAlert & Record<string, unknown>)[]}
        keyField="alert_id"
      />
    </div>
  );
}

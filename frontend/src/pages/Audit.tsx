import { useTenant } from "../hooks/useTenant";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { AuditRecord, AuditResponse } from "../types";

export default function Audit() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<AuditResponse>("audit", body, [tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Audit Log ({data.records.length} records)</h2>

      {data.service_breakdown.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">By Service</h3>
          <BarChart data={data.service_breakdown} xKey="service" yKey="total" height={250} />
        </div>
      )}

      {data.operation_breakdown.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Top Operations</h3>
          <BarChart data={data.operation_breakdown} xKey="operation" yKey="total" color="#0d9488" height={250} />
        </div>
      )}

      <DataTable<AuditRecord & Record<string, unknown>>
        columns={[
          { key: "operation", label: "Operation" },
          { key: "service", label: "Service" },
          { key: "user_id", label: "User" },
          { key: "record_type", label: "Type" },
          { key: "created", label: "Created" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.records as (AuditRecord & Record<string, unknown>)[]}
        keyField="record_id"
      />
    </div>
  );
}

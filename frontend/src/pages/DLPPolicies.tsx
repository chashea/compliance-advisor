import { useDepartment } from "../hooks/useDepartment";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { DLPPolicy, DLPPoliciesResponse } from "../types";

export default function DLPPolicies() {
  const { department } = useDepartment();
  const { data, loading, error } = useApi<DLPPoliciesResponse>("dlp-policies", department ? { department } : {}, [department]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">DLP Policies ({data.policies.length})</h2>

      {data.status_breakdown.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">By Status</h3>
          <BarChart data={data.status_breakdown} xKey="status" yKey="total" color="#dc2626" height={250} />
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
          { key: "modified", label: "Modified" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.policies as (DLPPolicy & Record<string, unknown>)[]}
        keyField="policy_id"
      />
    </div>
  );
}

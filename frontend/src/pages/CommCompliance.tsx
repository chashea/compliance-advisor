import { useTenant } from "../hooks/useTenant";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { CommCompliancePolicy, CommComplianceResponse } from "../types";

export default function CommCompliance() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<CommComplianceResponse>("comm-compliance", body, [tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Communication Compliance ({data.policies.length})</h2>
      <DataTable<CommCompliancePolicy & Record<string, unknown>>
        columns={[
          { key: "display_name", label: "Policy" },
          { key: "policy_type", label: "Type" },
          { key: "status", label: "Status" },
          { key: "review_pending_count", label: "Pending Reviews" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.policies as (CommCompliancePolicy & Record<string, unknown>)[]}
        keyField="policy_id"
      />
    </div>
  );
}

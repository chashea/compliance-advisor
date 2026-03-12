import { useDepartment } from "../components/DepartmentContext";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { CommCompliancePolicy, CommComplianceResponse } from "../types";

export default function CommCompliance() {
  const { department } = useDepartment();
  const { data, loading, error } = useApi<CommComplianceResponse>("comm-compliance", department ? { department } : {}, [department]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-800">Communication Compliance ({data.policies.length})</h2>
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

import { useDepartment } from "../components/DepartmentContext";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { GovernanceResponse, ProtectionScope } from "../types";

export default function Governance() {
  const { department } = useDepartment();
  const { data, loading, error } = useApi<GovernanceResponse>("governance", department ? { department } : {}, [department]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-800">Data Governance ({data.scopes.length})</h2>
      <DataTable<ProtectionScope & Record<string, unknown>>
        columns={[
          { key: "scope_type", label: "Scope Type" },
          { key: "execution_mode", label: "Execution Mode" },
          { key: "locations", label: "Locations" },
          { key: "activity_types", label: "Activity Types" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.scopes as (ProtectionScope & Record<string, unknown>)[]}
        keyField="scope_type"
      />
    </div>
  );
}

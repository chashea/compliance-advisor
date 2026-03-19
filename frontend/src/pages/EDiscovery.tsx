import { useDepartment } from "../components/DepartmentContext";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import PieChart from "../components/PieChart";
import { useApi } from "../hooks/useApi";
import type { EDiscoveryCase, EDiscoveryResponse } from "../types";

export default function EDiscovery() {
  const { department } = useDepartment();
  const { data, loading, error } = useApi<EDiscoveryResponse>("ediscovery", department ? { department } : {}, [department]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  const pieData = data.status_breakdown.map((s) => ({ name: s.status, value: s.total }));

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-100">eDiscovery Cases</h2>
      {pieData.length > 0 && (
        <div className="max-w-md">
          <h3 className="mb-2 text-sm font-medium text-slate-600 dark:text-slate-300">Status Breakdown</h3>
          <PieChart data={pieData} height={250} />
        </div>
      )}
      <DataTable<EDiscoveryCase & Record<string, unknown>>
        columns={[
          { key: "display_name", label: "Case Name" },
          { key: "status", label: "Status" },
          { key: "custodian_count", label: "Custodians" },
          { key: "created", label: "Created" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.cases as (EDiscoveryCase & Record<string, unknown>)[]}
        keyField="case_id"
      />
    </div>
  );
}

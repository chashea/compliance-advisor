import { useDepartment } from "../components/DepartmentContext";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import PieChart from "../components/PieChart";
import { useApi } from "../hooks/useApi";
import type { SubjectRightsRequest, SubjectRightsResponse } from "../types";

export default function SubjectRights() {
  const { department } = useDepartment();
  const { data, loading, error } = useApi<SubjectRightsResponse>("subject-rights", department ? { department } : {}, [department]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  const pieData = data.status_breakdown.map((s) => ({ name: s.status, value: s.total }));

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Subject Rights Requests ({data.requests.length})</h2>

      {pieData.length > 0 && (
        <div className="max-w-md">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Status Breakdown</h3>
          <PieChart data={pieData} height={250} />
        </div>
      )}

      <DataTable<SubjectRightsRequest & Record<string, unknown>>
        columns={[
          { key: "display_name", label: "Name" },
          { key: "request_type", label: "Type" },
          { key: "status", label: "Status" },
          { key: "data_subject_type", label: "Subject Type" },
          { key: "created", label: "Created" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.requests as (SubjectRightsRequest & Record<string, unknown>)[]}
        keyField="request_id"
      />
    </div>
  );
}

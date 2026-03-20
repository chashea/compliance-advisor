import { useDepartment } from "../hooks/useDepartment";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { Assessment, AssessmentsResponse } from "../types";

export default function Assessments() {
  const { department } = useDepartment();
  const { data, loading, error } = useApi<AssessmentsResponse>("assessments", department ? { department } : {}, [department]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Compliance Assessments ({data.assessments.length})</h2>

      {data.framework_breakdown.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">By Framework</h3>
          <BarChart data={data.framework_breakdown} xKey="framework" yKey="total" color="#b8860b" height={250} />
        </div>
      )}

      <DataTable<Assessment & Record<string, unknown>>
        columns={[
          { key: "display_name", label: "Assessment" },
          { key: "framework", label: "Framework" },
          { key: "status", label: "Status" },
          {
            key: "completion_percentage",
            label: "Completion",
            render: (v) => (
              <div className="flex items-center gap-2">
                <div className="h-2 w-24 rounded-full bg-slate-200 dark:bg-slate-700">
                  <div
                    className="h-2 rounded-full bg-gold-500"
                    style={{ width: `${Number(v)}%` }}
                  />
                </div>
                <span className="text-sm">{Number(v)}%</span>
              </div>
            ),
          },
          { key: "category", label: "Category" },
          { key: "created", label: "Created" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.assessments as (Assessment & Record<string, unknown>)[]}
        keyField="assessment_id"
      />
    </div>
  );
}

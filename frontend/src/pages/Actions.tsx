import { useDepartment } from "../components/DepartmentContext";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import StatCard from "../components/StatCard";
import { useApi } from "../hooks/useApi";
import type { ActionsResponse, ImprovementAction } from "../types";

export default function Actions() {
  const { department } = useDepartment();
  const { data, loading, error } = useApi<ActionsResponse>("actions", department ? { department } : {}, [department]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  const s = data.secure_score;
  const pct = s.max_score ? ((s.current_score / s.max_score) * 100).toFixed(0) : "0";
  const dataPct = s.data_max_score ? ((s.data_current_score / s.data_max_score) * 100).toFixed(0) : "0";

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-800">Secure Score & Improvement Actions</h2>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Overall Score" value={`${s.current_score} / ${s.max_score}`} sub={`${pct}%`} />
        <StatCard label="Data Category" value={`${s.data_current_score} / ${s.data_max_score}`} sub={`${dataPct}%`} />
        <StatCard label="Score Date" value={s.score_date ?? "N/A"} />
        <StatCard label="Actions" value={data.actions.length} />
      </div>

      {data.category_breakdown.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-slate-600">By Category</h3>
          <BarChart data={data.category_breakdown} xKey="control_category" yKey="total" color="#6366f1" height={250} />
        </div>
      )}

      <DataTable<ImprovementAction & Record<string, unknown>>
        columns={[
          { key: "rank", label: "#" },
          { key: "title", label: "Title" },
          { key: "control_category", label: "Category" },
          { key: "current_score", label: "Score" },
          { key: "max_score", label: "Max" },
          { key: "implementation_cost", label: "Cost" },
          { key: "user_impact", label: "Impact" },
          { key: "state", label: "State" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.actions as (ImprovementAction & Record<string, unknown>)[]}
        keyField="control_id"
      />
    </div>
  );
}

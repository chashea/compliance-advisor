import { useTenant } from "../hooks/useTenant";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import PieChart from "../components/PieChart";
import { useApi } from "../hooks/useApi";
import type { Assessment, AssessmentsResponse } from "../types";

export default function Assessments() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<AssessmentsResponse>("assessments", body, [tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  const frameworkPie = data.framework_breakdown.map((f) => ({ name: f.framework, value: f.total }));

  const avgCompletion =
    data.assessments.length > 0
      ? Math.round(data.assessments.reduce((sum, a) => sum + a.completion_percentage, 0) / data.assessments.length)
      : 0;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        Compliance Assessments ({data.assessments.length})
      </h2>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Total", value: data.assessments.length, color: "text-sky-400" },
          { label: "Active", value: data.assessments.filter((a) => a.status === "Active").length, color: "text-emerald-400" },
          { label: "Completed", value: data.assessments.filter((a) => a.status === "Completed").length, color: "text-teal-400" },
          { label: "Avg Completion", value: `${avgCompletion}%`, color: "text-amber-400" },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-xs text-navy-300">{stat.label}</p>
          </div>
        ))}
      </div>

      {frameworkPie.length > 0 && (
        <div className="max-w-md">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            By Framework
          </h3>
          <PieChart data={frameworkPie} height={250} />
        </div>
      )}

      <DataTable<Assessment & Record<string, unknown>>
        columns={[
          { key: "display_name", label: "Assessment" },
          { key: "framework", label: "Framework" },
          {
            key: "completion_percentage",
            label: "Completion",
            render: (v) => {
              const pct = v as number;
              return (
                <div className="flex items-center gap-2">
                  <div className="h-2 w-20 rounded-full bg-navy-700">
                    <div
                      className="h-2 rounded-full bg-teal-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs">{pct}%</span>
                </div>
              );
            },
          },
          {
            key: "status",
            label: "Status",
            render: (v) => {
              const s = String(v);
              const colors: Record<string, string> = {
                Active: "bg-emerald-600/20 text-emerald-400",
                Completed: "bg-teal-600/20 text-teal-400",
              };
              return (
                <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${colors[s] ?? "bg-navy-600/20 text-navy-300"}`}>
                  {s}
                </span>
              );
            },
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

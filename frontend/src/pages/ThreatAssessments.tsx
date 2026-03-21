import { useTenant } from "../hooks/useTenant";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import PieChart from "../components/PieChart";
import { useApi } from "../hooks/useApi";
import type { ThreatAssessmentRequest, ThreatAssessmentsResponse } from "../types";

export default function ThreatAssessments() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<ThreatAssessmentsResponse>("threat-assessments", body, [tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  const statusPie = data.status_breakdown.map((s) => ({ name: s.status, value: s.total }));
  const categoryPie = data.category_breakdown.map((c) => ({ name: c.category, value: c.total }));

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        Threat Assessment Requests ({data.requests.length})
      </h2>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Total", value: data.requests.length, color: "text-sky-400" },
          { label: "Spam", value: data.category_breakdown.find((c) => c.category === "spam")?.total ?? 0, color: "text-amber-400" },
          { label: "Phishing", value: data.category_breakdown.find((c) => c.category === "phishing")?.total ?? 0, color: "text-red-400" },
          { label: "Malware", value: data.category_breakdown.find((c) => c.category === "malware")?.total ?? 0, color: "text-rose-500" },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-xs text-navy-300">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid gap-6 md:grid-cols-2">
        {statusPie.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Status Breakdown</h3>
            <PieChart data={statusPie} height={250} />
          </div>
        )}
        {categoryPie.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Category Breakdown</h3>
            <PieChart data={categoryPie} height={250} />
          </div>
        )}
      </div>

      <DataTable<ThreatAssessmentRequest & Record<string, unknown>>
        columns={[
          { key: "category", label: "Category" },
          { key: "content_type", label: "Content Type" },
          { key: "status", label: "Status" },
          {
            key: "result_type",
            label: "Result",
            render: (v) => {
              const s = String(v);
              const colors: Record<string, string> = {
                malware: "bg-rose-600/20 text-rose-400",
                phishing: "bg-red-600/20 text-red-400",
                spam: "bg-amber-600/20 text-amber-400",
                clean: "bg-emerald-600/20 text-emerald-400",
              };
              return (
                <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${colors[s.toLowerCase()] ?? "bg-navy-600/20 text-navy-300"}`}>
                  {s || "Pending"}
                </span>
              );
            },
          },
          { key: "created", label: "Created" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.requests as (ThreatAssessmentRequest & Record<string, unknown>)[]}
        keyField="request_id"
      />
    </div>
  );
}

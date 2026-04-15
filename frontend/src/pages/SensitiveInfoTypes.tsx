import { useTenant } from "../hooks/useTenant";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import PieChart from "../components/PieChart";
import { useApi } from "../hooks/useApi";
import type { SensitiveInfoType, SensitiveInfoTypesResponse } from "../types";

export default function SensitiveInfoTypes() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<SensitiveInfoTypesResponse>("sensitive-info-types", body, [tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  const typePie = [
    { name: "Built-in", value: data.builtin_count },
    { name: "Custom", value: data.custom_count },
  ].filter((d) => d.value > 0);

  const categoryMap: Record<string, number> = {};
  for (const t of data.types) {
    const cat = t.category || "Uncategorized";
    categoryMap[cat] = (categoryMap[cat] || 0) + 1;
  }
  const categoryPie = Object.entries(categoryMap).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        Sensitive Information Types ({data.types.length})
      </h2>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {[
          { label: "Total", value: data.types.length, color: "text-sky-400" },
          { label: "Built-in", value: data.builtin_count, color: "text-emerald-400" },
          { label: "Custom", value: data.custom_count, color: "text-amber-400" },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-xs text-navy-300">{stat.label}</p>
          </div>
        ))}
      </div>

      {data.types.length === 0 ? (
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-6 text-center">
          <p className="text-sm text-navy-300">
            No sensitive information types found. These are auto-populated from tenant data classification settings.
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-6 md:grid-cols-2">
            {typePie.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Built-in vs Custom</h3>
                <PieChart data={typePie} height={250} />
              </div>
            )}
            {categoryPie.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">By Category</h3>
                <PieChart data={categoryPie} height={250} />
              </div>
            )}
          </div>

          <DataTable<SensitiveInfoType & Record<string, unknown>>
            columns={[
              { key: "name", label: "Name" },
              { key: "category", label: "Category" },
              {
                key: "is_custom",
                label: "Type",
                render: (v) => (
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${v ? "bg-amber-500/20 text-amber-400" : "bg-emerald-500/20 text-emerald-400"}`}>
                    {v ? "Custom" : "Built-in"}
                  </span>
                ),
              },
              { key: "scope", label: "Scope" },
              { key: "state", label: "State" },
              { key: "tenant_name", label: "Tenant" },
            ]}
            data={data.types as (SensitiveInfoType & Record<string, unknown>)[]}
            keyField="type_id"
          />
        </>
      )}
    </div>
  );
}

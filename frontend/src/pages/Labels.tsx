import { useTenant } from "../hooks/useTenant";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { LabelsResponse, SensitivityLabel, RetentionLabel, RetentionEvent } from "../types";

const modeColors: Record<string, string> = {
  automatic: "bg-sky-600/20 text-sky-400",
  recommended: "bg-amber-600/20 text-amber-400",
  manual: "bg-navy-600/20 text-navy-300",
};

const workloadIcons: Record<string, string> = {
  email: "✉️",
  file: "📄",
  site: "🌐",
  teamwork: "💬",
  unifiedGroup: "👥",
  schematizedData: "🗃️",
};

function WorkloadTags({ value }: { value: string }) {
  if (!value) return <span className="text-navy-500">—</span>;
  const items = value.split(",").map((s) => s.trim()).filter(Boolean);
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((w) => (
        <span key={w} className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs bg-navy-700/50 text-navy-200" title={w}>
          {workloadIcons[w] ?? "📋"} {w}
        </span>
      ))}
    </div>
  );
}

export default function Labels() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<LabelsResponse>("labels", body, [tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  const sl = data.sensitivity_labels;
  const protectedCount = sl.filter((l) => l.has_protection).length;
  const autoCount = sl.filter((l) => l.application_mode === "automatic").length;
  const dlpCount = sl.filter((l) => l.is_endpoint_protection_enabled).length;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Information Protection Labels</h2>

      {/* Sensitivity Labels stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Total Labels", value: sl.length, color: "text-sky-400" },
          { label: "Protected", value: protectedCount, color: "text-emerald-400" },
          { label: "Auto-Applied", value: autoCount, color: "text-amber-400" },
          { label: "Endpoint DLP", value: dlpCount, color: "text-rose-400" },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-navy-700 bg-navy-800/60 p-4 text-center">
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-xs text-navy-300">{stat.label}</p>
          </div>
        ))}
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
          Sensitivity Labels ({sl.length})
        </h3>
        <DataTable<SensitivityLabel & Record<string, unknown>>
          columns={[
            {
              key: "name",
              label: "Label",
              render: (v, row) => (
                <div className="flex items-center gap-2">
                  {row.color ? (
                    <span className="inline-block h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: row.color as string }} />
                  ) : (
                    <span className="inline-block h-3 w-3 shrink-0 rounded-full bg-navy-500" />
                  )}
                  <span className="font-medium">{String(v)}</span>
                </div>
              ),
            },
            { key: "priority", label: "Priority", render: (v) => `P${v}` },
            {
              key: "has_protection",
              label: "Protection",
              render: (v, row) => {
                if (!v) return <span className="text-navy-500">None</span>;
                return (
                  <div className="flex flex-wrap gap-1">
                    <span className="inline-block rounded px-2 py-0.5 text-xs font-semibold bg-emerald-600/20 text-emerald-400">
                      🔒 Encrypted
                    </span>
                    {row.is_endpoint_protection_enabled && (
                      <span className="inline-block rounded px-2 py-0.5 text-xs font-semibold bg-rose-600/20 text-rose-400">
                        DLP
                      </span>
                    )}
                  </div>
                );
              },
            },
            {
              key: "applicable_to",
              label: "Workloads",
              render: (v) => <WorkloadTags value={String(v ?? "")} />,
            },
            {
              key: "application_mode",
              label: "Mode",
              render: (v) => {
                const s = String(v || "manual");
                return (
                  <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${modeColors[s] ?? modeColors.manual}`}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </span>
                );
              },
            },
            { key: "tenant_name", label: "Tenant" },
          ]}
          data={sl as (SensitivityLabel & Record<string, unknown>)[]}
          keyField="label_id"
        />
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
          Retention Labels ({data.retention_labels.length})
        </h3>
        <DataTable<RetentionLabel & Record<string, unknown>>
          columns={[
            { key: "name", label: "Label" },
            {
              key: "is_in_use",
              label: "In Use",
              render: (v) => v ? "Yes" : "No",
            },
            { key: "retention_duration", label: "Duration" },
            {
              key: "action_after",
              label: "After Retention",
              render: (v) => {
                const s = String(v || "none");
                return s.charAt(0).toUpperCase() + s.slice(1);
              },
            },
            { key: "default_record_behavior", label: "Record Behavior" },
            { key: "tenant_name", label: "Tenant" },
          ]}
          data={data.retention_labels as (RetentionLabel & Record<string, unknown>)[]}
          keyField="label_id"
        />
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Retention Events ({data.retention_events.length})</h3>
        <DataTable<RetentionEvent & Record<string, unknown>>
          columns={[
            { key: "display_name", label: "Name" },
            { key: "event_type", label: "Type" },
            { key: "event_status", label: "Status" },
            { key: "created", label: "Created" },
            { key: "tenant_name", label: "Tenant" },
          ]}
          data={data.retention_events as (RetentionEvent & Record<string, unknown>)[]}
          keyField="event_id"
        />
      </div>
    </div>
  );
}

import { useTenant } from "../hooks/useTenant";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { LabelsResponse, SensitivityLabel, RetentionLabel, RetentionEvent } from "../types";

export default function Labels() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<LabelsResponse>("labels", body, [tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Information Protection Labels</h2>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Sensitivity Labels ({data.sensitivity_labels.length})</h3>
        <DataTable<SensitivityLabel & Record<string, unknown>>
          columns={[
            { key: "name", label: "Name" },
            { key: "priority", label: "Priority" },
            {
              key: "has_protection",
              label: "Protected",
              render: (v) => {
                return v ? (
                  <span className="inline-block rounded px-2 py-0.5 text-xs font-semibold bg-emerald-600/20 text-emerald-400">Yes</span>
                ) : (
                  <span className="inline-block rounded px-2 py-0.5 text-xs font-semibold bg-navy-600/20 text-navy-300">No</span>
                );
              },
            },
            { key: "applicable_to", label: "Applies To" },
            { key: "application_mode", label: "Mode" },
            { key: "is_active", label: "Active", render: (v) => (v ? "Yes" : "No") },
            { key: "tenant_name", label: "Tenant" },
          ]}
          data={data.sensitivity_labels as (SensitivityLabel & Record<string, unknown>)[]}
          keyField="label_id"
        />
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Retention Labels ({data.retention_labels.length})</h3>
        <DataTable<RetentionLabel & Record<string, unknown>>
          columns={[
            { key: "display_name", label: "Name" },
            { key: "retention_duration", label: "Duration" },
            { key: "retention_trigger", label: "Trigger" },
            { key: "action_after_retention", label: "Action" },
            { key: "status", label: "Status" },
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

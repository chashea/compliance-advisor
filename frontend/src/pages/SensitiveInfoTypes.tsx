import { useDepartment } from "../hooks/useDepartment";
import { useTenant } from "../hooks/useTenant";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import StatCard from "../components/StatCard";
import { useApi } from "../hooks/useApi";
import type { SensitiveInfoType, SensitiveInfoTypesResponse } from "../types";

export default function SensitiveInfoTypes() {
  const { department } = useDepartment();
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (department) body.department = department;
  if (tenantId) body.tenant_id = tenantId;
  const { data, loading, error } = useApi<SensitiveInfoTypesResponse>("sensitive-info-types", body, [department, tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Sensitive Information Types ({data.types.length})</h2>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard label="Total" value={data.types.length} accent="border-l-navy-600" />
        <StatCard label="Custom" value={data.custom_count} accent="border-l-gold-500" />
        <StatCard label="Built-in" value={data.builtin_count} accent="border-l-blue-500" />
      </div>

      <DataTable<SensitiveInfoType & Record<string, unknown>>
        columns={[
          { key: "name", label: "Name" },
          { key: "description", label: "Description" },
          {
            key: "is_custom",
            label: "Custom",
            render: (v) => <span>{v ? "Yes" : "No"}</span>,
          },
          { key: "category", label: "Category" },
          { key: "state", label: "State" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.types as (SensitiveInfoType & Record<string, unknown>)[]}
        keyField="type_id"
      />
    </div>
  );
}

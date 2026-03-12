import { useDepartment } from "../components/DepartmentContext";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { InfoBarrierPolicy, InfoBarriersResponse } from "../types";

export default function InfoBarriers() {
  const { department } = useDepartment();
  const { data, loading, error } = useApi<InfoBarriersResponse>("info-barriers", department ? { department } : {}, [department]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-800">Information Barriers ({data.policies.length})</h2>
      <DataTable<InfoBarrierPolicy & Record<string, unknown>>
        columns={[
          { key: "display_name", label: "Policy" },
          { key: "state", label: "State" },
          { key: "segments_applied", label: "Segments" },
          { key: "tenant_name", label: "Tenant" },
        ]}
        data={data.policies as (InfoBarrierPolicy & Record<string, unknown>)[]}
        keyField="policy_id"
      />
    </div>
  );
}

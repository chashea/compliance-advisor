import { useDepartment } from "../components/DepartmentContext";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import LineChart from "../components/LineChart";
import Loading from "../components/Loading";
import StatCard from "../components/StatCard";
import { useApi } from "../hooks/useApi";
import type { OverviewResponse, StatusResponse, TrendResponse, ActionsResponse, ImprovementAction } from "../types";

export default function Overview() {
  const { department } = useDepartment();
  const body = department ? { department } : {};

  const status = useApi<StatusResponse>("status", {}, []);
  const overview = useApi<OverviewResponse>("overview", body, [department]);
  const trend = useApi<TrendResponse>("trend", { ...body, days: 30 }, [department]);
  const actions = useApi<ActionsResponse>("actions", body, [department]);

  if (status.loading || overview.loading) return <Loading />;
  if (status.error) return <ErrorBanner message={status.error} />;
  if (overview.error) return <ErrorBanner message={overview.error} />;

  const s = status.data!;
  const o = overview.data!;
  const dlpData = o.dlp_summary
    ? [
        { severity: "High", count: o.dlp_summary.high_alerts },
        { severity: "Medium", count: o.dlp_summary.medium_alerts },
        { severity: "Low", count: (o.dlp_summary.total_dlp_alerts ?? 0) - (o.dlp_summary.high_alerts ?? 0) - (o.dlp_summary.medium_alerts ?? 0) },
      ].filter((d) => d.count > 0)
    : [];

  const score = actions.data?.secure_score;
  const dataPct = score?.data_max_score ? ((score.data_current_score / score.data_max_score) * 100).toFixed(0) : "0";

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-800">Overview</h2>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Active Tenants" value={s.active_tenants} sub={s.newest_sync ? `Last sync: ${s.newest_sync}` : undefined} />
        <StatCard label="eDiscovery Cases" value={o.ediscovery_summary?.total_cases ?? 0} sub={`${o.ediscovery_summary?.active_cases ?? 0} active`} />
        <StatCard label="Sensitivity Labels" value={o.labels_summary?.sensitivity_labels ?? 0} />
        <StatCard label="Retention Labels" value={o.labels_summary?.retention_labels ?? 0} />
        <StatCard label="DLP Alerts" value={o.dlp_summary?.total_dlp_alerts ?? 0} sub={`${o.dlp_summary?.active_alerts ?? 0} active`} />
        <StatCard label="Audit Records" value={o.audit_summary?.total_records ?? 0} />
      </div>

      {dlpData.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-slate-600">DLP Alerts by Severity</h3>
          <BarChart data={dlpData} xKey="severity" yKey="count" color="#ef4444" height={250} />
        </div>
      )}

      {trend.data && trend.data.trend.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-slate-600">30-Day Trend</h3>
          <LineChart
            data={trend.data.trend}
            xKey="snapshot_date"
            series={[
              { key: "ediscovery_cases", color: "#3b82f6", label: "eDiscovery" },
              { key: "dlp_alerts", color: "#ef4444", label: "DLP" },
              { key: "sensitivity_labels", color: "#10b981", label: "Sensitivity" },
              { key: "audit_records", color: "#f59e0b", label: "Audit" },
            ]}
            height={300}
          />
        </div>
      )}

      {actions.data && (
        <>
          <h3 className="text-lg font-semibold text-slate-800">Secure Score & Improvement Actions</h3>

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="Data Category" value={`${dataPct}%`} />
            <StatCard label="Actions" value={actions.data.actions.length} />
          </div>

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
            data={actions.data.actions as (ImprovementAction & Record<string, unknown>)[]}
            keyField="control_id"
          />
        </>
      )}
    </div>
  );
}

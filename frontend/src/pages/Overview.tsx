import { useTenant } from "../hooks/useTenant";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import LineChart from "../components/LineChart";
import Loading from "../components/Loading";
import StatCard from "../components/StatCard";
import { useApi } from "../hooks/useApi";
import type { OverviewResponse, StatusResponse, TrendResponse, ActionsResponse, ImprovementAction } from "../types";

export default function Overview() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;

  const status = useApi<StatusResponse>("status", {}, []);
  const overview = useApi<OverviewResponse>("overview", body, [tenantId]);
  const trend = useApi<TrendResponse>("trend", { ...body, days: 30 }, [tenantId]);
  const actions = useApi<ActionsResponse>("actions", body, [tenantId]);

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
      <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Overview</h2>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Active Tenants" value={s.active_tenants} sub={s.newest_sync ? `Last sync: ${s.newest_sync}` : undefined} accent="border-l-navy-700" />
        <StatCard label="eDiscovery Cases" value={o.ediscovery_summary?.total_cases ?? 0} sub={`${o.ediscovery_summary?.active_cases ?? 0} active`} accent="border-l-teal-600" />
        <StatCard label="Sensitivity Labels" value={o.labels_summary?.sensitivity_labels ?? 0} accent="border-l-gold-500" />
        <StatCard label="Retention Labels" value={o.labels_summary?.retention_labels ?? 0} accent="border-l-gold-500" />
        <StatCard label="DLP Alerts" value={o.dlp_summary?.total_dlp_alerts ?? 0} sub={`${o.dlp_summary?.active_alerts ?? 0} active`} accent="border-l-red-600" />
        <StatCard label="Audit Records" value={o.audit_summary?.total_records ?? 0} accent="border-l-navy-500" />
      </div>

      {dlpData.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">DLP Alerts by Severity</h3>
          <DataTable<{ severity: string; count: number } & Record<string, unknown>>
            columns={[
              { key: "severity", label: "Severity" },
              { key: "count", label: "Count" },
            ]}
            data={dlpData as ({ severity: string; count: number } & Record<string, unknown>)[]}
            keyField="severity"
          />
        </div>
      )}

      {trend.data && trend.data.trend.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">30-Day Trend</h3>
          <LineChart
            data={trend.data.trend}
            xKey="snapshot_date"
            series={[
              { key: "ediscovery_cases", color: "#4a90d9", label: "eDiscovery" },
              { key: "dlp_alerts", color: "#dc2626", label: "DLP" },
              { key: "sensitivity_labels", color: "#14b8a6", label: "Sensitivity" },
              { key: "audit_records", color: "#b8860b", label: "Audit" },
            ]}
            height={300}
          />
        </div>
      )}

      {actions.data && (
        <>
          <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100">Secure Score & Improvement Actions</h3>

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="Data Secure Score" value={`${dataPct}%`} accent="border-l-gold-500" />
            <StatCard label="Actions" value={actions.data.actions.length} accent="border-l-navy-500" />
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

import { useState } from "react";
import { useTenant } from "../hooks/useTenant";
import ActionDrawer from "../components/ActionDrawer";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import KPICard from "../components/KPICard";
import LineChart from "../components/LineChart";
import Loading from "../components/Loading";
import ScoreGauge from "../components/ScoreGauge";
import TenantCard from "../components/TenantCard";
import { useApi } from "../hooks/useApi";
import type {
  OverviewResponse,
  StatusResponse,
  TrendResponse,
  ActionsResponse,
  ImprovementAction,
} from "../types";

/* ── tiny SVG icons for KPI cards ─────────────────────────────────── */
const IconSearch = (
  <svg className="h-5 w-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
  </svg>
);
const IconShield = (
  <svg className="h-5 w-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);
const IconTag = (
  <svg className="h-5 w-5 text-gold-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5a1.99 1.99 0 011.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.99 1.99 0 013 12V7a4 4 0 014-4z" />
  </svg>
);
const IconAlert = (
  <svg className="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
  </svg>
);
const IconClipboard = (
  <svg className="h-5 w-5 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
  </svg>
);
const IconUsers = (
  <svg className="h-5 w-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m9.12 0a4 4 0 10-5.24 0M12 14a4 4 0 100-8 4 4 0 000 8z" />
  </svg>
);

/* ── helpers ──────────────────────────────────────────────────────── */
function fmtNum(n: number): string {
  if (n >= 10_000) return `${(n / 1000).toFixed(1)}K`;
  if (n >= 1_000) return n.toLocaleString();
  return String(n);
}

/* ── page ─────────────────────────────────────────────────────────── */
export default function Overview() {
  const { tenantId } = useTenant();
  const [selectedAction, setSelectedAction] = useState<ImprovementAction | null>(null);
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
  const score = actions.data?.secure_score;
  const dataPct = score?.data_max_score
    ? Math.round((score.data_current_score / score.data_max_score) * 100)
    : 0;
  const dlpHigh = o.dlp_summary?.high_alerts ?? 0;
  const dlpMed = o.dlp_summary?.medium_alerts ?? 0;

  return (
    <div className="space-y-6">
      {/* ── Page header ────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">
            Compliance Posture Overview
          </h2>
          <p className="text-sm text-navy-300">
            Real-time visibility across {s.active_tenants} tenant{s.active_tenants !== 1 && "s"}
            {s.newest_sync && (
              <> &middot; Last updated: {new Date(s.newest_sync).toLocaleString()}</>
            )}
          </p>
        </div>
        <button
          onClick={() => overview.refetch()}
          className="rounded-lg border border-navy-600 px-4 py-2 text-sm font-medium text-navy-200 hover:bg-navy-700 transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {/* ── Alert banner (DLP high alerts) ─────────────────────────── */}
      {dlpHigh > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-amber-600/40 bg-amber-900/20 px-5 py-3">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-500/20">
              <svg className="h-5 w-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
            </span>
            <div>
              <p className="text-sm font-semibold text-amber-300">
                {dlpHigh} high-severity DLP alert{dlpHigh !== 1 && "s"} requiring attention
              </p>
              <p className="text-xs text-amber-400/70">
                {dlpMed} medium-severity alert{dlpMed !== 1 && "s"} also active
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Hero row: Score gauge + KPI cards ──────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-4">
        {/* Score gauge card */}
        <div className="flex flex-col items-center justify-center rounded-xl border border-navy-700 bg-navy-800/60 p-6 lg:col-span-1">
          {score ? (
            <ScoreGauge
              score={score.data_current_score}
              max={score.data_max_score}
              label="Compliance Score"
            />
          ) : (
            <ScoreGauge score={0} max={100} label="Compliance Score" />
          )}
        </div>

        {/* KPI grid — 2 rows × 3 columns */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:col-span-3">
          <KPICard
            icon={IconSearch}
            iconBg="bg-teal-600/20"
            value={o.ediscovery_summary?.total_cases ?? 0}
            label="eDiscovery Cases"
            delta={`${o.ediscovery_summary?.active_cases ?? 0} active`}
            deltaUp
          />
          <KPICard
            icon={IconAlert}
            iconBg="bg-red-600/20"
            value={o.dlp_summary?.total_dlp_alerts ?? 0}
            label="DLP Alerts"
            delta={`${dlpHigh} high`}
            deltaUp={false}
          />
          <KPICard
            icon={IconUsers}
            iconBg="bg-emerald-600/20"
            value={s.active_tenants}
            label="Active Tenants"
          />
          <KPICard
            icon={IconTag}
            iconBg="bg-gold-500/20"
            value={o.labels_summary?.sensitivity_labels ?? 0}
            label="Sensitivity Labels"
          />
          <KPICard
            icon={IconShield}
            iconBg="bg-gold-500/20"
            value={o.labels_summary?.retention_labels ?? 0}
            label="Retention Labels"
          />
          <KPICard
            icon={IconClipboard}
            iconBg="bg-sky-600/20"
            value={fmtNum(o.audit_summary?.total_records ?? 0)}
            label="Audit Records"
          />
        </div>
      </div>

      {/* ── Secure Score detail row ────────────────────────────────── */}
      {score && (
        <div className="grid gap-4 lg:grid-cols-3">
          {/* Overall Secure Score card */}
          <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
            <div className="mb-1 flex items-center gap-2">
              <span className="h-3 w-3 rounded-sm bg-sky-500" />
              <span className="text-sm font-semibold text-navy-200">
                Compliance Score
              </span>
            </div>
            <p className="mt-2 text-4xl font-bold text-white">
              {score.data_current_score}
            </p>
            <p className="text-sm text-navy-400">
              of {score.data_max_score} points
            </p>
            <p className="mt-1 text-2xl font-semibold text-white">
              {score.data_max_score > 0
                ? Math.round((score.data_current_score / score.data_max_score) * 100)
                : 0}
              %
            </p>
            {/* Progress bars */}
            <div className="mt-4 space-y-3">
              <div>
                <div className="flex justify-between text-xs text-navy-300">
                  <span>Data category controls</span>
                  <span>{score.data_current_score}/{score.data_max_score}</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-navy-700">
                  <div
                    className="h-2 rounded-full bg-teal-500 transition-all duration-700"
                    style={{
                      width: `${score.data_max_score > 0 ? (score.data_current_score / score.data_max_score) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs text-navy-300">
                  <span>Overall score</span>
                  <span>{score.current_score}/{score.max_score}</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-navy-700">
                  <div
                    className="h-2 rounded-full bg-sky-500 transition-all duration-700"
                    style={{
                      width: `${score.max_score > 0 ? (score.current_score / score.max_score) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Tenant posture cards ───────────────────────────────────── */}
      {o.tenants && o.tenants.length > 1 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-navy-300">
            Tenant Posture
          </h3>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {o.tenants.map((t) => (
              <TenantCard
                key={t.tenant_id}
                name={t.display_name}
                badge={t.department}
                metrics={[
                  { label: "Department", value: t.department, color: "text-teal-400" },
                ]}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── 30-Day Trend chart ─────────────────────────────────────── */}
      {trend.data && trend.data.trend.length > 0 && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <h3 className="mb-4 text-sm font-semibold text-navy-200">
            30-Day Compliance Trend
          </h3>
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

      {/* ── Improvement Actions table ──────────────────────────────── */}
      {actions.data && actions.data.actions.length > 0 && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <h3 className="mb-4 text-sm font-semibold text-navy-200">
            Improvement Actions
            <span className="ml-2 text-xs font-normal text-navy-400">
              {actions.data.actions.length} actions &middot; {dataPct}% Data score
            </span>
          </h3>
          <DataTable<ImprovementAction & Record<string, unknown>>
            columns={[
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
            onRowClick={(row) => setSelectedAction(row as unknown as ImprovementAction)}
          />
        </div>
      )}

      {selectedAction && (
        <ActionDrawer action={selectedAction} onClose={() => setSelectedAction(null)} />
      )}
    </div>
  );
}

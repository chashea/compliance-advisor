import { useState } from "react";
import { useTenant } from "../hooks/useTenant";
import ActionDrawer from "../components/ActionDrawer";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import KPICard from "../components/KPICard";
import Loading from "../components/Loading";
import ScoreGauge from "../components/ScoreGauge";
import TenantCard from "../components/TenantCard";
import { useApi } from "../hooks/useApi";
import type {
  OverviewResponse,
  StatusResponse,
  ActionsResponse,
  ImprovementAction,
} from "../types";

/* ── tiny SVG icons for KPI cards ─────────────────────────────────── */
const IconSearch = (
  <svg className="h-5 w-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
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
const IconThreat = (
  <svg className="h-5 w-5 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.75c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.57-.598-3.75h-.152c-3.196 0-6.1-1.25-8.25-3.286zM12 15.75h.007v.008H12v-.008z" />
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
  const threatTotal = o.threat_summary?.total_requests ?? 0;
  const threatPhishing = o.threat_summary?.phishing ?? 0;

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
        {/* Combined Compliance Score card */}
        <div className="flex items-center gap-6 rounded-xl border border-navy-700 bg-navy-800/60 p-6 lg:col-span-1">
          <div className="shrink-0">
            {score ? (
              <ScoreGauge
                score={score.data_current_score}
                max={score.data_max_score}
                label="Compliance Score"
                size={140}
              />
            ) : (
              <ScoreGauge score={0} max={100} label="Compliance Score" size={140} />
            )}
          </div>
          {score && (
            <div className="min-w-0 flex-1 space-y-3">
              <div>
                <div className="flex justify-between text-xs text-navy-300">
                  <span>Data controls</span>
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
                  <span>Overall</span>
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
            delta={`${o.labels_summary?.protected_labels ?? 0} protected`}
            deltaUp
          />
          <KPICard
            icon={IconClipboard}
            iconBg="bg-sky-600/20"
            value={fmtNum(o.audit_summary?.total_records ?? 0)}
            label="Audit Records"
          />
          <KPICard
            icon={IconThreat}
            iconBg="bg-rose-600/20"
            value={threatTotal}
            label="Threat Reports"
            delta={threatPhishing > 0 ? `${threatPhishing} phishing` : undefined}
            deltaUp={false}
          />
        </div>
      </div>

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
              {
                key: "max_score",
                label: "Score Impact",
                render: (v) => `+${v} pts`,
              },
              {
                key: "current_score",
                label: "Points Achieved",
                render: (v, row) => {
                  const cur = v as number;
                  const max = row.max_score as number;
                  return `${cur} / ${max}`;
                },
              },
              {
                key: "state",
                label: "Status",
                render: (v) => {
                  const s = String(v);
                  const colors: Record<string, string> = {
                    Completed: "bg-emerald-600/20 text-emerald-400",
                    InProgress: "bg-amber-600/20 text-amber-400",
                  };
                  const label = s === "InProgress" ? "In Progress" : s || "Not Started";
                  return (
                    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${colors[s] ?? "bg-navy-600/20 text-navy-300"}`}>
                      {label}
                    </span>
                  );
                },
              },
              { key: "implementation_cost", label: "Cost" },
              { key: "user_impact", label: "Impact" },
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

import { useState } from "react";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import Loading from "../components/Loading";
import { useTenant } from "../hooks/useTenant";
import { useApi } from "../hooks/useApi";
import type { HuntFinding, HuntResultsResponse, HuntRun } from "../types";

const SEVERITY_COLORS: Record<string, string> = {
  high: "bg-red-500/20 text-red-400",
  medium: "bg-amber-500/20 text-amber-400",
  low: "bg-sky-500/20 text-sky-400",
  info: "bg-navy-600/40 text-navy-300",
};

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_COLORS[severity] ?? SEVERITY_COLORS.info}`}>
      {severity}
    </span>
  );
}

function SummaryCards({ summary }: { summary: HuntResultsResponse["summary"] }) {
  const cards = [
    { label: "Total Findings", value: summary.total, color: "text-white" },
    { label: "High", value: summary.high, color: "text-red-400" },
    { label: "Medium", value: summary.medium, color: "text-amber-400" },
    { label: "Low", value: summary.low, color: "text-sky-400" },
  ];
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-navy-400">{c.label}</p>
          <p className={`mt-1 text-2xl font-bold ${c.color}`}>{c.value}</p>
        </div>
      ))}
    </div>
  );
}

function NarrativeCard({ run }: { run: HuntRun }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-xl border border-navy-700 bg-navy-800/60 p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">
            {run.template_name ? `Template: ${run.template_name}` : run.question ?? "Hunt Run"}
          </h3>
          <p className="mt-0.5 text-xs text-navy-400">
            {new Date(run.run_at).toLocaleString()} | {run.result_count} results
          </p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-gold-400 hover:text-gold-300"
        >
          {expanded ? "Collapse" : "View Analysis"}
        </button>
      </div>
      {expanded && run.ai_narrative && (
        <div className="mt-3 whitespace-pre-wrap rounded-lg bg-navy-900 p-4 text-sm text-navy-200">
          {run.ai_narrative}
        </div>
      )}
    </div>
  );
}

export default function ThreatHunting() {
  const { tenantId } = useTenant();
  const body: Record<string, unknown> = {};
  if (tenantId) body.tenant_id = tenantId;

  const { data, loading, error } = useApi<HuntResultsResponse>("hunt-results", body, [tenantId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white">Threat Hunting</h2>

      <SummaryCards summary={data.summary} />

      {data.recent_runs.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-navy-400">Recent Hunt Runs</h3>
          {data.recent_runs.map((run) => (
            <NarrativeCard key={run.id} run={run} />
          ))}
        </div>
      )}

      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-navy-400">Findings</h3>
        <DataTable<HuntFinding & Record<string, unknown>>
          columns={[
            {
              key: "severity",
              label: "Severity",
              render: (v) => <SeverityBadge severity={String(v)} />,
            },
            { key: "finding_type", label: "Finding" },
            { key: "account_upn", label: "User" },
            { key: "object_name", label: "Object" },
            { key: "action_type", label: "Action" },
            {
              key: "detected_at",
              label: "Detected",
              render: (v) => (v ? new Date(String(v)).toLocaleString() : ""),
            },
          ]}
          data={data.results as (HuntFinding & Record<string, unknown>)[]}
          keyField="id"
        />
      </div>
    </div>
  );
}

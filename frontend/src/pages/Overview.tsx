import { useState } from "react";
import { useDepartment } from "../components/DepartmentContext";
import BarChart from "../components/BarChart";
import DataTable from "../components/DataTable";
import ErrorBanner from "../components/ErrorBanner";
import LineChart from "../components/LineChart";
import Loading from "../components/Loading";
import StatCard from "../components/StatCard";
import { useApi } from "../hooks/useApi";
import { post } from "../api/client";
import type { OverviewResponse, StatusResponse, TrendResponse, ActionsResponse, ImprovementAction, AskResponse } from "../types";

interface QAPair {
  question: string;
  answer: string;
}

export default function Overview() {
  const { department } = useDepartment();
  const body = department ? { department } : {};

  const status = useApi<StatusResponse>("status", {}, []);
  const overview = useApi<OverviewResponse>("overview", body, [department]);
  const trend = useApi<TrendResponse>("trend", { ...body, days: 30 }, [department]);
  const actions = useApi<ActionsResponse>("actions", body, [department]);

  const [question, setQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [history, setHistory] = useState<QAPair[]>([]);

  async function askQuestion(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setAskLoading(true);
    setAskError(null);
    try {
      const res = await post<AskResponse>("ask", { question: q, ...(department ? { department } : {}) });
      setHistory((prev) => [...prev, { question: q, answer: res.answer }]);
      setQuestion("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to get answer";
      setAskError(msg.includes("429") ? "Rate limit reached. Please wait a moment and try again." : msg);
    } finally {
      setAskLoading(false);
    }
  }

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
  const pct = score?.max_score ? ((score.current_score / score.max_score) * 100).toFixed(0) : "0";
  const dataPct = score?.data_max_score ? ((score.data_current_score / score.data_max_score) * 100).toFixed(0) : "0";

  return (
    <div className="flex gap-6">
    <div className="min-w-0 flex-1 space-y-6">
      <h2 className="text-xl font-semibold text-slate-800">Overview</h2>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Active Tenants" value={s.active_tenants} sub={s.newest_sync ? `Last sync: ${s.newest_sync}` : undefined} />
        <StatCard label="eDiscovery Cases" value={o.ediscovery_summary?.total_cases ?? 0} sub={`${o.ediscovery_summary?.active_cases ?? 0} active`} />
        <StatCard label="Sensitivity Labels" value={o.labels_summary?.sensitivity_labels ?? 0} />
        <StatCard label="Retention Labels" value={o.labels_summary?.retention_labels ?? 0} />
        <StatCard label="DLP Alerts" value={o.dlp_summary?.total_dlp_alerts ?? 0} sub={`${o.dlp_summary?.active_alerts ?? 0} active`} />
        <StatCard label="Audit Records" value={o.audit_summary?.total_records ?? 0} />
        {score && (
          <>
            <StatCard label="Overall Score" value={`${pct}%`} />
            <StatCard label="Data Category" value={`${dataPct}%`} />
          </>
        )}
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
            <StatCard label="Score Date" value={score?.score_date ?? "N/A"} />
            <StatCard label="Actions" value={actions.data.actions.length} />
          </div>

          {actions.data.category_breakdown.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-medium text-slate-600">By Category</h3>
              <BarChart data={actions.data.category_breakdown} xKey="control_category" yKey="total" color="#6366f1" height={250} />
            </div>
          )}

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

    {/* Ask AI Sidebar */}
    <aside className="hidden w-80 shrink-0 lg:block">
      <div className="sticky top-0 rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-700">Ask AI</h3>
        <form onSubmit={askQuestion} className="space-y-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about your compliance data..."
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={askLoading}
          />
          <button
            type="submit"
            disabled={askLoading || !question.trim()}
            className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {askLoading ? "Thinking..." : "Ask"}
          </button>
        </form>
        {askError && <div className="mt-2"><ErrorBanner message={askError} /></div>}
        {askLoading && <Loading />}
        {history.length > 0 && (
          <div className="mt-3 max-h-[60vh] space-y-3 overflow-y-auto">
            {history.map((qa, i) => (
              <div key={i} className="rounded-md border border-slate-100 bg-slate-50 p-3">
                <p className="mb-1 text-xs font-medium text-slate-700">Q: {qa.question}</p>
                <div className="whitespace-pre-wrap text-xs text-slate-600">{qa.answer}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
    </div>
  );
}

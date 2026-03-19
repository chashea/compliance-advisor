import { useState } from "react";
import { useDepartment } from "../components/DepartmentContext";
import ErrorBanner from "../components/ErrorBanner";
import LineChart from "../components/LineChart";
import Loading from "../components/Loading";
import { useApi } from "../hooks/useApi";
import type { TrendResponse } from "../types";

const RANGES = [7, 30, 90, 365] as const;

export default function Trend() {
  const { department } = useDepartment();
  const [days, setDays] = useState<number>(30);
  const body = { ...(department ? { department } : {}), days };
  const { data, loading, error } = useApi<TrendResponse>("trend", body, [department, days]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-100">Compliance Trend</h2>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setDays(r)}
              className={`rounded px-3 py-1 text-sm ${days === r ? "bg-blue-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"}`}
            >
              {r}d
            </button>
          ))}
        </div>
      </div>

      <LineChart
        data={data.trend}
        xKey="snapshot_date"
        series={[
          { key: "ediscovery_cases", color: "#3b82f6", label: "eDiscovery" },
          { key: "sensitivity_labels", color: "#10b981", label: "Sensitivity Labels" },
          { key: "retention_labels", color: "#8b5cf6", label: "Retention Labels" },
          { key: "dlp_alerts", color: "#ef4444", label: "DLP Alerts" },
          { key: "audit_records", color: "#f59e0b", label: "Audit Records" },
          { key: "tenant_count", color: "#6366f1", label: "Tenants" },
        ]}
        height={500}
      />
    </div>
  );
}

import { useState } from "react";
import { useDepartment } from "../hooks/useDepartment";
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
        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Compliance Trend</h2>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setDays(r)}
              className={`rounded px-3 py-1 text-sm ${days === r ? "bg-navy-900 text-white" : "bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700"}`}
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
          { key: "ediscovery_cases", color: "#4a90d9", label: "eDiscovery" },
          { key: "sensitivity_labels", color: "#14b8a6", label: "Sensitivity Labels" },
          { key: "retention_labels", color: "#829ab1", label: "Retention Labels" },
          { key: "dlp_alerts", color: "#dc2626", label: "DLP Alerts" },
          { key: "audit_records", color: "#b8860b", label: "Audit Records" },
          { key: "tenant_count", color: "#bcccdc", label: "Tenants" },
        ]}
        height={500}
      />
    </div>
  );
}

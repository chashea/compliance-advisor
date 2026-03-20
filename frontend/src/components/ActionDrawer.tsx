import { useEffect, useState } from "react";
import type { ImprovementAction } from "../types";

interface Props {
  action: ImprovementAction;
  onClose: () => void;
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${color}`}>
      {label}
    </span>
  );
}

function stateBadge(state: string) {
  switch (state) {
    case "Completed":
      return <Badge label="Completed" color="bg-emerald-600/20 text-emerald-400" />;
    case "InProgress":
      return <Badge label="In Progress" color="bg-amber-600/20 text-amber-400" />;
    default:
      return <Badge label={state || "Not Started"} color="bg-navy-600/20 text-navy-300" />;
  }
}

function costBadge(cost: string) {
  const colors: Record<string, string> = {
    Low: "bg-emerald-600/20 text-emerald-400",
    Moderate: "bg-amber-600/20 text-amber-400",
    High: "bg-red-600/20 text-red-400",
  };
  return <Badge label={cost} color={colors[cost] ?? "bg-navy-600/20 text-navy-300"} />;
}

export default function ActionDrawer({ action, onClose }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setOpen(true));
  }, []);

  function handleClose() {
    setOpen(false);
    setTimeout(onClose, 300);
  }

  const scorePct =
    action.max_score > 0
      ? Math.round((action.current_score / action.max_score) * 100)
      : 0;

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-black/20 transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0"}`}
        onClick={handleClose}
      />
      <div
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col bg-white shadow-xl transition-transform duration-300 ease-out dark:bg-slate-900 ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between bg-navy-900 px-5 py-4">
          <h2 className="text-lg font-semibold text-white">Action Details</h2>
          <button onClick={handleClose} className="text-navy-300 hover:text-white">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          {/* Title + State */}
          <div>
            <div className="mb-2 flex items-center gap-2">
              {stateBadge(action.state)}
              <span className="text-xs text-navy-400">#{action.rank}</span>
            </div>
            <h3 className="text-lg font-bold text-white">{action.title}</h3>
            <p className="mt-1 text-sm text-navy-400">{action.control_id}</p>
          </div>

          {/* Score bar */}
          <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-navy-200">Score</span>
              <span className="text-sm font-bold text-white">
                {action.current_score} / {action.max_score} ({scorePct}%)
              </span>
            </div>
            <div className="h-2.5 rounded-full bg-navy-700">
              <div
                className="h-2.5 rounded-full bg-teal-500 transition-all duration-700"
                style={{ width: `${scorePct}%` }}
              />
            </div>
          </div>

          {/* Metadata grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-3">
              <p className="text-xs text-navy-400">Category</p>
              <p className="mt-1 text-sm font-semibold text-white">{action.control_category}</p>
            </div>
            <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-3">
              <p className="text-xs text-navy-400">Service</p>
              <p className="mt-1 text-sm font-semibold text-white">{action.service}</p>
            </div>
            <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-3">
              <p className="text-xs text-navy-400">Implementation Cost</p>
              <div className="mt-1">{costBadge(action.implementation_cost)}</div>
            </div>
            <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-3">
              <p className="text-xs text-navy-400">User Impact</p>
              <div className="mt-1">{costBadge(action.user_impact)}</div>
            </div>
            <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-3">
              <p className="text-xs text-navy-400">Tier</p>
              <p className="mt-1 text-sm font-semibold text-white">{action.tier}</p>
            </div>
            <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-3">
              <p className="text-xs text-navy-400">Tenant</p>
              <p className="mt-1 text-sm font-semibold text-white">{action.tenant_name}</p>
            </div>
          </div>

          {/* Threats */}
          {action.threats && (
            <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-navy-400">
                Threats Addressed
              </p>
              <p className="text-sm leading-relaxed text-navy-200">{action.threats}</p>
            </div>
          )}

          {/* Remediation */}
          {action.remediation && (
            <div className="rounded-lg border border-navy-700 bg-navy-800/60 p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-navy-400">
                Remediation Steps
              </p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-navy-200">
                {action.remediation}
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

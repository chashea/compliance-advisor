import type { ReactNode } from "react";

interface Props {
  icon: ReactNode;
  iconBg?: string;
  value: string | number;
  label: string;
  delta?: string;
  deltaUp?: boolean;
}

export default function KPICard({
  icon,
  iconBg = "bg-navy-700",
  value,
  label,
  delta,
  deltaUp,
}: Props) {
  return (
    <div className="flex flex-col justify-between rounded-xl border border-navy-700 bg-navy-800/60 p-5">
      <div className="flex items-start justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${iconBg}`}>
          {icon}
        </div>
        {delta && (
          <span
            className={`text-xs font-medium ${deltaUp ? "text-emerald-400" : "text-red-400"}`}
          >
            {deltaUp ? "↑" : "↓"} {delta}
          </span>
        )}
      </div>
      <div className="mt-4">
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-sm text-navy-300">{label}</p>
      </div>
    </div>
  );
}

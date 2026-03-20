interface Props {
  name: string;
  badge?: string;
  score?: number;
  maxScore?: number;
  metrics: { label: string; value: string | number; color?: string }[];
}

export default function TenantCard({ name, badge, score, maxScore, metrics }: Props) {
  const pct = maxScore && maxScore > 0 ? Math.round(((score ?? 0) / maxScore) * 100) : null;

  return (
    <div className="min-w-[260px] rounded-xl border border-navy-700 bg-navy-800/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-white">{name}</p>
          {badge && (
            <span className="mt-0.5 inline-block rounded bg-teal-600/30 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-teal-400">
              {badge}
            </span>
          )}
        </div>
        {pct !== null && (
          <span className="text-2xl font-bold text-white">{pct}</span>
        )}
      </div>
      <div className="flex gap-4">
        {metrics.map((m) => (
          <div key={m.label} className="text-center">
            <p className={`text-sm font-bold ${m.color ?? "text-navy-200"}`}>
              {m.value}
            </p>
            <p className="text-[10px] uppercase text-navy-400">{m.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

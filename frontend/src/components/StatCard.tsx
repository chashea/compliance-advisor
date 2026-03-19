interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}

export default function StatCard({ label, value, sub, accent = "border-l-navy-600" }: Props) {
  return (
    <div className={`rounded-lg border border-slate-200 dark:border-slate-700 border-l-4 ${accent} bg-white dark:bg-slate-900 p-4 shadow-sm`}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{sub}</p>}
    </div>
  );
}

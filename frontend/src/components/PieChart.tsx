import { Cell, Pie, PieChart as RePieChart, ResponsiveContainer, Tooltip, Legend } from "recharts";

const COLORS = ["#1a365d", "#0d9488", "#b8860b", "#dc2626", "#627d98", "#486581", "#9fb3c8"];

interface Props {
  data: { name: string; value: number }[];
  height?: number;
}

export default function PieChart({ data, height = 300 }: Props) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
      <ResponsiveContainer width="100%" height={height}>
        <RePieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </RePieChart>
      </ResponsiveContainer>
    </div>
  );
}

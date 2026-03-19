import { Cell, Pie, PieChart as RePieChart, ResponsiveContainer, Tooltip, Legend } from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#6366f1", "#ec4899"];

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

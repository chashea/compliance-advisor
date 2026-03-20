import {
  CartesianGrid,
  Legend,
  Line,
  LineChart as ReLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTheme } from "../hooks/useTheme";

interface Series {
  key: string;
  color: string;
  label?: string;
}

interface Props {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  xKey: string;
  series: Series[];
  height?: number;
}

export default function LineChart({ data, xKey, series, height = 300 }: Props) {
  const { dark } = useTheme();

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
      <ResponsiveContainer width="100%" height={height}>
        <ReLineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={dark ? "#334155" : "#e2e8f0"} />
          <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label ?? s.key}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </ReLineChart>
      </ResponsiveContainer>
    </div>
  );
}

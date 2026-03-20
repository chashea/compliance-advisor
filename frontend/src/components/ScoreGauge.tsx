interface Props {
  score: number;
  max: number;
  label?: string;
  size?: number;
}

export default function ScoreGauge({ score, max, label = "Compliance Score", size = 180 }: Props) {
  const pct = max > 0 ? Math.round((score / max) * 100) : 0;
  const r = (size - 20) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  const cx = size / 2;
  const cy = size / 2;

  // Color based on score
  const color = pct >= 80 ? "#14b8a6" : pct >= 50 ? "#d4a017" : "#dc2626";

  return (
    <div className="flex flex-col items-center">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-navy-300">
        {label}
      </p>
      <svg width={size} height={size} className="drop-shadow-lg">
        {/* Background ring */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="currentColor"
          className="text-navy-800"
          strokeWidth="12"
        />
        {/* Score arc */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${cx} ${cy})`}
          className="transition-all duration-1000 ease-out"
        />
        {/* Center text */}
        <text
          x={cx}
          y={cy - 8}
          textAnchor="middle"
          className="fill-white text-4xl font-bold"
          style={{ fontSize: size * 0.22 }}
        >
          {pct}
        </text>
        <text
          x={cx}
          y={cy + 14}
          textAnchor="middle"
          className="fill-navy-300 text-sm"
          style={{ fontSize: size * 0.08 }}
        >
          of 100
        </text>
      </svg>
      <div className="mt-3 flex items-center gap-3 text-xs text-navy-300">
        <span>
          <span className="font-semibold text-white">{score}</span> / {max} pts
        </span>
      </div>
    </div>
  );
}

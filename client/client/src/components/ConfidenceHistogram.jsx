import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts"

function bucketize(confidences) {
  const buckets = [
    { range: "0-20", min: 0, max: 0.2, count: 0 },
    { range: "20-40", min: 0.2, max: 0.4, count: 0 },
    { range: "40-60", min: 0.4, max: 0.6, count: 0 },
    { range: "60-80", min: 0.6, max: 0.8, count: 0 },
    { range: "80-100", min: 0.8, max: 1.01, count: 0 },
  ]
  for (const c of confidences) {
    for (const b of buckets) {
      if (c >= b.min && c < b.max) { b.count++; break }
    }
  }
  return buckets
}

const COLORS = ["#555555", "#b36b00", "#ff9800", "#00c853", "#00e676"]

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { range, count } = payload[0].payload
  return (
    <div className="border border-border bg-[#111] px-2 py-1 text-[10px]">
      <span className="text-amber">{range}%</span>
      <span className="ml-1 tabular text-foreground">n={count}</span>
    </div>
  )
}

export default function ConfidenceHistogram({ confidences }) {
  const data = bucketize(confidences)
  const total = confidences.length
  const mean = total > 0
    ? (confidences.reduce((a, b) => a + b, 0) / total * 100).toFixed(1)
    : "—"

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Confidence
        </span>
        <span className="tabular text-[10px]">
          <span className="text-muted-foreground">μ=</span>
          <span className="text-amber">{mean}%</span>
          <span className="text-muted-foreground ml-1">n={total}</span>
        </span>
      </div>
      <div className="flex-1 p-1">
        {total === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            No data<span className="blink">_</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#1a1a1a" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="range"
                tick={{ fontSize: 8, fill: "#666" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                width={20}
                tick={{ fontSize: 9, fill: "#666" }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="count" isAnimationActive={false} radius={0}>
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

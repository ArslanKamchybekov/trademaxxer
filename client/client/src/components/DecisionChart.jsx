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

const COLORS = { YES: "#00c853", NO: "#ff1744", SKIP: "#555555" }

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0].payload
  return (
    <div className="border border-border bg-[#111] px-2 py-1 text-[10px]">
      <span style={{ color: COLORS[name] }}>{name}</span>
      <span className="ml-1 tabular text-foreground">{value}</span>
    </div>
  )
}

export default function DecisionChart({ stats }) {
  const data = [
    { name: "YES", value: stats.yes },
    { name: "NO", value: stats.no },
    { name: "SKIP", value: stats.skip },
  ]

  const total = stats.yes + stats.no + stats.skip

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Distribution
        </span>
        {total > 0 && (
          <span className="ml-2 tabular text-[10px] text-muted-foreground">
            n={total}
          </span>
        )}
      </div>
      <div className="flex-1 p-1">
        {total === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            No signals<span className="blink">_</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#1a1a1a" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 9, fill: "#666" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                width={24}
                tick={{ fontSize: 9, fill: "#666" }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="value" isAnimationActive={false} radius={0}>
                {data.map((entry) => (
                  <Cell key={entry.name} fill={COLORS[entry.name]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

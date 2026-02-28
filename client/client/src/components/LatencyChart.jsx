import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts"

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  return (
    <div className="border border-border bg-[#111] px-2 py-1 text-[10px]">
      <span className="tabular text-amber">{payload[0].value}ms</span>
    </div>
  )
}

export default function LatencyChart({ data }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Latency
        </span>
        {data.length > 0 && (
          <span className="ml-2 tabular text-[10px] text-muted-foreground">
            last {data[data.length - 1].ms}ms
          </span>
        )}
      </div>
      <div className="flex-1 p-1">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            Collecting data<span className="blink">_</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#1a1a1a" strokeDasharray="3 3" />
              <XAxis dataKey="t" hide />
              <YAxis
                width={32}
                tick={{ fontSize: 9, fill: "#666" }}
                axisLine={false}
                tickLine={false}
                domain={["auto", "auto"]}
                tickFormatter={(v) => `${v}`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="ms"
                stroke="#ff9800"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

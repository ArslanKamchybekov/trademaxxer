import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts"

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  return (
    <div className="border border-border bg-[#111] px-2 py-1 text-[10px]">
      <div>
        <span className="text-amber">events/s: </span>
        <span className="tabular text-foreground">{payload[0]?.value || 0}</span>
      </div>
      <div>
        <span className="text-yes">decisions/s: </span>
        <span className="tabular text-foreground">{payload[1]?.value || 0}</span>
      </div>
    </div>
  )
}

export default function ThroughputChart({ data }) {
  const lastEps = data.length > 0 ? data[data.length - 1].eps : 0
  const lastDps = data.length > 0 ? data[data.length - 1].dps : 0

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Throughput
        </span>
        <span className="tabular text-[10px]">
          <span className="text-amber">{lastEps}</span>
          <span className="text-muted-foreground"> ev/s </span>
          <span className="text-yes">{lastDps}</span>
          <span className="text-muted-foreground"> dec/s</span>
        </span>
      </div>
      <div className="flex-1 p-1">
        {data.length < 3 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            Sampling<span className="blink">_</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#1a1a1a" strokeDasharray="3 3" />
              <XAxis dataKey="t" hide />
              <YAxis
                width={20}
                tick={{ fontSize: 9, fill: "#666" }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="eps"
                stroke="#ff9800"
                fill="#ff980015"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="dps"
                stroke="#00c853"
                fill="#00c85310"
                strokeWidth={1}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

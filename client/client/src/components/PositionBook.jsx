const ACTION_COLOR = { YES: "text-yes", NO: "text-no", SKIP: "text-skip" }

function PressureBar({ yes, no }) {
  const total = yes + no
  if (total === 0) return <div className="h-[4px] w-full bg-[#1a1a1a]" />
  const yesPct = (yes / total) * 100
  return (
    <div className="flex h-[4px] w-full overflow-hidden">
      <div className="bg-yes/60" style={{ width: `${yesPct}%` }} />
      <div className="bg-no/60 flex-1" />
    </div>
  )
}

function MicroSparkline({ values, color }) {
  if (values.length < 2) return null
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1
  const w = 40
  const h = 12
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w
    const y = h - ((v - min) / range) * h
    return `${x},${y}`
  }).join(" ")

  return (
    <svg width={w} height={h} className="inline-block">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1" />
    </svg>
  )
}

export default function PositionBook({ markets, marketStats }) {
  let totalPnl = 0
  for (const m of markets) {
    const s = marketStats[m.address]
    if (s) totalPnl += s.pnl
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Position Book
        </span>
        <span className="tabular text-[10px]">
          <span className="text-muted-foreground">SIM P&amp;L </span>
          <span className={totalPnl >= 0 ? "text-yes" : "text-no"}>
            {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(0)}
          </span>
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="border-b border-border text-left text-[9px] uppercase text-muted-foreground">
              <th className="px-1.5 py-0.5 font-normal">Market</th>
              <th className="px-1.5 py-0.5 font-normal text-center">Pressure</th>
              <th className="px-1.5 py-0.5 font-normal text-right">Conf</th>
              <th className="px-1.5 py-0.5 font-normal text-center">Spark</th>
              <th className="px-1.5 py-0.5 font-normal text-right">P&L</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((m) => {
              const s = marketStats[m.address] || {
                yes: 0, no: 0, skip: 0, avgConf: 0, pnl: 0,
                confidences: [], latencies: [], lastAction: null,
              }
              const lastColor = ACTION_COLOR[s.lastAction] || "text-muted-foreground"
              return (
                <tr key={m.address} className="border-b border-border/30">
                  <td className="max-w-[140px] truncate px-1.5 py-1 text-foreground/80">
                    {m.question.slice(0, 40)}…
                  </td>
                  <td className="px-1.5 py-1">
                    <PressureBar yes={s.yes} no={s.no} />
                    <div className="flex justify-between mt-0.5 text-[8px]">
                      <span className="text-yes">{s.yes}Y</span>
                      <span className="text-no">{s.no}N</span>
                    </div>
                  </td>
                  <td className="tabular px-1.5 py-1 text-right text-amber">
                    {s.avgConf ? `${(s.avgConf * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td className="px-1.5 py-1 text-center">
                    <MicroSparkline
                      values={s.confidences}
                      color={s.lastAction === "YES" ? "#00c853" : s.lastAction === "NO" ? "#ff1744" : "#ff9800"}
                    />
                  </td>
                  <td className={`tabular px-1.5 py-1 text-right font-bold ${s.pnl >= 0 ? "text-yes" : "text-no"}`}>
                    {s.pnl >= 0 ? "+" : ""}{s.pnl.toFixed(0)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

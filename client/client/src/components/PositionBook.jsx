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

export default function PositionBook({ markets, marketStats, manualTrades = [] }) {
  // Combine agent positions and manual trades
  const marketsWithAgentPositions = markets.filter(m => {
    const s = marketStats[m.address]
    return s && (s.yes > 0 || s.no > 0) // Only show if we have YES or NO positions
  })

  // Get markets with manual trades
  const manualTradeMarkets = [...new Set(manualTrades.map(t => t.market.address))]
    .map(address => {
      const market = markets.find(m => m.address === address)
      if (!market) return null

      const trades = manualTrades.filter(t => t.market.address === address)
      const position = trades.reduce((acc, trade) => {
        const size = trade.side === "YES" ? trade.size : -trade.size
        return acc + size
      }, 0)

      return {
        market,
        position,
        trades: trades.length,
        avgPrice: trades.length > 0
          ? trades.reduce((acc, t) => acc + t.price, 0) / trades.length
          : 0,
        pnl: position * (market.current_probability - trades[0]?.price || 0)
      }
    })
    .filter(Boolean)

  // Calculate total P&L from both agent and manual positions
  let totalPnl = 0

  // Agent P&L
  for (const m of marketsWithAgentPositions) {
    const s = marketStats[m.address]
    if (s) totalPnl += s.pnl
  }

  // Manual trades P&L
  for (const pos of manualTradeMarkets) {
    totalPnl += pos.pnl
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
            {marketsWithAgentPositions.length === 0 && manualTradeMarkets.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-1.5 py-4 text-center text-muted-foreground text-[10px]">
                  No positions yet
                </td>
              </tr>
            ) : (
              <>
                {/* Agent Positions */}
                {marketsWithAgentPositions.map((m) => {
                  const s = marketStats[m.address] || {
                    yes: 0, no: 0, skip: 0, avgConf: 0, pnl: 0,
                    confidences: [], latencies: [], lastAction: null,
                  }
                  const lastColor = ACTION_COLOR[s.lastAction] || "text-muted-foreground"
                  return (
                    <tr key={`agent-${m.address}`} className="border-b border-border/30">
                      <td className="max-w-[140px] truncate px-1.5 py-1 text-foreground/80">
                        <span className="text-[8px] text-muted-foreground mr-1">🤖</span>
                        {m.question.slice(0, 35)}…
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

                {/* Manual Trade Positions */}
                {manualTradeMarkets.map((pos) => {
                  const { market, position, trades, avgPrice, pnl } = pos
                  return (
                    <tr key={`manual-${market.address}`} className="border-b border-border/30">
                      <td className="max-w-[140px] truncate px-1.5 py-1 text-foreground/80">
                        <span className="text-[8px] text-muted-foreground mr-1">👤</span>
                        {market.question.slice(0, 35)}…
                      </td>
                      <td className="px-1.5 py-1">
                        <div className="text-[8px] text-center">
                          <div className={position > 0 ? "text-yes" : "text-no"}>
                            {position > 0 ? "YES" : "NO"} ${Math.abs(position)}
                          </div>
                          <div className="text-muted-foreground">
                            {trades} trade{trades !== 1 ? 's' : ''}
                          </div>
                        </div>
                      </td>
                      <td className="tabular px-1.5 py-1 text-right text-amber">
                        {(avgPrice * 100).toFixed(1)}¢
                      </td>
                      <td className="px-1.5 py-1 text-center text-[8px] text-muted-foreground">
                        Manual
                      </td>
                      <td className={`tabular px-1.5 py-1 text-right font-bold ${pnl >= 0 ? "text-yes" : "text-no"}`}>
                        {pnl >= 0 ? "+" : ""}{pnl.toFixed(0)}
                      </td>
                    </tr>
                  )
                })}
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

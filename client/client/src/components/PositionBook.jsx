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

export default function PositionBook({ markets, marketStats, allTrades = [] }) {
  // Combine agent positions and all trades (manual + agent)
  const marketsWithAgentPositions = markets.filter(m => {
    const s = marketStats[m.address]
    return s && (s.yes > 0 || s.no > 0) // Only show if we have YES or NO positions
  })

  // Get markets with trades (both agent and manual)
  const tradeMarkets = [...new Set(allTrades.map(t => t.market.address))]
    .map(address => {
      // First try to find market in main markets array (Kalshi markets)
      let market = markets.find(m => m.address === address)

      // If not found, this might be a DFlow market - use the market from the trade itself
      if (!market) {
        const trade = allTrades.find(t => t.market.address === address)
        if (trade && trade.market) {
          market = trade.market
        }
      }

      if (!market) return null

      const trades = allTrades.filter(t => t.market.address === address)
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

  // Calculate P&L by type
  let totalSimPnl = 0
  let totalOnChainPnl = 0
  let totalDFlowTestPnl = 0

  // Agent P&L (simulation)
  for (const m of marketsWithAgentPositions) {
    const s = marketStats[m.address]
    if (s) totalSimPnl += s.pnl
  }

  // All trades P&L categorized
  for (const pos of tradeMarkets) {
    const tradesForMarket = allTrades.filter(t => t.market.address === pos.market.address)
    const hasOnChain = tradesForMarket.some(t => t.venue === "dflow" && t.tx_hash && !t.test_mode)
    const hasDFlow = tradesForMarket.some(t => t.venue === "dflow")

    if (hasOnChain) {
      totalOnChainPnl += pos.pnl
    } else if (hasDFlow) {
      totalDFlowTestPnl += pos.pnl
    } else {
      totalSimPnl += pos.pnl
    }
  }

  const totalPnl = totalSimPnl + totalOnChainPnl + totalDFlowTestPnl
  const hasOnChainTrades = totalOnChainPnl !== 0
  const hasDFlowTestTrades = totalDFlowTestPnl !== 0

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Position Book
        </span>
        <div className="tabular text-[10px] space-y-0.5">
          {hasOnChainTrades && (
            <div>
              <span className="text-muted-foreground">⛓️ On-Chain </span>
              <span className={totalOnChainPnl >= 0 ? "text-yes" : "text-no"}>
                {totalOnChainPnl >= 0 ? "+" : ""}{totalOnChainPnl.toFixed(0)}
              </span>
            </div>
          )}
          {hasDFlowTestTrades && (
            <div>
              <span className="text-muted-foreground">🧪 DFlow </span>
              <span className={totalDFlowTestPnl >= 0 ? "text-yes" : "text-no"}>
                {totalDFlowTestPnl >= 0 ? "+" : ""}{totalDFlowTestPnl.toFixed(0)}
              </span>
            </div>
          )}
          <div>
            <span className="text-muted-foreground">SIM </span>
            <span className={totalSimPnl >= 0 ? "text-yes" : "text-no"}>
              {totalSimPnl >= 0 ? "+" : ""}{totalSimPnl.toFixed(0)}
            </span>
          </div>
          {(hasOnChainTrades || hasDFlowTestTrades) && (
            <div className="border-t border-border/30 pt-0.5">
              <span className="text-muted-foreground">Total </span>
              <span className={totalPnl >= 0 ? "text-yes" : "text-no"}>
                {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(0)}
              </span>
            </div>
          )}
        </div>
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
            {marketsWithAgentPositions.length === 0 && tradeMarkets.length === 0 ? (
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

                {/* All Trade Positions (Manual + Agent) */}
                {tradeMarkets.map((pos) => {
                  const { market, position, trades, avgPrice, pnl } = pos
                  const tradesForMarket = allTrades.filter(t => t.market.address === market.address)
                  const hasManual = tradesForMarket.some(t => t.type === "manual")
                  const hasAgent = tradesForMarket.some(t => t.type === "agent")
                  const hasOnChain = tradesForMarket.some(t => t.venue === "dflow" && t.tx_hash && !t.test_mode)
                  const hasDFlow = tradesForMarket.some(t => t.venue === "dflow")

                  // Get the latest on-chain transaction hash for Solscan link
                  const onChainTrade = tradesForMarket.find(t => t.venue === "dflow" && t.tx_hash && !t.test_mode)
                  const dflowTrade = tradesForMarket.find(t => t.venue === "dflow")

                  let tradeTypeLabel = "M"
                  if (hasOnChain) tradeTypeLabel = "⛓️"
                  else if (hasDFlow) tradeTypeLabel = "🧪" // Test mode DFlow
                  else if (hasAgent && hasManual) tradeTypeLabel = "A+M"
                  else if (hasAgent) tradeTypeLabel = "A"

                  return (
                    <tr key={`trade-${market.address}`} className="border-b border-border/30">
                      <td className="max-w-[140px] truncate px-1.5 py-1 text-foreground/80">
                        <span className="text-[8px] text-muted-foreground/50 mr-1" title={
                          hasOnChain ? "On-chain trade" :
                          hasDFlow ? "DFlow test mode" :
                          hasAgent && hasManual ? "Agent + Manual" :
                          hasAgent ? "Agent" : "Manual"
                        }>
                          {tradeTypeLabel}
                        </span>
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
                          {hasOnChain && onChainTrade && (
                            <a
                              href={`https://solscan.io/tx/${onChainTrade.tx_hash}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-amber hover:text-amber/80 underline"
                              title="View on Solscan"
                            >
                              Solscan ↗
                            </a>
                          )}
                          {hasDFlow && !hasOnChain && dflowTrade && (
                            <div className="text-amber/60">
                              DFlow Test
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="tabular px-1.5 py-1 text-right text-amber">
                        {(avgPrice * 100).toFixed(1)}¢
                      </td>
                      <td className="px-1.5 py-1 text-center text-[8px] text-muted-foreground">
                        {hasOnChain ? "On-Chain" :
                         hasDFlow ? "DFlow" :
                         hasAgent && hasManual ? "Mixed" :
                         hasAgent ? "Agent" : "Manual"}
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

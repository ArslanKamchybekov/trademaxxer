import { useState } from "react"
import React from "react"
import useWebSocket from "@/hooks/useWebSocket"
import TerminalHeader from "@/components/TerminalHeader"
import TickerTape from "@/components/TickerTape"
import NewsTape from "@/components/NewsTape"
import DecisionFeed from "@/components/DecisionFeed"
import MarketGrid from "@/components/MarketGrid"
import PositionBook from "@/components/PositionBook"
import LatencyChart from "@/components/LatencyChart"
import LatencyStats from "@/components/LatencyStats"
import ThroughputChart from "@/components/ThroughputChart"
import DecisionChart from "@/components/DecisionChart"
import ModalAgentPanel from "@/components/ModalAgentPanel"
import MarketActivity from "@/components/MarketActivity"
import TagHeatmap from "@/components/TagHeatmap"
import SystemBar from "@/components/SystemBar"
import OrderTicket from "@/components/OrderTicket"

export default function App() {
  const {
    status, news, decisions,
    latencyData, throughputData, velocityData,
    stats, marketStats, tagStats, sessionStart,
    enabledMarkets, toggleMarket, markets,
  } = useWebSocket()

  const [tradingMode, setTradingMode] = useState("agent") // "manual" or "agent"
  const [manualTrades, setManualTrades] = useState([])
  const [agentTrades, setAgentTrades] = useState([])

  const handlePlaceOrder = (order) => {
    // Add to manual trades list
    const trade = {
      id: Date.now().toString(),
      ...order,
      status: "filled",
      fillTime: new Date().toISOString(),
      type: "manual"
    }
    setManualTrades(prev => [trade, ...prev.slice(0, 49)]) // Keep last 50 trades

    console.log("Manual trade placed:", trade)
  }

  // Track agent trades from decisions
  React.useEffect(() => {
    if (decisions.length > 0) {
      const latestDecision = decisions[0]
      if (latestDecision.action && latestDecision.action !== "SKIP") {
        const market = markets.find(m => m.address === latestDecision.marketId)
        if (market) {
          const agentTrade = {
            id: `agent-${latestDecision.timestamp}`,
            market: market,
            side: latestDecision.action,
            size: 100, // Standard agent trade size
            price: latestDecision.action === "YES" ? market.current_probability : (1 - market.current_probability),
            timestamp: latestDecision.timestamp,
            status: "filled",
            fillTime: new Date(latestDecision.timestamp).toISOString(),
            type: "agent",
            confidence: latestDecision.confidence,
            theoPrice: latestDecision.theo || null
          }

          setAgentTrades(prev => {
            // Avoid duplicates
            const exists = prev.some(t => t.id === agentTrade.id)
            if (!exists) {
              return [agentTrade, ...prev.slice(0, 49)] // Keep last 50 trades
            }
            return prev
          })
        }
      }
    }
  }, [decisions, markets])

  // Combine all trades for position book
  const allTrades = [...agentTrades, ...manualTrades].sort((a, b) =>
    new Date(b.fillTime).getTime() - new Date(a.fillTime).getTime()
  )

  return (
    <div className="flex h-screen flex-col bg-background">
      <TerminalHeader
        status={status}
        stats={stats}
        sessionStart={sessionStart}
        throughputData={throughputData}
      />

      <TickerTape decisions={decisions} />

      {/* Main 3-column layout */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT COL: News + Market Activity ── */}
        <div className="flex w-[360px] shrink-0 flex-col border-r border-border">
          {/* News Wire — top */}
          <div className="flex-[3] overflow-hidden border-b border-border">
            <NewsTape news={news} velocityData={velocityData} />
          </div>
          {/* Market Activity — bottom */}
          <div className="flex-[2] overflow-hidden">
            <MarketActivity decisions={decisions} />
          </div>
        </div>

        {/* ── CENTER COL: Markets + Position Book + Tags ─ */}
        <div className="flex w-[380px] shrink-0 flex-col border-r border-border">
          <div className="flex-[3] overflow-hidden border-b border-border">
            <MarketGrid
              markets={markets}
              marketStats={marketStats}
              enabledMarkets={enabledMarkets}
              onToggle={toggleMarket}
            />
          </div>
          <div className="flex-[3] overflow-hidden border-b border-border">
            <PositionBook markets={markets} marketStats={marketStats} allTrades={allTrades} />
          </div>
          <div className="flex-[2] overflow-hidden">
            <TagHeatmap tagStats={tagStats} />
          </div>
        </div>

        {/* ── RIGHT COL: Decisions + Agent/Trading Panel ────────── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-[3] overflow-hidden border-b border-border">
            <DecisionFeed decisions={decisions} />
          </div>
          <div className="flex-[4] overflow-hidden">
            <div className="flex h-full">
              {/* Left side: Agent Panel */}
              <div className="flex-1 border-r border-border overflow-hidden">
                <ModalAgentPanel stats={stats} decisions={decisions} enabledCount={enabledMarkets.size} />
              </div>
              {/* Right side: Trading Mode Toggle + Order Ticket */}
              <div className="w-[200px] shrink-0 overflow-hidden">
                <div className="h-full flex flex-col">
                  {/* Mode Toggle */}
                  <div className="border-b border-border px-2 py-1">
                    <div className="flex gap-1">
                      <button
                        onClick={() => setTradingMode("agent")}
                        className={`px-2 py-0.5 text-[8px] uppercase rounded ${
                          tradingMode === "agent"
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:bg-accent"
                        }`}
                      >
                        Agent
                      </button>
                      <button
                        onClick={() => setTradingMode("manual")}
                        className={`px-2 py-0.5 text-[8px] uppercase rounded ${
                          tradingMode === "manual"
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:bg-accent"
                        }`}
                      >
                        Manual
                      </button>
                    </div>
                  </div>

                  {/* Order Ticket */}
                  <div className="flex-1 overflow-hidden">
                    <OrderTicket
                      markets={markets}
                      marketStats={marketStats}
                      onPlaceOrder={handlePlaceOrder}
                      mode={tradingMode}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <SystemBar stats={stats} status={status} sessionStart={sessionStart} />
    </div>
  )
}
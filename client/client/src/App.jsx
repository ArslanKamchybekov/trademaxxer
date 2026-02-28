import { useState } from "react"
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

export default function App() {
  const {
    status, news, decisions,
    latencyData, throughputData, velocityData,
    stats, marketStats, tagStats, sessionStart,
    enabledMarkets, toggleMarket, markets,
  } = useWebSocket()

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
            <PositionBook markets={markets} marketStats={marketStats} />
          </div>
          <div className="flex-[2] overflow-hidden">
            <TagHeatmap tagStats={tagStats} />
          </div>
        </div>

        {/* ── RIGHT COL: Decisions + Modal Agent ────────── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-[3] overflow-hidden border-b border-border">
            <DecisionFeed decisions={decisions} />
          </div>
          <div className="flex-[4] overflow-hidden">
            <ModalAgentPanel stats={stats} decisions={decisions} enabledCount={enabledMarkets.size} />
          </div>
        </div>
      </div>

      <SystemBar stats={stats} status={status} sessionStart={sessionStart} />
    </div>
  )
}
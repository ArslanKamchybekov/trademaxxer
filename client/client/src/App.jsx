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
import ConfidenceHistogram from "@/components/ConfidenceHistogram"
import TagHeatmap from "@/components/TagHeatmap"
import SystemBar from "@/components/SystemBar"

// Removed hardcoded test markets - using only live data from Kalshi

export default function App() {
  const {
    status, news, decisions,
    latencyData, throughputData, velocityData,
    stats, marketStats, tagStats, sessionStart,
    enabledMarkets, toggleMarket, markets,
  } = useWebSocket()

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header row */}
      <TerminalHeader
        status={status}
        stats={stats}
        sessionStart={sessionStart}
        throughputData={throughputData}
      />

      {/* Ticker tape */}
      <TickerTape decisions={decisions} />

      {/* Main 3-column layout */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT COL: News Wire ─────────────────────── */}
        <div className="flex w-[360px] shrink-0 flex-col border-r border-border">
          <div className="flex-1 overflow-hidden">
            <NewsTape news={news} velocityData={velocityData} />
          </div>
        </div>

        {/* ── CENTER COL: Markets + Position Book + Tags ─ */}
        <div className="flex w-[380px] shrink-0 flex-col border-r border-border">
          {/* Markets table — top */}
          <div className="flex-[3] overflow-hidden border-b border-border">
            <MarketGrid
              markets={markets}
              marketStats={marketStats}
              enabledMarkets={enabledMarkets}
              onToggle={toggleMarket}
            />
          </div>
          {/* Position Book — middle */}
          <div className="flex-[3] overflow-hidden border-b border-border">
            <PositionBook markets={markets} marketStats={marketStats} />
          </div>
          {/* Tag heatmap — bottom */}
          <div className="flex-[2] overflow-hidden">
            <TagHeatmap tagStats={tagStats} />
          </div>
        </div>

        {/* ── RIGHT COL: Decisions + Charts ──────────── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Decision feed — top */}
          <div className="flex-[4] overflow-hidden border-b border-border">
            <DecisionFeed decisions={decisions} />
          </div>

          {/* Charts — 2x2 grid bottom */}
          <div className="flex flex-[3] overflow-hidden">
            {/* Left 2 charts stacked */}
            <div className="flex flex-1 flex-col">
              <div className="flex-1 border-b border-border border-r border-border overflow-hidden">
                <LatencyChart data={latencyData} />
              </div>
              <div className="flex-1 border-r border-border overflow-hidden">
                <ThroughputChart data={throughputData} />
              </div>
            </div>
            {/* Right 2 charts stacked */}
            <div className="flex flex-1 flex-col">
              <div className="flex-1 border-b border-border overflow-hidden">
                <ConfidenceHistogram confidences={stats.confidences} />
              </div>
              <div className="flex-1 overflow-hidden">
                <div className="flex h-full">
                  <div className="flex-1 border-r border-border overflow-hidden">
                    <DecisionChart stats={stats} />
                  </div>
                  <div className="w-[160px] shrink-0 overflow-hidden">
                    <LatencyStats stats={stats} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <SystemBar stats={stats} status={status} sessionStart={sessionStart} />
    </div>
  )
}

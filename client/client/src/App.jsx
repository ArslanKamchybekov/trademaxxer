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

const MARKETS = [
  { address: "FakeContract1111111111111111111111111111111", question: "Will the US engage in direct military conflict with Iran before April 2026?", current_probability: 0.38, tags: ["geopolitics", "politics"] },
  { address: "FakeContract2222222222222222222222222222222", question: "Will oil prices exceed $120/barrel before June 2026?", current_probability: 0.55, tags: ["geopolitics", "commodities", "macro"] },
  { address: "FakeContract3333333333333333333333333333333", question: "Will the Federal Reserve cut interest rates before July 2026?", current_probability: 0.42, tags: ["macro", "economic_data"] },
  { address: "FakeContract4444444444444444444444444444444", question: "Will Bitcoin exceed $150k before September 2026?", current_probability: 0.31, tags: ["crypto"] },
  { address: "FakeContract5555555555555555555555555555555", question: "Will Ethereum flip Bitcoin in market cap before 2027?", current_probability: 0.08, tags: ["crypto"] },
  { address: "FakeContract6666666666666666666666666666666", question: "Will China invade Taiwan before January 2027?", current_probability: 0.12, tags: ["geopolitics", "politics"] },
  { address: "FakeContract7777777777777777777777777777777", question: "Will US unemployment exceed 5% before October 2026?", current_probability: 0.24, tags: ["macro", "economic_data"] },
  { address: "FakeContract8888888888888888888888888888888", question: "Will gold exceed $3500/oz before August 2026?", current_probability: 0.47, tags: ["commodities", "macro"] },
  { address: "FakeContract9999999999999999999999999999999", question: "Will the EU impose new sanctions on Russia before May 2026?", current_probability: 0.72, tags: ["geopolitics", "politics"] },
  { address: "FakeContractAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", question: "Will the S&P 500 hit a new all-time high before July 2026?", current_probability: 0.61, tags: ["macro", "economic_data"] },
  { address: "FakeContractBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", question: "Will a major US bank fail before December 2026?", current_probability: 0.05, tags: ["macro", "economic_data"] },
  { address: "FakeContractCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC", question: "Will natural gas prices exceed $5/MMBtu before winter 2026?", current_probability: 0.33, tags: ["commodities", "macro"] },
]

export default function App() {
  const {
    status, news, decisions,
    latencyData, throughputData, velocityData,
    stats, marketStats, tagStats, sessionStart,
    enabledMarkets, toggleMarket,
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
              markets={MARKETS}
              marketStats={marketStats}
              enabledMarkets={enabledMarkets}
              onToggle={toggleMarket}
            />
          </div>
          {/* Position Book — middle */}
          <div className="flex-[3] overflow-hidden border-b border-border">
            <PositionBook markets={MARKETS} marketStats={marketStats} />
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

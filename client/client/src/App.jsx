import useWebSocket from "@/hooks/useWebSocket"
import TerminalHeader from "@/components/TerminalHeader"
import NewsTape from "@/components/NewsTape"
import DecisionFeed from "@/components/DecisionFeed"
import MarketGrid from "@/components/MarketGrid"
import LatencyChart from "@/components/LatencyChart"
import DecisionChart from "@/components/DecisionChart"
import SystemBar from "@/components/SystemBar"

const MARKETS = [
  {
    address: "FakeContract1111111111111111111111111111111",
    question: "Will the US engage in direct military conflict with Iran before April 2026?",
    current_probability: 0.38,
    tags: ["geopolitics", "politics"],
  },
  {
    address: "FakeContract2222222222222222222222222222222",
    question: "Will oil prices exceed $120/barrel before June 2026?",
    current_probability: 0.55,
    tags: ["geopolitics", "commodities", "macro"],
  },
  {
    address: "FakeContract3333333333333333333333333333333",
    question: "Will the Federal Reserve cut interest rates before July 2026?",
    current_probability: 0.42,
    tags: ["macro", "economic_data"],
  },
  {
    address: "FakeContract4444444444444444444444444444444",
    question: "Will Bitcoin exceed $150k before September 2026?",
    current_probability: 0.31,
    tags: ["crypto"],
  },
]

export default function App() {
  const { status, news, decisions, latencyData, stats, marketStats } = useWebSocket()

  return (
    <div className="flex h-screen flex-col bg-background">
      <TerminalHeader status={status} stats={stats} />

      {/* Main grid: 2 cols x 2 rows */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left column */}
        <div className="flex w-[420px] shrink-0 flex-col border-r border-border">
          {/* News wire — top 60% */}
          <div className="flex-[3] overflow-hidden border-b border-border">
            <NewsTape news={news} />
          </div>
          {/* Markets — bottom 40% */}
          <div className="flex-[2] overflow-hidden">
            <MarketGrid markets={MARKETS} marketStats={marketStats} />
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Decisions — top 55% */}
          <div className="flex-[3] overflow-hidden border-b border-border">
            <DecisionFeed decisions={decisions} />
          </div>
          {/* Charts — bottom 45% */}
          <div className="flex flex-[2] overflow-hidden">
            <div className="flex-1 border-r border-border">
              <LatencyChart data={latencyData} />
            </div>
            <div className="flex-1">
              <DecisionChart stats={stats} />
            </div>
          </div>
        </div>
      </div>

      <SystemBar stats={stats} status={status} />
    </div>
  )
}

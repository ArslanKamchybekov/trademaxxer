import { useState, useEffect, useRef } from "react"
import {
  Radio,
  Cpu,
  Crosshair,
  BarChart3,
  Wallet,
  CircleDot,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import NewsFeed from "@/components/NewsFeed"
import StatsBar from "@/components/StatsBar"
import PlaceholderPanel from "@/components/PlaceholderPanel"

const WS_URL = "ws://localhost:8765"

function ConnectionDot({ status }) {
  const color = {
    Connected: "bg-bullish",
    Connecting: "bg-yellow-400",
    Disconnected: "bg-bearish",
    Error: "bg-bearish",
  }[status] || "bg-muted-foreground"

  return (
    <span className="relative flex h-2 w-2">
      {status === "Connected" && (
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-50 ${color}`} />
      )}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
    </span>
  )
}

export default function App() {
  const [news, setNews] = useState([])
  const [connectionStatus, setConnectionStatus] = useState("Connecting")
  const [stats, setStats] = useState({ total: 0, bullish: 0, bearish: 0, neutral: 0 })
  const ws = useRef(null)
  const seqRef = useRef(0)

  useEffect(() => {
    const connect = () => {
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => setConnectionStatus("Connected")

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === "news") {
            const item = message.data
            item._seq = ++seqRef.current

            setNews((prev) => [item, ...prev.slice(0, 99)])
            setStats((prev) => ({
              total: prev.total + 1,
              bullish: prev.bullish + (item.sentiment === "bullish" ? 1 : 0),
              bearish: prev.bearish + (item.sentiment === "bearish" ? 1 : 0),
              neutral: prev.neutral + (item.sentiment === "neutral" ? 1 : 0),
            }))
          }
        } catch (e) {
          console.error("Parse error:", e)
        }
      }

      ws.current.onclose = () => {
        setConnectionStatus("Disconnected")
        setTimeout(connect, 3000)
      }

      ws.current.onerror = () => setConnectionStatus("Error")
    }

    connect()
    return () => ws.current?.close()
  }, [])

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* ── Top Bar ─────────────────────────────────────────── */}
      <header className="flex shrink-0 items-center justify-between border-b border-border bg-card/50 px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <CircleDot size={18} className="text-primary" />
            <span className="text-sm font-semibold tracking-tight">
              trademaxxer
            </span>
          </div>
          <Separator orientation="vertical" className="!h-4" />
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ConnectionDot status={connectionStatus} />
            {connectionStatus}
          </div>
        </div>

        <StatsBar data={stats} />
      </header>

      {/* ── Main Grid ───────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── News Feed (left, wide) ──────────────────────── */}
        <div className="flex w-[480px] shrink-0 flex-col border-r border-border">
          <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <Radio size={13} className="text-primary" />
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Live Feed
            </span>
            <span className="ml-auto text-[11px] font-mono text-muted-foreground/60 tabular-nums">
              {news.length} events
            </span>
          </div>
          <div className="flex-1 overflow-hidden">
            <NewsFeed news={news} />
          </div>
        </div>

        {/* ── Right panels ────────────────────────────────── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top row: Agents + Executor */}
          <div className="grid flex-1 grid-cols-2 gap-px bg-border">
            <div className="bg-background p-3">
              <PlaceholderPanel
                title="Agents"
                icon={Cpu}
                description="Per-market Groq agents will appear here"
              />
            </div>
            <div className="bg-background p-3">
              <PlaceholderPanel
                title="Executor"
                icon={Crosshair}
                description="Trade execution status will appear here"
              />
            </div>
          </div>

          {/* Bottom row: Positions + PnL */}
          <div className="grid flex-1 grid-cols-2 gap-px bg-border">
            <div className="bg-background p-3">
              <PlaceholderPanel
                title="Positions"
                icon={Wallet}
                description="Open positions & monitoring will appear here"
              />
            </div>
            <div className="bg-background p-3">
              <PlaceholderPanel
                title="Performance"
                icon={BarChart3}
                description="PnL tracking & metrics will appear here"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

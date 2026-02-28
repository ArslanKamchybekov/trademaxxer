import { useMemo, useState, useEffect } from "react"
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts"

const CONTAINER_COLORS = [
  "#00c853", "#ff9800", "#29b6f6", "#ff1744",
  "#ab47bc", "#26a69a", "#fdd835", "#ec407a",
  "#7e57c2", "#66bb6a", "#42a5f5", "#ef5350",
]

function Pulse({ active }) {
  return (
    <span className="relative flex h-2 w-2">
      {active && (
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yes opacity-50" />
      )}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${active ? "bg-yes" : "bg-muted-foreground/30"}`} />
    </span>
  )
}

function KV({ label, value, mono }) {
  return (
    <div className="flex justify-between items-center text-[9px]">
      <span className="text-muted-foreground/70">{label}</span>
      <span className={`${mono ? "tabular" : ""} text-foreground`}>{value}</span>
    </div>
  )
}

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  return (
    <div className="border border-border bg-[#111] px-2 py-1 text-[9px] space-y-0.5">
      {payload.filter(p => p.value != null).map(p => (
        <div key={p.dataKey} className="flex items-center gap-1.5">
          <div className="h-1.5 w-1.5 rounded-full shrink-0" style={{ background: p.stroke }} />
          <span className="text-muted-foreground truncate max-w-[80px]">{p.dataKey}</span>
          <span className="tabular text-foreground ml-auto">{Math.round(p.value)}ms</span>
        </div>
      ))}
    </div>
  )
}

function formatUptime(ms) {
  if (ms < 60_000) return `${Math.floor(ms / 1000)}s`
  if (ms < 3600_000) return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`
  return `${Math.floor(ms / 3600_000)}h ${Math.floor((ms % 3600_000) / 60_000)}m`
}

export default function ModalAgentPanel({ stats, decisions, enabledCount }) {
  const total = stats.decisions || 0
  const agents = enabledCount || 0
  const isActive = total > 0

  const [tick, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 3000)
    return () => clearInterval(id)
  }, [])

  const containers = useMemo(() => {
    const map = new Map()
    const now = Date.now()
    for (const d of decisions) {
      const addr = d.market_address
      if (!addr) continue
      let c = map.get(addr)
      if (!c) {
        c = { address: addr, label: addr.slice(0, 10), evals: 0, firstTs: d._ts, lastTs: 0, latencies: [] }
        map.set(addr, c)
      }
      c.evals++
      if (d._ts < c.firstTs) c.firstTs = d._ts
      if (d._ts > c.lastTs) c.lastTs = d._ts
      if (d.latency_ms) c.latencies.push({ t: d._ts, ms: d.latency_ms })
    }
    const list = [...map.values()].sort((a, b) => b.evals - a.evals)
    return list.map((c, i) => {
      const age = now - c.lastTs
      let state
      if (age < 5_000) state = "PROCESSING"
      else if (age < 30_000) state = "WARM"
      else state = "IDLE"
      const uptime = now - c.firstTs
      const avgLat = c.latencies.length > 0
        ? Math.round(c.latencies.reduce((s, l) => s + l.ms, 0) / c.latencies.length)
        : 0
      return { ...c, state, uptime, avgLat, color: CONTAINER_COLORS[i % CONTAINER_COLORS.length] }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decisions, tick])

  const chartData = useMemo(() => {
    if (containers.length === 0) return []
    const bucketMs = 5000
    const allPoints = new Map()
    for (const c of containers) {
      for (const pt of c.latencies) {
        const bucket = Math.floor(pt.t / bucketMs) * bucketMs
        let entry = allPoints.get(bucket)
        if (!entry) {
          entry = { t: bucket }
          allPoints.set(bucket, entry)
        }
        const key = c.label
        if (!entry[key] || pt.ms > entry[key]) entry[key] = pt.ms
      }
    }
    return [...allPoints.values()].sort((a, b) => a.t - b.t).slice(-30)
  }, [containers])

  const stateColor = { PROCESSING: "text-yes", WARM: "text-amber", IDLE: "text-muted-foreground/50" }
  const stateDot = { PROCESSING: "bg-yes", WARM: "bg-amber", IDLE: "bg-muted-foreground/30" }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Modal Infrastructure
        </span>
        <div className="flex items-center gap-1.5">
          <Pulse active={isActive} />
          <span className={`text-[9px] font-bold uppercase ${isActive ? "text-yes" : "text-muted-foreground/40"}`}>
            {isActive ? `${agents} CONTAINERS` : "IDLE"}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {!isActive ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            Containers cold<span className="blink">_</span>
          </div>
        ) : (
          <div className="flex flex-col">

            {/* ── App + Image ───────────────────────────── */}
            <div className="flex border-b border-border/50">
              <div className="flex-1 border-r border-border/50 px-3 py-2">
                <div className="text-[8px] text-muted-foreground/50 mb-1">MODAL APP</div>
                <div className="text-[11px] font-bold text-primary">trademaxxer-agents</div>
                <div className="text-[9px] text-muted-foreground mt-0.5">
                  modal.App · deployed · us-east
                </div>
              </div>
              <div className="flex-1 px-3 py-2">
                <div className="text-[8px] text-muted-foreground/50 mb-1">CONTAINER IMAGE</div>
                <div className="text-[9px] space-y-0.5">
                  <KV label="base" value="debian-slim:3.12" />
                  <KV label="pip" value="groq" />
                  <KV label="source" value="agents/" />
                </div>
              </div>
            </div>

            {/* ── MarketAgent config ────────────────────── */}
            <div className="border-b border-border/50 px-3 py-2">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[8px] text-muted-foreground/50">@app.cls</span>
                <span className="text-[10px] font-bold text-amber">MarketAgent</span>
                <span className="text-[8px] text-muted-foreground/40">@modal.concurrent(max_inputs=20)</span>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[9px]">
                <KV label="scaledown_window" value="300s" mono />
                <KV label="buffer_containers" value="1" mono />
                <KV label="max_inputs" value="20 / container" mono />
                <KV label="secrets" value="groq-api-key" />
              </div>
            </div>

            {/* ── Container Lifecycle ───────────────────── */}
            <div className="border-b border-border/50 px-3 py-2">
              <div className="text-[8px] text-muted-foreground/50 mb-1.5">CONTAINER LIFECYCLE</div>
              <div className="flex items-center text-[8px]">
                {[
                  { label: "BOOT", detail: "~1s", color: "text-muted-foreground" },
                  { label: "@enter", detail: "init Groq", color: "text-amber" },
                  { label: "WARM", detail: "eval()", color: "text-yes" },
                  { label: "IDLE", detail: "≤300s", color: "text-muted-foreground/60" },
                  { label: "SCALE↓", detail: "→ 0", color: "text-no/60" },
                ].map((step, i, arr) => (
                  <div key={step.label} className="flex items-center">
                    <div className="flex flex-col items-center px-1.5">
                      <span className={`font-bold ${step.color}`}>{step.label}</span>
                      <span className="text-[7px] text-muted-foreground/40 mt-0.5">{step.detail}</span>
                    </div>
                    {i < arr.length - 1 && <span className="text-muted-foreground/30">→</span>}
                  </div>
                ))}
              </div>
            </div>

            {/* ── Inference config ──────────────────────── */}
            <div className="flex border-b border-border/50">
              <div className="flex-1 border-r border-border/50 px-3 py-2">
                <div className="text-[8px] text-muted-foreground/50 mb-1">INFERENCE</div>
                <div className="text-[10px] font-bold text-amber">llama-3.1-8b-instant</div>
                <div className="text-[9px] text-muted-foreground mt-0.5 space-y-0.5">
                  <KV label="provider" value="Groq" />
                  <KV label="mode" value="JSON structured" />
                  <KV label="max_tokens" value="32" mono />
                  <KV label="temperature" value="0.1" mono />
                </div>
              </div>
              <div className="flex-1 px-3 py-2">
                <div className="text-[8px] text-muted-foreground/50 mb-1">EVAL PIPELINE</div>
                <div className="text-[9px] space-y-0.5">
                  <KV label="method" value="evaluate.remote.aio" />
                  <KV label="serialization" value="dict boundary" />
                  <KV label="output" value='{"action","p"}' />
                  <KV label="timeout" value="2.0s" mono />
                </div>
              </div>
            </div>

            {/* ── Container Performance Chart ───────────── */}
            <div className="border-b border-border/50 flex flex-col" style={{ height: 160 }}>
              <div className="flex items-center justify-between px-3 pt-1.5">
                <span className="text-[8px] text-muted-foreground/50">CONTAINER PERFORMANCE</span>
                <span className="text-[7px] text-muted-foreground/40">{containers.length} containers · latency/ms</span>
              </div>
              <div className="flex-1 px-1 pb-1">
                {chartData.length < 2 ? (
                  <div className="flex h-full items-center justify-center text-[9px] text-muted-foreground">
                    Collecting data<span className="blink">_</span>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid stroke="#1a1a1a" strokeDasharray="3 3" />
                      <XAxis dataKey="t" hide />
                      <YAxis
                        width={30}
                        tick={{ fontSize: 8, fill: "#666" }}
                        axisLine={false}
                        tickLine={false}
                        domain={["auto", "auto"]}
                        tickFormatter={v => `${v}`}
                      />
                      <Tooltip content={<ChartTooltip />} />
                      {containers.map(c => (
                        <Line
                          key={c.label}
                          type="monotone"
                          dataKey={c.label}
                          stroke={c.color}
                          strokeWidth={1.5}
                          dot={false}
                          connectNulls
                          isAnimationActive={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* ── Container Status Table ────────────────── */}
            <div className="px-3 py-2">
              <div className="text-[8px] text-muted-foreground/50 mb-1.5">CONTAINER STATUS</div>
              {/* Header */}
              <div className="flex items-center text-[7px] text-muted-foreground/40 uppercase tracking-wider mb-1 px-0.5">
                <span className="w-3 shrink-0" />
                <span className="flex-[3] min-w-0">Container</span>
                <span className="flex-[2] text-right">State</span>
                <span className="flex-[2] text-right">Uptime</span>
                <span className="flex-[1] text-right">Evals</span>
                <span className="flex-[2] text-right">Avg Lat</span>
              </div>
              {/* Rows */}
              <div className="space-y-0">
                {containers.map(c => (
                  <div
                    key={c.label}
                    className="flex items-center text-[9px] py-[3px] px-0.5 border-b border-border/30 last:border-0"
                  >
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${stateDot[c.state]}`} />
                    <span className="flex-[3] min-w-0 truncate ml-1.5 font-mono text-foreground/80" style={{ color: c.color }}>
                      {c.label}
                    </span>
                    <span className={`flex-[2] text-right text-[8px] font-bold uppercase ${stateColor[c.state]}`}>
                      {c.state === "PROCESSING" ? "WARM" : c.state}
                    </span>
                    <span className="flex-[2] text-right tabular text-foreground/60">
                      {formatUptime(c.uptime)}
                    </span>
                    <span className="flex-[1] text-right tabular text-foreground/60">
                      {c.evals}
                    </span>
                    <span className="flex-[2] text-right tabular text-amber">
                      {c.avgLat}ms
                    </span>
                  </div>
                ))}
              </div>
              <div className="text-[7px] text-muted-foreground/40 mt-2 text-center">
                Modal autoscaler · scale-to-zero · sub-second cold starts · scaledown 300s
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}

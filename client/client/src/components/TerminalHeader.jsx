import { useState, useEffect } from "react"

function StatusDot({ label, active }) {
  return (
    <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          active ? "bg-yes" : "bg-[#333]"
        }`}
      />
      {label}
    </span>
  )
}

function Clock() {
  const [time, setTime] = useState("")

  useEffect(() => {
    const tick = () => setTime(new Date().toISOString().slice(11, 23))
    tick()
    const id = setInterval(tick, 100)
    return () => clearInterval(id)
  }, [])

  return <span className="tabular text-muted-foreground">{time} UTC</span>
}

function Uptime({ sessionStart }) {
  const [elapsed, setElapsed] = useState("00:00")

  useEffect(() => {
    const tick = () => {
      const s = Math.floor((Date.now() - sessionStart) / 1000)
      const m = Math.floor(s / 60)
      const h = Math.floor(m / 60)
      if (h > 0) setElapsed(`${h}:${String(m % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`)
      else setElapsed(`${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [sessionStart])

  return (
    <span className="tabular">
      <span className="text-muted-foreground">UP </span>
      <span className="text-foreground">{elapsed}</span>
    </span>
  )
}

export default function TerminalHeader({ status, stats, sessionStart, throughputData }) {
  const wsActive = status === "CONNECTED"
  const lastTp = throughputData?.length > 0 ? throughputData[throughputData.length - 1] : null
  const eps = lastTp?.eps ?? 0
  const dps = lastTp?.dps ?? 0
  const yesRate = stats.decisions > 0 ? ((stats.yes / stats.decisions) * 100).toFixed(1) : "—"
  const hitRate = stats.decisions > 0 ? (((stats.yes + stats.no) / stats.decisions) * 100).toFixed(1) : "—"

  return (
    <header className="flex items-center justify-between border-b border-border bg-[#0d0d0d] px-3 py-1.5">
      <div className="flex items-center gap-4">
        <span className="text-[13px] font-bold tracking-wide text-primary">
          TRADEMAXXER
        </span>
        <span className="text-[10px] text-muted-foreground">|</span>
        <StatusDot label="KALSHI" active={wsActive} />
        <StatusDot label="POLYMARKET" active={wsActive} />
      </div>

      <div className="flex items-center gap-3 text-[10px]">
        <span className="tabular">
          <span className="text-muted-foreground">EV </span>
          <span className="text-foreground">{stats.events}</span>
        </span>
        <span className="tabular">
          <span className="text-muted-foreground">DEC </span>
          <span className="text-foreground">{stats.decisions}</span>
        </span>
        <span className="text-border">|</span>
        <span className="tabular">
          <span className="text-muted-foreground">e/s </span>
          <span className="text-amber">{eps}</span>
        </span>
        <span className="tabular">
          <span className="text-muted-foreground">d/s </span>
          <span className="text-yes">{dps}</span>
        </span>
        <span className="text-border">|</span>
        <span className="tabular">
          <span className="text-muted-foreground">AVG </span>
          <span className="text-amber">
            {stats.avgLatency ? `${Math.round(stats.avgLatency)}ms` : "—"}
          </span>
        </span>
        <span className="tabular">
          <span className="text-muted-foreground">HIT </span>
          <span className="text-foreground">{hitRate}%</span>
        </span>
        <span className="tabular">
          <span className="text-muted-foreground">YES% </span>
          <span className="text-yes">{yesRate}%</span>
        </span>
        <span className="text-border">|</span>
        <Uptime sessionStart={sessionStart} />
        <Clock />
      </div>
    </header>
  )
}

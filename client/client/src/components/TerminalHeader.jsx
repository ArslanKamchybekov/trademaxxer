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
    const tick = () => {
      const now = new Date()
      setTime(
        now.toISOString().slice(11, 19)
      )
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  return <span className="tabular text-muted-foreground">{time} UTC</span>
}

export default function TerminalHeader({ status, stats }) {
  const wsActive = status === "CONNECTED"

  return (
    <header className="flex items-center justify-between border-b border-border bg-[#0d0d0d] px-3 py-1.5">
      <div className="flex items-center gap-4">
        <span className="text-[13px] font-bold tracking-wide text-primary">
          TRADEMAXXER
        </span>
        <span className="text-[10px] text-muted-foreground">|</span>
        <StatusDot label="WS" active={wsActive} />
        <StatusDot label="REDIS" active={wsActive} />
        <StatusDot label="MODAL" active={wsActive} />
      </div>

      <div className="flex items-center gap-4 text-[11px]">
        <span className="tabular">
          <span className="text-muted-foreground">EVENTS </span>
          <span className="text-foreground">{stats.events}</span>
        </span>
        <span className="tabular">
          <span className="text-muted-foreground">DECISIONS </span>
          <span className="text-foreground">{stats.decisions}</span>
        </span>
        <span className="tabular">
          <span className="text-muted-foreground">AVG </span>
          <span className="text-foreground">
            {stats.avgLatency ? `${Math.round(stats.avgLatency)}ms` : "—"}
          </span>
        </span>
        <Clock />
      </div>
    </header>
  )
}

import { useRef, useEffect } from "react"

const ACTION_COLOR = { YES: "text-yes", NO: "text-no", SKIP: "text-skip" }

export default function TickerTape({ decisions }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollLeft = 0
  }, [decisions.length])

  const items = decisions.slice(0, 40)

  if (items.length === 0) {
    return (
      <div className="flex items-center border-b border-border bg-[#080808] px-3 py-[3px] text-[10px] text-muted-foreground">
        <span className="text-amber-dim mr-2">SIGNAL TAPE</span>
        Awaiting signals<span className="blink">_</span>
      </div>
    )
  }

  return (
    <div className="flex items-center border-b border-border bg-[#080808] overflow-hidden">
      <span className="shrink-0 bg-primary px-2 py-[3px] text-[9px] font-bold text-primary-foreground tracking-wider">
        TAPE
      </span>
      <div ref={scrollRef} className="flex-1 overflow-x-hidden">
        <div className="ticker-scroll flex items-center gap-4 whitespace-nowrap px-3 py-[3px] text-[10px]">
          {items.map((d, i) => {
            const color = ACTION_COLOR[d.action] || "text-muted-foreground"
            const addr = (d.market_address || "").slice(0, 8)
            const conf = d.confidence ? (d.confidence * 100).toFixed(0) : "—"
            const lat = d.latency_ms ? Math.round(d.latency_ms) : "—"
            return (
              <span key={d._seq || i} className="flex items-center gap-1 ticker-item">
                <span className={`font-bold ${color}`}>{d.action}</span>
                <span className="text-muted-foreground">{addr}</span>
                <span className="tabular text-foreground/70">{conf}%</span>
                <span className="tabular text-amber-dim">{lat}ms</span>
                <span className="text-border">|</span>
              </span>
            )
          })}
          {items.map((d, i) => {
            const color = ACTION_COLOR[d.action] || "text-muted-foreground"
            const addr = (d.market_address || "").slice(0, 8)
            const conf = d.confidence ? (d.confidence * 100).toFixed(0) : "—"
            const lat = d.latency_ms ? Math.round(d.latency_ms) : "—"
            return (
              <span key={`dup-${d._seq || i}`} className="flex items-center gap-1 ticker-item">
                <span className={`font-bold ${color}`}>{d.action}</span>
                <span className="text-muted-foreground">{addr}</span>
                <span className="tabular text-foreground/70">{conf}%</span>
                <span className="tabular text-amber-dim">{lat}ms</span>
                <span className="text-border">|</span>
              </span>
            )
          })}
        </div>
      </div>
    </div>
  )
}

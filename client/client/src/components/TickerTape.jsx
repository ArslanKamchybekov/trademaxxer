import { useRef, useEffect } from "react"

const ACTION_COLOR = { YES: "text-yes", NO: "text-no", SKIP: "text-skip" }

function shortName(question) {
  if (!question) return "—"
  let q = question
    .replace(/^Will\s+/i, "")
    .replace(/\s+by\s+\w+\s+\d+.*$/i, "")
    .replace(/\s+before\s+\w+\s+\d+.*$/i, "")
    .replace(/\s+in\s+20\d\d\??$/i, "")
    .replace(/\?$/, "")
    .trim()
  if (q.length > 32) q = q.slice(0, 30) + "…"
  return q
}

function TickerItem({ d, keyPrefix }) {
  const color = ACTION_COLOR[d.action] || "text-muted-foreground"
  const name = shortName(d.market_question)
  const conf = d.confidence ? (d.confidence * 100).toFixed(0) : "—"
  const lat = d.latency_ms ? Math.round(d.latency_ms) : "—"
  return (
    <span key={`${keyPrefix}${d._seq}`} className="flex items-center gap-1 ticker-item">
      <span className={`font-bold ${color}`}>{d.action}</span>
      <span className="text-foreground/60">{name}</span>
      <span className="tabular text-foreground/70">{conf}%</span>
      <span className="tabular text-amber-dim">{lat}ms</span>
      <span className="text-border">|</span>
    </span>
  )
}

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
          {items.map(d => <TickerItem key={d._seq} d={d} keyPrefix="" />)}
          {items.map(d => <TickerItem key={`dup-${d._seq}`} d={d} keyPrefix="dup-" />)}
        </div>
      </div>
    </div>
  )
}

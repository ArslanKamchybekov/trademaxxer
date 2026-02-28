import { useRef, useEffect } from "react"

const URGENCY_LABEL = {
  breaking: { text: "BRKNG", color: "text-no" },
  high: { text: "HIGH", color: "text-amber" },
  normal: { text: "", color: "" },
  low: { text: "", color: "" },
}

const SENTIMENT_COLOR = {
  bullish: "text-yes",
  bearish: "text-no",
  neutral: "text-muted-foreground",
}

function formatTime(iso) {
  if (!iso) return "--:--:--"
  try {
    return new Date(iso).toISOString().slice(11, 19)
  } catch {
    return "--:--:--"
  }
}

function NewsRow({ item, idx }) {
  const urg = URGENCY_LABEL[item.urgency] || URGENCY_LABEL.normal
  const sentColor = SENTIMENT_COLOR[item.sentiment] || SENTIMENT_COLOR.neutral
  const cats = (item.categories || []).slice(0, 3)
  const age = item._ts ? `${Math.floor((Date.now() - item._ts) / 1000)}s` : ""

  return (
    <div className="flash-news flex gap-1.5 border-b border-border/50 px-2 py-[3px] text-[10px] leading-tight">
      <span className="tabular shrink-0 text-[9px] text-muted-foreground/60 w-4 text-right">
        {idx + 1}
      </span>
      <span className="tabular shrink-0 text-muted-foreground">
        {formatTime(item.timestamp)}
      </span>
      {urg.text && (
        <span className={`shrink-0 font-bold ${urg.color}`}>{urg.text}</span>
      )}
      <span className="min-w-0 flex-1 truncate text-foreground">
        {item.headline}
      </span>
      <span className={`shrink-0 ${sentColor}`}>
        {item.sentiment === "bullish" ? "+" : item.sentiment === "bearish" ? "−" : "~"}
      </span>
      {cats.map((c) => (
        <span key={c} className="shrink-0 text-[8px] uppercase text-amber-dim">
          {c}
        </span>
      ))}
      {age && (
        <span className="shrink-0 tabular text-[8px] text-muted-foreground/40">
          {age}
        </span>
      )}
    </div>
  )
}

export default function NewsTape({ news, velocityData }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (containerRef.current) containerRef.current.scrollTop = 0
  }, [news.length])

  const lastRate = velocityData?.length > 0 ? velocityData[velocityData.length - 1].rate : 0

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          News Wire
        </span>
        <span className="tabular text-[10px]">
          <span className="text-muted-foreground">{news.length} </span>
          <span className="text-amber">{lastRate}/s</span>
        </span>
      </div>
      <div ref={containerRef} className="flex-1 overflow-y-auto">
        {news.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            Waiting for feed<span className="blink">_</span>
          </div>
        ) : (
          news.map((item, i) => <NewsRow key={item._seq} item={item} idx={i} />)
        )}
      </div>
    </div>
  )
}

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
    const d = new Date(iso)
    return d.toISOString().slice(11, 19)
  } catch {
    return "--:--:--"
  }
}

function NewsRow({ item }) {
  const urg = URGENCY_LABEL[item.urgency] || URGENCY_LABEL.normal
  const sentColor = SENTIMENT_COLOR[item.sentiment] || SENTIMENT_COLOR.neutral
  const cats = (item.categories || []).slice(0, 2)

  return (
    <div className="flash-news flex gap-2 border-b border-border/50 px-2 py-1 text-[11px] leading-tight">
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
        {item.sentiment === "bullish" ? "+" : item.sentiment === "bearish" ? "-" : "~"}
      </span>
      {cats.map((c) => (
        <span key={c} className="shrink-0 text-[9px] uppercase text-amber-dim">
          {c}
        </span>
      ))}
    </div>
  )
}

export default function NewsTape({ news }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0
    }
  }, [news.length])

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          News Wire
        </span>
        <span className="ml-2 tabular text-[10px] text-muted-foreground">
          {news.length}
        </span>
      </div>
      <div ref={containerRef} className="flex-1 overflow-y-auto">
        {news.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            Waiting for feed<span className="blink">_</span>
          </div>
        ) : (
          news.map((item) => <NewsRow key={item._seq} item={item} />)
        )}
      </div>
    </div>
  )
}

import { useEffect, useRef } from "react"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Zap, Flame, Newspaper, Clock } from "lucide-react"

const urgencyConfig = {
  breaking: { icon: Flame, label: "Breaking", className: "text-red-500" },
  high: { icon: Zap, label: "High", className: "text-yellow-400" },
  normal: { icon: Newspaper, label: "", className: "text-muted-foreground" },
}


function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

function NewsItem({ item }) {
  const urgency = urgencyConfig[item.urgency] || urgencyConfig.normal
  const UrgencyIcon = urgency.icon

  return (
    <div className="group relative border-b border-border/50 px-4 py-3.5 transition-colors hover:bg-card/80 animate-slide-in"
    >
      {item.urgency === "breaking" && (
        <div className="absolute inset-y-0 left-0 w-0.5 bg-red-500" />
      )}

      <div className="flex items-start gap-3">
        <div className={`mt-0.5 shrink-0 ${urgency.className}`}>
          <UrgencyIcon size={14} />
        </div>

        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-[13px] leading-snug font-medium text-foreground">
            {item.headline}
          </p>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground font-mono">
              <Clock size={10} />
              {formatTime(item.timestamp)}
            </span>


            {item.tickers?.slice(0, 4).map((ticker) => (
              <Badge key={ticker} variant="ticker">
                ${ticker}
              </Badge>
            ))}
            {item.tickers?.length > 4 && (
              <span className="text-[11px] text-muted-foreground">
                +{item.tickers.length - 4}
              </span>
            )}

            {item.categories?.slice(0, 2).map((cat) => (
              <Badge key={cat} variant="category">
                {cat}
              </Badge>
            ))}
          </div>

          {item.sourceHandle && (
            <p className="text-[11px] text-muted-foreground/70">
              {item.sourceHandle}
              {item.sourceType && item.sourceType !== "Other" && (
                <span> &middot; {item.sourceType}</span>
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default function NewsFeed({ news }) {
  if (news.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground">
        <div className="flex gap-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
        </div>
        <p className="text-sm">Waiting for live events&hellip;</p>
      </div>
    )
  }

  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [news.length])

  return (
    <ScrollArea ref={scrollRef} className="h-full">
      {news.map((item) => (
        <NewsItem key={item._seq} item={item} />
      ))}
    </ScrollArea>
  )
}

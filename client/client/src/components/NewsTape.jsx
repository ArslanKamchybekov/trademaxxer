import { useRef, useEffect, useState } from "react"

const URGENCY_LABEL = {
  breaking: { text: "BRKNG", color: "text-no" },
  high: { text: "HIGH", color: "text-amber" },
  normal: { text: "", color: "" },
  low: { text: "", color: "" },
}

const SOURCE_ABBR = {
  Twitter: "X",
  Telegram: "TG",
  Reddit: "RDT",
  Discord: "DSC",
  YouTube: "YT",
  RSS: "RSS",
  News: "NW",
  Web: "WEB",
  Other: "OTH",
}

const SOURCE_COLOR = {
  X: "text-blue-400",
  TG: "text-sky-400",
  RDT: "text-orange-400",
  NW: "text-emerald-400",
  RSS: "text-yellow-400",
}

function formatTime(iso) {
  if (!iso) return "--:--:--"
  try {
    return new Date(iso).toISOString().slice(11, 19)
  } catch {
    return "--:--:--"
  }
}

function stripHtml(html) {
  if (!html) return ""
  return html.replace(/<[^>]*>/g, " ").replace(/&[a-z]+;/gi, " ").replace(/\s+/g, " ").trim()
}

const URL_REGEX = /(https?:\/\/[^\s<>"')\]]+)/g
const IMG_EXT = /\.(jpg|jpeg|png|gif|webp)(\?|$)/i

function extractUrls(text) {
  if (!text) return { urls: [], imageUrls: [] }
  const all = [...text.matchAll(URL_REGEX)].map(m => m[1])
  const unique = [...new Set(all)]
  return {
    urls: unique.filter(u => !IMG_EXT.test(u)),
    imageUrls: unique.filter(u => IMG_EXT.test(u)),
  }
}

function RichBody({ text }) {
  if (!text) return null
  const parts = text.split(URL_REGEX)
  return (
    <>
      {parts.map((part, i) =>
        URL_REGEX.test(part) ? (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400/80 hover:text-blue-400 break-all"
            onClick={(e) => e.stopPropagation()}
          >
            {part.length > 40 ? part.slice(0, 40) + "…" : part}
          </a>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  )
}

function NewsDetail({ item }) {
  const rawBody = stripHtml(item.body)
  const rawHeadline = stripHtml(item.headline)
  const hasBody = rawBody && rawBody !== rawHeadline
  const tickers = item.tickers || []
  const keywords = item.highlightedWords || []
  const srcHandle = item.sourceHandle || ""
  const srcUrl = item.sourceUrl || ""
  const mediaUrl = item.mediaUrl || ""
  const avatar = item.sourceAvatar || ""
  const srcDesc = item.sourceDescription || ""

  const { imageUrls } = extractUrls(rawBody)
  const allImages = [...new Set([mediaUrl, ...imageUrls].filter(Boolean))]

  return (
    <div className="border-b border-amber/15 bg-[#0d0d0d] px-3 py-2 text-[9px]">
      {/* Source row */}
      <div className="flex items-center gap-2 mb-1.5">
        {avatar && (
          <img
            src={avatar}
            alt=""
            className="h-5 w-5 rounded-full object-cover shrink-0 border border-border/50"
            onError={(e) => { e.target.style.display = "none" }}
          />
        )}
        <div className="flex flex-col min-w-0 flex-1">
          {srcHandle && (
            <span className="text-[10px] font-bold text-foreground truncate">
              {srcHandle}
            </span>
          )}
          {srcDesc && (
            <span className="text-[8px] text-muted-foreground/60 truncate">
              {srcDesc}
            </span>
          )}
        </div>
        {srcUrl && (
          <a
            href={srcUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[8px] text-amber/60 hover:text-amber shrink-0"
            onClick={(e) => e.stopPropagation()}
          >
            SOURCE →
          </a>
        )}
      </div>

      {/* Body with linkified URLs */}
      {hasBody && (
        <div className="text-[10px] text-foreground/80 leading-snug mb-1.5 max-h-[100px] overflow-y-auto">
          <RichBody text={rawBody} />
        </div>
      )}

      {/* Images (media_url + any image URLs found in body) */}
      {allImages.length > 0 && (
        <div className="flex gap-1.5 mb-1.5 overflow-x-auto">
          {allImages.map((url) => (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="shrink-0"
            >
              <img
                src={url}
                alt=""
                className="max-h-[100px] max-w-[200px] rounded-sm border border-border/50 object-cover hover:border-amber/40 transition-colors"
                onError={(e) => { e.target.parentElement.style.display = "none" }}
              />
            </a>
          ))}
        </div>
      )}

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
        {tickers.length > 0 && tickers.map((t) => (
          <span key={t} className="text-[8px] font-bold text-blue-400/80">
            ${t}
          </span>
        ))}

        {keywords.length > 0 && keywords.slice(0, 5).map((k) => (
          <span key={k} className="text-[8px] text-muted-foreground/50">
            #{k}
          </span>
        ))}
      </div>
    </div>
  )
}

function NewsRow({ item, idx, isExpanded, onToggle }) {
  const urg = URGENCY_LABEL[item.urgency] || URGENCY_LABEL.normal
  const cats = (item.categories || []).slice(0, 3)
  const age = item._ts ? `${Math.floor((Date.now() - item._ts) / 1000)}s` : ""
  const srcAbbr = SOURCE_ABBR[item.sourceType] || item.sourceType?.slice(0, 3).toUpperCase() || ""
  const srcHandle = item.sourceHandle || ""

  return (
    <>
      <div
        className={`flash-news flex gap-1.5 border-b border-border/50 px-2 py-[3px] text-[10px] leading-tight cursor-pointer hover:bg-[#151515] transition-colors ${isExpanded ? "bg-[#131313] border-b-0" : ""}`}
        onClick={() => onToggle(item.id)}
      >
        <span className="tabular shrink-0 text-[9px] text-muted-foreground/60 w-4 text-right">
          {idx + 1}
        </span>
        <span className="tabular shrink-0 text-muted-foreground">
          {formatTime(item.timestamp)}
        </span>
        {srcAbbr && (
          <span className={`shrink-0 text-[8px] font-bold ${SOURCE_COLOR[srcAbbr] || "text-blue-400"}`} title={srcHandle || srcAbbr}>
            {srcAbbr}
          </span>
        )}
        {urg.text && (
          <span className={`shrink-0 font-bold ${urg.color}`}>{urg.text}</span>
        )}
        <span className="min-w-0 flex-1 truncate text-foreground">
          {item.headline}
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
      {isExpanded && <NewsDetail item={item} />}
    </>
  )
}

export default function NewsTape({ news, velocityData }) {
  const containerRef = useRef(null)
  const [expandedId, setExpandedId] = useState(null)

  useEffect(() => {
    if (containerRef.current) containerRef.current.scrollTop = 0
  }, [news.length])

  const lastRate = velocityData?.length > 0 ? velocityData[velocityData.length - 1].rate : 0

  const handleToggle = (id) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

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
          news.map((item, i) => (
            <NewsRow
              key={item._seq}
              item={item}
              idx={i}
              isExpanded={expandedId === item.id}
              onToggle={handleToggle}
            />
          ))
        )}
      </div>
    </div>
  )
}
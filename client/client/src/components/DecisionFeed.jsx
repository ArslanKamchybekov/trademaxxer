const ACTION_STYLE = {
  YES: { color: "text-yes", bg: "flash-decision-yes", label: "YES" },
  NO: { color: "text-no", bg: "flash-decision-no", label: " NO" },
  SKIP: { color: "text-skip", bg: "", label: "SKP" },
}

function ConfidenceBar({ value, action }) {
  const pct = Math.round(value * 100)
  const color = action === "YES" ? "bg-yes" : action === "NO" ? "bg-no" : "bg-skip"
  return (
    <div className="flex items-center gap-1">
      <div className="h-[3px] w-12 bg-[#1a1a1a]">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular text-[10px] text-muted-foreground">{pct}%</span>
    </div>
  )
}

function DecisionRow({ data }) {
  const style = ACTION_STYLE[data.action] || ACTION_STYLE.SKIP
  const addr = (data.market_address || "").slice(0, 12)
  const question = data.market_question || ""
  const latency = data.latency_ms ? `${Math.round(data.latency_ms)}ms` : "—"

  return (
    <div className={`${style.bg} border-b border-border/50 px-2 py-1.5 text-[11px]`}>
      <div className="flex items-center gap-2">
        <span className={`font-bold ${style.color} w-6 shrink-0`}>
          {style.label}
        </span>
        <ConfidenceBar value={data.confidence || 0} action={data.action} />
        <span className="tabular shrink-0 text-muted-foreground">{latency}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground">
          {addr}
        </span>
      </div>
      <div className="mt-0.5 flex gap-2 pl-8">
        <span className="min-w-0 flex-1 truncate text-foreground/80 text-[10px]">
          {question}
        </span>
      </div>
      {data.reasoning && (
        <div className="mt-0.5 truncate pl-8 text-[10px] text-muted-foreground italic">
          {data.reasoning}
        </div>
      )}
    </div>
  )
}

export default function DecisionFeed({ decisions }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Agent Decisions
        </span>
        <span className="ml-2 tabular text-[10px] text-muted-foreground">
          {decisions.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {decisions.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            Awaiting signals<span className="blink">_</span>
          </div>
        ) : (
          decisions.map((d) => <DecisionRow key={d._seq} data={d} />)
        )}
      </div>
    </div>
  )
}

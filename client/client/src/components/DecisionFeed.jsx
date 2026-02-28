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
      <div className="h-[3px] w-14 bg-[#1a1a1a]">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular text-[9px] text-muted-foreground w-7">{pct}%</span>
    </div>
  )
}

function Theo({ value, action }) {
  if (value == null) return null
  const pct = Math.round(value * 100)
  const color = action === "YES" ? "text-yes" : action === "NO" ? "text-no" : "text-muted-foreground"
  return (
    <span className={`tabular text-[9px] font-mono ${color}`}>
      →{pct}¢
    </span>
  )
}

function DecisionRow({ data, idx }) {
  const style = ACTION_STYLE[data.action] || ACTION_STYLE.SKIP
  const addr = (data.market_address || "").slice(0, 10)
  const question = data.market_question || ""
  const latency = data.latency_ms ? `${Math.round(data.latency_ms)}ms` : "—"
  const version = data.prompt_version || ""
  const age = data._ts ? `${Math.floor((Date.now() - data._ts) / 1000)}s ago` : ""

  return (
    <div className={`${style.bg} border-b border-border/50 px-2 py-1 text-[10px]`}>
      <div className="flex items-center gap-1.5">
        <span className="tabular text-[9px] text-muted-foreground/50 w-4 text-right shrink-0">
          {idx + 1}
        </span>
        <span className={`font-bold ${style.color} w-6 shrink-0`}>
          {style.label}
        </span>
        <ConfidenceBar value={data.confidence || 0} action={data.action} />
        <Theo value={data.theo} action={data.action} />
        <span className="tabular shrink-0 text-amber">{latency}</span>
        <span className="shrink-0 text-[8px] text-muted-foreground/40">{version}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground text-[9px]">
          {addr}
        </span>
        <span className="shrink-0 tabular text-[8px] text-muted-foreground/40">
          {age}
        </span>
      </div>
      <div className="mt-0.5 flex gap-2 pl-[22px]">
        <span className="min-w-0 flex-1 truncate text-foreground/70 text-[9px]">
          {question}
        </span>
      </div>
      {data.reasoning && (
        <div className="mt-0.5 truncate pl-[22px] text-[9px] text-muted-foreground/60 italic">
          → {data.reasoning}
        </div>
      )}
      {data.headline && (
        <div className="mt-0.5 truncate pl-[22px] text-[9px] text-foreground/40">
          ▸ {data.headline}
        </div>
      )}
    </div>
  )
}

export default function DecisionFeed({ decisions }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Agent Decisions
        </span>
        <span className="tabular text-[10px] text-muted-foreground">
          {decisions.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {decisions.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            Awaiting signals<span className="blink">_</span>
          </div>
        ) : (
          decisions.map((d, i) => <DecisionRow key={d._seq} data={d} idx={i} />)
        )}
      </div>
    </div>
  )
}

import { useMemo } from "react"

const ACTION_COLOR = {
  YES: "bg-yes",
  NO: "bg-no",
  SKIP: "bg-skip",
}

function ActivityBar({ market, maxEvals }) {
  const pct = maxEvals > 0 ? (market.total / maxEvals) * 100 : 0
  const yesPct = market.total > 0 ? (market.yes / market.total) * 100 : 0
  const noPct = market.total > 0 ? (market.no / market.total) * 100 : 0
  const addr = market.address.slice(0, 12)
  const lastAction = market.lastAction

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center justify-between">
        <span className="text-[9px] text-foreground/70 truncate max-w-[160px]" title={market.question}>
          {addr}
        </span>
        <div className="flex items-center gap-1.5">
          {lastAction && (
            <span className={`h-1.5 w-1.5 rounded-full ${ACTION_COLOR[lastAction] || "bg-skip"}`} />
          )}
          <span className="text-[8px] tabular text-muted-foreground">{market.total}</span>
        </div>
      </div>
      <div className="h-[4px] w-full bg-[#1a1a1a] overflow-hidden flex">
        {yesPct > 0 && <div className="h-full bg-yes/70" style={{ width: `${yesPct}%` }} />}
        {noPct > 0 && <div className="h-full bg-no/70" style={{ width: `${noPct}%` }} />}
        <div className="h-full bg-skip/30 flex-1" />
      </div>
    </div>
  )
}

export default function MarketActivity({ decisions }) {
  const markets = useMemo(() => {
    const map = new Map()
    for (const d of decisions) {
      const addr = d.market_address
      if (!addr) continue
      let entry = map.get(addr)
      if (!entry) {
        entry = { address: addr, question: d.market_question || "", total: 0, yes: 0, no: 0, skip: 0, lastAction: null, lastTs: 0 }
        map.set(addr, entry)
      }
      entry.total++
      if (d.action === "YES") entry.yes++
      else if (d.action === "NO") entry.no++
      else entry.skip++
      if (d._ts > entry.lastTs) {
        entry.lastTs = d._ts
        entry.lastAction = d.action
      }
    }
    return [...map.values()].sort((a, b) => b.total - a.total)
  }, [decisions])

  const maxEvals = markets.length > 0 ? markets[0].total : 1
  const totalSignals = markets.reduce((s, m) => s + m.yes + m.no, 0)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Market Activity
        </span>
        <span className="tabular text-[10px]">
          <span className="text-muted-foreground">{markets.length} mkts </span>
          <span className="text-amber">{totalSignals} sig</span>
        </span>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-1">
        {markets.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            No activity<span className="blink">_</span>
          </div>
        ) : (
          <div className="space-y-1.5">
            {markets.map((m) => (
              <ActivityBar key={m.address} market={m} maxEvals={maxEvals} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

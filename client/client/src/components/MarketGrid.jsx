import { useState, useEffect } from "react"

const ACTION_COLOR = {
  YES: "text-yes",
  NO: "text-no",
  SKIP: "text-skip",
}

function MicroSparkline({ values, color }) {
  if (values.length < 2) return <span className="text-[9px] text-muted-foreground">—</span>
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1
  const w = 36
  const h = 10
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w
    const y = h - ((v - min) / range) * h
    return `${x},${y}`
  }).join(" ")

  return (
    <svg width={w} height={h} className="inline-block">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1" />
    </svg>
  )
}

function SignalStrength({ total }) {
  const bars = [1, 3, 6, 10, 16]
  const level = bars.filter((b) => total >= b).length
  return (
    <span className="inline-flex items-end gap-[1px]">
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="inline-block w-[2px]"
          style={{
            height: `${4 + i * 2}px`,
            backgroundColor: i < level ? "#ff9800" : "#1e1e1e",
          }}
        />
      ))}
    </span>
  )
}

function AgentToggle({ enabled, onClick }) {
  return (
    <button
      onClick={onClick}
      className="group relative flex h-[14px] w-[26px] shrink-0 cursor-pointer items-center border border-border px-[2px] transition-colors"
      style={{
        backgroundColor: enabled ? "rgba(0, 200, 83, 0.15)" : "rgba(255, 23, 68, 0.08)",
        borderColor: enabled ? "#00c853" : "#333",
      }}
    >
      <span
        className="block h-[8px] w-[8px] transition-all duration-150"
        style={{
          backgroundColor: enabled ? "#00c853" : "#555",
          marginLeft: enabled ? "auto" : "0",
        }}
      />
    </button>
  )
}

export default function MarketGrid({ markets, marketStats, enabledMarkets, onToggle }) {
  const [selectedTags, setSelectedTags] = useState(new Set())

  // Load saved tag preferences from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('marketTagFilters')
    if (saved) {
      try {
        const tags = JSON.parse(saved)
        setSelectedTags(new Set(tags))
      } catch (e) {
        // Invalid JSON, ignore
      }
    }
  }, [])

  // Save tag preferences to localStorage
  useEffect(() => {
    localStorage.setItem('marketTagFilters', JSON.stringify([...selectedTags]))
  }, [selectedTags])

  // Get all unique tags from markets
  const allTags = [...new Set(markets.flatMap(m => m.tags || []))].sort()

  // Filter markets by selected tags
  const filteredMarkets = selectedTags.size === 0
    ? markets
    : markets.filter(m => m.tags?.some(tag => selectedTags.has(tag)))

  const enabledCount = filteredMarkets.filter((m) => enabledMarkets?.has(m.address)).length

  const toggleTag = (tag) => {
    setSelectedTags(prev => {
      const next = new Set(prev)
      if (next.has(tag)) {
        next.delete(tag)
      } else {
        next.add(tag)
      }
      return next
    })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-2 py-1">
        <div className="flex items-center justify-between mb-1">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
              Markets
            </span>
            <span className="ml-2 tabular text-[10px] text-muted-foreground">
              {enabledCount}/{filteredMarkets.length} armed
            </span>
          </div>
          <span className="text-[8px] uppercase tracking-wider text-muted-foreground">
            Agent
          </span>
        </div>

        {/* Tag filters */}
        {allTags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {allTags.map(tag => (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`px-1.5 py-0.5 text-[8px] uppercase tracking-wide transition-colors ${
                  selectedTags.has(tag)
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-accent'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="border-b border-border text-left text-[8px] uppercase text-muted-foreground">
              <th className="w-[26px] px-1 py-0.5 font-normal text-center">On</th>
              <th className="px-1.5 py-0.5 font-normal">Market</th>
              <th className="px-1.5 py-0.5 font-normal text-right">Prob</th>
              <th className="px-1.5 py-0.5 font-normal text-center">Y</th>
              <th className="px-1.5 py-0.5 font-normal text-center">N</th>
              <th className="px-1.5 py-0.5 font-normal text-center">S</th>
              <th className="px-1.5 py-0.5 font-normal text-right">Last</th>
            </tr>
          </thead>
          <tbody>
            {filteredMarkets.map((m) => {
              const enabled = enabledMarkets?.has(m.address) ?? true
              const s = marketStats[m.address] || {
                yes: 0, no: 0, skip: 0, lastAction: null,
                avgConf: 0, totalSignals: 0, latencies: [],
              }
              const lastColor = ACTION_COLOR[s.lastAction] || "text-muted-foreground"
              const dimClass = enabled ? "" : "opacity-30"
              return (
                <tr
                  key={m.address}
                  className={`border-b border-border/30 hover:bg-accent/30 transition-opacity duration-200 ${dimClass}`}
                >
                  <td className="px-1 py-1 text-center">
                    <AgentToggle
                      enabled={enabled}
                      onClick={() => onToggle?.(m.address)}
                    />
                  </td>
                  <td className="max-w-[180px] truncate px-1.5 py-1 text-foreground/90">
                    {m.question}
                  </td>
                  <td className="tabular whitespace-nowrap px-1.5 py-1 text-right text-amber">
                    {(m.current_probability * 100).toFixed(0)}%
                  </td>
                  <td className="tabular px-1.5 py-1 text-center text-yes">
                    {s.yes || "·"}
                  </td>
                  <td className="tabular px-1.5 py-1 text-center text-no">
                    {s.no || "·"}
                  </td>
                  <td className="tabular px-1.5 py-1 text-center text-muted-foreground">
                    {s.skip || "·"}
                  </td>
                  <td className={`tabular px-1.5 py-1 text-right font-bold ${lastColor}`}>
                    {s.lastAction || "—"}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

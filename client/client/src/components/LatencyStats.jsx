function percentile(sorted, p) {
  if (sorted.length === 0) return 0
  const idx = Math.ceil(sorted.length * p) - 1
  return sorted[Math.max(0, idx)]
}

export default function LatencyStats({ stats }) {
  const latencies = stats.latencies || []
  const sorted = [...latencies].sort((a, b) => a - b)
  const p50 = percentile(sorted, 0.5)
  const p95 = percentile(sorted, 0.95)
  const p99 = percentile(sorted, 0.99)
  const min = stats.minLatency === Infinity ? 0 : stats.minLatency
  const max = stats.maxLatency
  const avg = stats.avgLatency || 0
  const n = latencies.length

  const rows = [
    { label: "MIN", value: min, color: "text-yes" },
    { label: "P50", value: p50, color: "text-foreground" },
    { label: "AVG", value: avg, color: "text-amber" },
    { label: "P95", value: p95, color: "text-amber" },
    { label: "P99", value: p99, color: "text-no" },
    { label: "MAX", value: max, color: "text-no" },
  ]

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Latency Stats
        </span>
        <span className="tabular text-[10px] text-muted-foreground">n={n}</span>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-1">
        {n === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            No samples<span className="blink">_</span>
          </div>
        ) : (
          <div className="space-y-1">
            {rows.map((r) => (
              <div key={r.label} className="flex items-center justify-between text-[11px]">
                <span className="text-muted-foreground w-8">{r.label}</span>
                <div className="flex-1 mx-2 h-[3px] bg-[#1a1a1a] overflow-hidden">
                  <div
                    className="h-full bg-amber/50"
                    style={{ width: `${max > 0 ? (r.value / max) * 100 : 0}%` }}
                  />
                </div>
                <span className={`tabular ${r.color} w-14 text-right`}>
                  {Math.round(r.value)}ms
                </span>
              </div>
            ))}
            <div className="mt-2 flex justify-between text-[9px] text-muted-foreground border-t border-border/50 pt-1">
              <span>σ = {n > 1
                ? Math.round(Math.sqrt(latencies.reduce((s, l) => s + (l - avg) ** 2, 0) / (n - 1)))
                : 0}ms</span>
              <span>range = {Math.round(max - min)}ms</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

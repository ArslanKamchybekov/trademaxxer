export default function TagHeatmap({ tagStats }) {
  const entries = Object.entries(tagStats).sort((a, b) => b[1] - a[1])
  const max = entries.length > 0 ? entries[0][1] : 1
  const total = entries.reduce((s, [, v]) => s + v, 0)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Categories
        </span>
        <span className="tabular text-[10px] text-muted-foreground">
          {entries.length} tags
        </span>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-1">
        {entries.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[11px] text-muted-foreground">
            Listening<span className="blink">_</span>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1">
            {entries.map(([tag, count]) => {
              const intensity = Math.max(0.15, count / max)
              const pct = total > 0 ? ((count / total) * 100).toFixed(1) : "0"
              return (
                <div
                  key={tag}
                  className="flex items-center gap-1 border border-border px-1.5 py-0.5 text-[10px]"
                  style={{
                    backgroundColor: `rgba(255, 152, 0, ${intensity * 0.25})`,
                    borderColor: `rgba(255, 152, 0, ${intensity * 0.5})`,
                  }}
                >
                  <span className="uppercase text-amber">{tag}</span>
                  <span className="tabular text-muted-foreground">{count}</span>
                  <span className="tabular text-[9px] text-foreground/40">{pct}%</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

const ACTION_COLOR = {
  YES: "text-yes",
  NO: "text-no",
  SKIP: "text-skip",
}

export default function MarketGrid({ markets, marketStats }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-2 py-1">
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
          Markets
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-border text-left text-[9px] uppercase text-muted-foreground">
              <th className="px-2 py-1 font-normal">Market</th>
              <th className="px-2 py-1 font-normal text-right">Prob</th>
              <th className="px-2 py-1 font-normal text-center">Y</th>
              <th className="px-2 py-1 font-normal text-center">N</th>
              <th className="px-2 py-1 font-normal text-center">S</th>
              <th className="px-2 py-1 font-normal text-right">Last</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((m) => {
              const s = marketStats[m.address] || { yes: 0, no: 0, skip: 0, lastAction: null }
              const lastColor = ACTION_COLOR[s.lastAction] || "text-muted-foreground"
              return (
                <tr key={m.address} className="border-b border-border/30 hover:bg-accent/30">
                  <td className="max-w-[200px] truncate px-2 py-1 text-foreground/90">
                    {m.question}
                  </td>
                  <td className="tabular whitespace-nowrap px-2 py-1 text-right text-amber">
                    {(m.current_probability * 100).toFixed(0)}%
                  </td>
                  <td className="tabular px-2 py-1 text-center text-yes">
                    {s.yes || "·"}
                  </td>
                  <td className="tabular px-2 py-1 text-center text-no">
                    {s.no || "·"}
                  </td>
                  <td className="tabular px-2 py-1 text-center text-muted-foreground">
                    {s.skip || "·"}
                  </td>
                  <td className={`tabular px-2 py-1 text-right font-bold ${lastColor}`}>
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

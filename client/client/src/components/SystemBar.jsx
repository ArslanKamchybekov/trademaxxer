export default function SystemBar({ stats, status }) {
  return (
    <footer className="flex items-center gap-4 border-t border-border bg-[#0d0d0d] px-3 py-1 text-[10px]">
      <span className="flex items-center gap-1">
        <span className={`h-1.5 w-1.5 rounded-full ${status === "CONNECTED" ? "bg-yes" : "bg-no"}`} />
        <span className="text-muted-foreground">
          {status}
        </span>
      </span>

      <span className="text-border">|</span>

      <span className="tabular">
        <span className="text-muted-foreground">EVENTS </span>
        <span className="text-foreground">{stats.events}</span>
      </span>

      <span className="tabular">
        <span className="text-muted-foreground">DECISIONS </span>
        <span className="text-foreground">{stats.decisions}</span>
      </span>

      <span className="text-border">|</span>

      <span className="tabular">
        <span className="text-yes">YES </span>
        <span className="text-foreground">{stats.yes}</span>
      </span>
      <span className="tabular">
        <span className="text-no">NO </span>
        <span className="text-foreground">{stats.no}</span>
      </span>
      <span className="tabular">
        <span className="text-skip">SKIP </span>
        <span className="text-foreground">{stats.skip}</span>
      </span>

      <span className="text-border">|</span>

      <span className="tabular">
        <span className="text-muted-foreground">AVG LATENCY </span>
        <span className="text-amber">
          {stats.avgLatency ? `${Math.round(stats.avgLatency)}ms` : "—"}
        </span>
      </span>

      <span className="ml-auto text-[9px] text-muted-foreground">
        TRADEMAXXER v0.1
      </span>
    </footer>
  )
}

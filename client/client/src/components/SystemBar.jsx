export default function SystemBar({ stats, status, sessionStart }) {
  const upSec = Math.floor((Date.now() - (sessionStart || Date.now())) / 1000)
  const minLat = stats.minLatency === Infinity ? 0 : stats.minLatency
  const decRate = stats.decisions > 0 && upSec > 0
    ? (stats.decisions / upSec).toFixed(2)
    : "0.00"

  return (
    <footer className="flex items-center gap-3 border-t border-border bg-[#0d0d0d] px-3 py-1 text-[9px]">
      <span className="flex items-center gap-1">
        <span className={`h-1.5 w-1.5 rounded-full ${status === "CONNECTED" ? "bg-yes" : "bg-no"}`} />
        <span className="text-muted-foreground">{status}</span>
      </span>

      <span className="text-border">│</span>

      <span className="tabular">
        <span className="text-muted-foreground">EV </span>
        <span className="text-foreground">{stats.events}</span>
      </span>
      <span className="tabular">
        <span className="text-muted-foreground">DEC </span>
        <span className="text-foreground">{stats.decisions}</span>
      </span>
      <span className="tabular">
        <span className="text-muted-foreground">RATE </span>
        <span className="text-amber">{decRate}/s</span>
      </span>

      <span className="text-border">│</span>

      <span className="tabular">
        <span className="text-yes">Y </span>
        <span className="text-foreground">{stats.yes}</span>
      </span>
      <span className="tabular">
        <span className="text-no">N </span>
        <span className="text-foreground">{stats.no}</span>
      </span>
      <span className="tabular">
        <span className="text-skip">S </span>
        <span className="text-foreground">{stats.skip}</span>
      </span>

      {stats.decisions > 0 && (
        <>
          <span className="text-border">│</span>
          <span className="tabular">
            <span className="text-muted-foreground">Y% </span>
            <span className="text-yes">{((stats.yes / stats.decisions) * 100).toFixed(1)}</span>
          </span>
          <span className="tabular">
            <span className="text-muted-foreground">N% </span>
            <span className="text-no">{((stats.no / stats.decisions) * 100).toFixed(1)}</span>
          </span>
          <span className="tabular">
            <span className="text-muted-foreground">S% </span>
            <span className="text-foreground/60">{((stats.skip / stats.decisions) * 100).toFixed(1)}</span>
          </span>
        </>
      )}

      <span className="text-border">│</span>

      <span className="tabular">
        <span className="text-muted-foreground">LAT </span>
        <span className="text-amber">
          {stats.avgLatency ? `${Math.round(stats.avgLatency)}ms` : "—"}
        </span>
      </span>
      <span className="tabular">
        <span className="text-muted-foreground">MIN </span>
        <span className="text-yes">{minLat ? `${Math.round(minLat)}ms` : "—"}</span>
      </span>
      <span className="tabular">
        <span className="text-muted-foreground">MAX </span>
        <span className="text-no">{stats.maxLatency ? `${Math.round(stats.maxLatency)}ms` : "—"}</span>
      </span>

      <span className="ml-auto text-[8px] text-muted-foreground/40">
        TRADEMAXXER v0.1 — {stats.decisions > 0 ? "LIVE" : "IDLE"}
      </span>
    </footer>
  )
}

import { Activity } from "lucide-react"

const stats = [
  { key: "total", label: "Events", icon: Activity, color: "text-foreground" },
]

export default function StatsBar({ data }) {
  return (
    <div className="flex items-center gap-5">
      {stats.map(({ key, label, icon: Icon, color }) => (
        <div key={key} className="flex items-center gap-1.5">
          <Icon size={13} className={color} />
          <span className={`text-sm font-semibold tabular-nums ${color}`}>
            {data[key]}
          </span>
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {label}
          </span>
        </div>
      ))}
    </div>
  )
}

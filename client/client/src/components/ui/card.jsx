import { cn } from "@/lib/utils"

function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card text-card-foreground shadow-sm",
        className
      )}
      {...props}
    />
  )
}

function CardHeader({ className, ...props }) {
  return (
    <div
      className={cn("flex flex-col space-y-1.5 p-5 pb-3", className)}
      {...props}
    />
  )
}

function CardTitle({ className, ...props }) {
  return (
    <h3
      className={cn("text-sm font-medium tracking-wide text-muted-foreground uppercase", className)}
      {...props}
    />
  )
}

function CardContent({ className, ...props }) {
  return (
    <div className={cn("p-5 pt-0", className)} {...props} />
  )
}

export { Card, CardHeader, CardTitle, CardContent }

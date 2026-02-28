import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-primary/15 text-primary",
        bullish: "bg-bullish/15 text-bullish",
        bearish: "bg-bearish/15 text-bearish",
        neutral: "bg-muted text-muted-foreground",
        outline: "border border-border text-muted-foreground",
        ticker: "bg-primary/10 text-primary font-mono text-[11px]",
        category: "bg-accent text-accent-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({ className, variant, ...props }) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }

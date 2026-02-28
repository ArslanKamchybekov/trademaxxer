import { forwardRef } from "react"
import { cn } from "@/lib/utils"

const ScrollArea = forwardRef(({ className, children, ...props }, ref) => {
  return (
    <div
      ref={ref}
      className={cn(
        "relative overflow-y-auto scrollbar-thin scrollbar-track-transparent scrollbar-thumb-border",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
})

ScrollArea.displayName = "ScrollArea"

export { ScrollArea }

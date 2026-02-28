import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

export default function PlaceholderPanel({ title, icon: Icon, description, children }) {
  return (
    <Card className="flex flex-col h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {Icon && <Icon size={14} />}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 items-center justify-center">
        {children || (
          <p className="text-xs text-muted-foreground/50 text-center">
            {description || "Coming soon"}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

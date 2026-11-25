import { IconSparkles, IconTrendingDown, IconTrendingUp } from "@tabler/icons-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

// Example figures for the UI prototype. Step 9 computes these from events.
const CARDS = [
  {
    label: "Leads answered after hours",
    value: "47",
    delta: { up: true, text: "+35%" },
    line: "41 by Ondra, 6 by your team",
    ai: true,
    sub: "This week, 7 pm to 9 am and Sundays",
  },
  {
    label: "Median first response",
    value: "14 s",
    delta: { up: true, text: "−3 h 52 m" },
    line: "Was 3 h 52 m before Ondra",
    sub: "Calls, texts, email and WhatsApp",
  },
  {
    label: "Appointments booked",
    value: "23",
    delta: { up: true, text: "+9" },
    line: "19 by Ondra, 4 by your team",
    ai: true,
    sub: "Test drives 15, service 8",
  },
  {
    label: "Showed up",
    value: "78%",
    delta: { up: false, text: "−4 pts" },
    line: "18 of 23 kept their slot",
    sub: "Reminders sent the day before",
  },
]

export function SectionCards() {
  return (
    <div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4 dark:*:data-[slot=card]:bg-card">
      {CARDS.map((c) => (
        <Card key={c.label} className="@container/card">
          <CardHeader>
            <CardDescription>{c.label}</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">{c.value}</CardTitle>
            <CardAction>
              <Badge variant="outline" className={c.delta.up ? "" : "text-muted-foreground"}>
                {c.delta.up ? <IconTrendingUp /> : <IconTrendingDown />}
                {c.delta.text}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardFooter className="flex-col items-start gap-1.5 text-sm">
            <div className={`line-clamp-1 flex items-center gap-1.5 font-medium ${c.ai ? "text-ai" : ""}`}>
              {c.ai && <IconSparkles className="size-4" aria-hidden="true" />}
              {c.line}
            </div>
            <div className="text-muted-foreground">{c.sub}</div>
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}

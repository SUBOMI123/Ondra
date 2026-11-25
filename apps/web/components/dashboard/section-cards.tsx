import { IconTrendingDown, IconTrendingUp } from "@tabler/icons-react"

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
type Split = { ondra: number; team: number }
const CARDS: { label: string; value: string; delta: { up: boolean; text: string }; split?: Split; line?: string; sub: string }[] = [
  {
    label: "Leads answered after hours",
    value: "47",
    delta: { up: true, text: "+35%" },
    split: { ondra: 41, team: 6 },
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
    split: { ondra: 19, team: 4 },
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

/** Who did the work, as a proportion: Ondra's share in the AI blue, the team's in neutral. */
function SplitBar({ split }: { split: Split }) {
  const total = split.ondra + split.team
  const pct = (split.ondra / total) * 100
  return (
    <div className="flex w-full flex-col gap-2">
      <div
        className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`${split.ondra} by Ondra, ${split.team} by your team`}
      >
        <div className="h-full bg-ai" style={{ width: `${pct}%` }} />
        <div className="h-full bg-chart-2/60" style={{ width: `${100 - pct}%` }} />
      </div>
      <div className="flex items-center gap-4 text-sm tabular-nums">
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-[2px] bg-ai" aria-hidden="true" />
          <span className="text-muted-foreground">Ondra</span>
          <span className="font-medium">{split.ondra}</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-[2px] bg-chart-2/60" aria-hidden="true" />
          <span className="text-muted-foreground">Your team</span>
          <span className="font-medium">{split.team}</span>
        </span>
      </div>
    </div>
  )
}

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
          <CardFooter className="flex-col items-start gap-2 text-sm">
            {c.split ? <SplitBar split={c.split} /> : <div className="line-clamp-1 font-medium">{c.line}</div>}
            <div className="text-muted-foreground">{c.sub}</div>
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}

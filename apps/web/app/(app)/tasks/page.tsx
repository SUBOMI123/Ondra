"use client"

import { IconAlertTriangle, IconClock, IconPlus, IconUser } from "@tabler/icons-react"
import { useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { TASKS, type TaskCard } from "@/lib/examples"
import { cn } from "@/lib/utils"

const COLUMNS = [
  { key: "open", title: "To do" },
  { key: "in_progress", title: "In progress" },
  { key: "done", title: "Done today" },
] as const

function Source({ source }: { source: TaskCard["source"] }) {
  if (source === "handoff")
    return (
      <Badge variant="outline" className="gap-1 border-transparent bg-ai-subtle px-1.5 text-ai">
        <OndraMark className="size-3.5" /> Handoff from Ondra
      </Badge>
    )
  return (
    <Badge variant="outline" className="px-1.5 text-muted-foreground">
      {source === "rule" ? "From a rule" : "Added by hand"}
    </Badge>
  )
}

function Card({ t, done }: { t: TaskCard; done?: boolean }) {
  return (
    <article className={cn("flex flex-col gap-2.5 rounded-xl border bg-card p-3.5 text-sm shadow-xs", done && "opacity-70")}>
      <div className="flex items-start justify-between gap-2">
        <h3 className={cn("font-medium", done && "line-through decoration-muted-foreground/60")}>{t.title}</h3>
        {t.escalated && (
          <Badge variant="outline" className="shrink-0 gap-1 border-transparent bg-vip-subtle px-1.5 text-vip">
            <IconAlertTriangle /> Escalated
          </Badge>
        )}
      </div>
      <p className="text-muted-foreground">{t.client}</p>
      {t.brief && <p className="line-clamp-2 text-muted-foreground">{t.brief}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <Source source={t.source} />
      </div>
      <div className="flex items-center justify-between gap-2 border-t pt-2.5 text-xs">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <IconUser className="size-3.5" aria-hidden="true" /> {t.assignee}
        </span>
        <span className={cn("flex items-center gap-1 tabular-nums", t.overdue ? "font-medium text-vip" : "text-muted-foreground")}>
          <IconClock className="size-3.5" aria-hidden="true" />
          {t.overdue ? `Overdue, ${t.due}` : t.due}
        </span>
      </div>
    </article>
  )
}

export default function TasksPage() {
  const [who, setWho] = useState("all")
  const filter = (list: TaskCard[]) => (who === "mine" ? list.filter((t) => t.assignee === "Daniel Okafor") : list)
  const overdue = Object.values(TASKS).flat().filter((t) => t.overdue).length
  return (
    <>
      <SiteHeader title="Tasks" note="Example data until handoffs are live in Step 3" />
      <div className="flex flex-col gap-4 p-4 lg:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <ToggleGroup type="single" variant="outline" size="sm" value={who} onValueChange={(v) => v && setWho(v)} aria-label="Whose tasks">
              <ToggleGroupItem value="all" className="px-3">Everyone</ToggleGroupItem>
              <ToggleGroupItem value="mine" className="px-3">Mine</ToggleGroupItem>
            </ToggleGroup>
            {overdue > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-vip">
                <IconClock className="size-4" aria-hidden="true" /> {overdue} overdue
              </span>
            )}
          </div>
          <Button size="sm">
            <IconPlus /> New task
          </Button>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {COLUMNS.map((col) => {
            const items = filter(TASKS[col.key])
            return (
              <section key={col.key} className="flex flex-col gap-3 rounded-xl bg-muted/40 p-3" aria-label={col.title}>
                <h2 className="flex items-center justify-between px-1 text-sm font-medium">
                  {col.title}
                  <span className="text-muted-foreground tabular-nums">{items.length}</span>
                </h2>
                {items.length === 0 ? (
                  <p className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">Nothing here.</p>
                ) : (
                  items.map((t) => <Card key={t.title} t={t} done={col.key === "done"} />)
                )}
              </section>
            )
          })}
        </div>
      </div>
    </>
  )
}

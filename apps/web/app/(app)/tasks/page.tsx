"use client"

/**
 * Tasks. One job: "what do I do next?" A to-do list grouped by urgency, where finishing a task is one tap.
 * Where a task came from (Ondra's handoff, a rule) is a quiet mark, and the brief opens only when wanted.
 */

import { IconChevronDown, IconPlus } from "@tabler/icons-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { TASKS, type TaskCard } from "@/lib/examples"
import { cn } from "@/lib/utils"

const ME = "Daniel Okafor" // example signed-in salesperson for the "Mine" view
type Task = TaskCard & { id: string; done: boolean }

const ALL: Task[] = [
  ...TASKS.open.map((t, i) => ({ ...t, id: `o${i}`, done: false })),
  ...TASKS.in_progress.map((t, i) => ({ ...t, id: `p${i}`, done: false })),
  ...TASKS.done.map((t, i) => ({ ...t, id: `d${i}`, done: true })),
]

function group(t: Task): "Overdue" | "Today" | "Later" {
  if (t.overdue) return "Overdue"
  return t.due.startsWith("Today") ? "Today" : "Later"
}

function TaskRow({ t, onToggle }: { t: Task; onToggle: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="px-4 py-3">
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex items-start gap-3">
          <Checkbox checked={t.done} onCheckedChange={onToggle} className="mt-0.5 size-5" aria-label={t.done ? `Mark "${t.title}" as not done` : `Mark "${t.title}" as done`} />
          <div className="min-w-0 flex-1">
            <p className={cn("flex items-center gap-1.5 font-medium", t.done && "text-muted-foreground line-through")}>
              {t.source === "handoff" && <OndraMark className="size-3.5 shrink-0 text-ai" />}
              {t.source === "handoff" && <span className="sr-only">Handed off by Ondra:</span>}
              <span className="truncate">{t.title}</span>
            </p>
            <p className="truncate text-sm text-muted-foreground">
              {t.client}
              {t.assignee !== ME && `, ${t.assignee}`}
            </p>
          </div>
          <span className={cn("shrink-0 text-sm tabular-nums", t.overdue && !t.done ? "font-medium text-vip" : "text-muted-foreground")}>
            {t.due.replace(/^Today, /, "")}
          </span>
          {t.brief && (
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="icon" className="-my-1 size-8 shrink-0" aria-label={open ? "Hide details" : "Show details"}>
                <IconChevronDown className={cn("transition-transform", open && "rotate-180")} />
              </Button>
            </CollapsibleTrigger>
          )}
        </div>
        {t.brief && (
          <CollapsibleContent>
            <p className="mt-2 ml-8 text-sm text-muted-foreground">
              {t.source === "handoff" && <span className="text-ai">Ondra&apos;s brief: </span>}
              {t.brief}
            </p>
          </CollapsibleContent>
        )}
      </Collapsible>
    </li>
  )
}

export default function TasksPage() {
  const [who, setWho] = useState("mine")
  const [tasks, setTasks] = useState(ALL)
  const [showDone, setShowDone] = useState(false)

  const visible = useMemo(() => tasks.filter((t) => who === "all" || t.assignee === ME), [tasks, who])
  const open = visible.filter((t) => !t.done)
  const done = visible.filter((t) => t.done)
  const groups = (["Overdue", "Today", "Later"] as const).map((g) => ({ g, items: open.filter((t) => group(t) === g) })).filter((x) => x.items.length)

  function toggle(id: string) {
    const t = tasks.find((x) => x.id === id)!
    setTasks((all) => all.map((x) => (x.id === id ? { ...x, done: !x.done } : x)))
    if (!t.done)
      toast.success(`Done: ${t.title}`, {
        action: { label: "Undo", onClick: () => setTasks((all) => all.map((x) => (x.id === id ? { ...x, done: false } : x))) },
      })
  }

  return (
    <>
      <SiteHeader title="Tasks" note="Example data until handoffs are live in Step 3" />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 lg:px-6">
        <div className="flex items-center justify-between gap-3">
          <ToggleGroup type="single" variant="outline" size="sm" value={who} onValueChange={(v) => v && setWho(v)} aria-label="Whose tasks">
            <ToggleGroupItem value="mine" className="px-3">Mine</ToggleGroupItem>
            <ToggleGroupItem value="all" className="px-3">Everyone</ToggleGroupItem>
          </ToggleGroup>
          <Button size="sm">
            <IconPlus /> New task
          </Button>
        </div>

        {groups.length === 0 ? (
          <p className="rounded-xl border p-6 text-sm text-muted-foreground">You&apos;re clear. New handoffs from Ondra land here.</p>
        ) : (
          groups.map(({ g, items }) => (
            <section key={g} aria-labelledby={`g-${g}`}>
              <h2 id={`g-${g}`} className={cn("mb-2 text-sm font-medium", g === "Overdue" ? "text-vip" : "text-muted-foreground")}>
                {g} <span className="tabular-nums">{items.length}</span>
              </h2>
              <ul className="divide-y rounded-xl border">
                {items.map((t) => (
                  <TaskRow key={t.id} t={t} onToggle={() => toggle(t.id)} />
                ))}
              </ul>
            </section>
          ))
        )}

        {done.length > 0 && (
          <section>
            <button
              type="button"
              onClick={() => setShowDone((s) => !s)}
              aria-expanded={showDone}
              className="flex items-center gap-1.5 rounded-sm text-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
            >
              Done <span className="tabular-nums">{done.length}</span>
              <IconChevronDown className={cn("size-4 transition-transform", showDone && "rotate-180")} aria-hidden="true" />
            </button>
            {showDone && (
              <ul className="mt-2 divide-y rounded-xl border">
                {done.map((t) => (
                  <TaskRow key={t.id} t={t} onToggle={() => toggle(t.id)} />
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </>
  )
}

"use client"

/**
 * Tasks. Mine: "what do I do next?", a to-do list grouped by urgency, where finishing a task is one tap.
 * Everyone: a board with one column per person, to see whose work is slipping and move it (components/tasks).
 * Where a task came from (Ondra's handoff, a rule) is a quiet mark, and the brief opens only when wanted.
 * Data: GET/POST/PATCH /tasks. Deadlines come from urgency, counted in opening hours; overdue tasks escalate.
 */

import { IconChevronDown, IconMessage, IconPlus } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { TableSkeleton } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { type Person, TeamBoard } from "@/components/tasks/team-board"
import { VipTag } from "@/components/vip"
import { api, send } from "@/lib/api"
import { useLiveInbox } from "@/lib/live"
import { cn } from "@/lib/utils"
import { clock, fmt, isToday } from "@/lib/time"

type Task = {
  id: string
  title: string
  brief: string | null
  status: "open" | "in_progress" | "done" | "cancelled"
  urgency: "low" | "normal" | "high"
  source: "ai_handoff" | "rule" | "manual"
  due_at: string | null
  overdue: boolean
  escalated: boolean
  assignee: { id: string; name: string | null } | null
  contact: { id: string; name: string; is_vip: boolean } | null
  conversation_id: string | null
}

function due(iso: string | null) {
  if (!iso) return ""
  const d = new Date(iso)
  const time = clock(d)
  if (isToday(d)) return time
  return `${fmt(d, { weekday: "short", month: "short", day: "numeric" })}, ${time}`
}

function group(t: Task): "Overdue" | "Today" | "Later" {
  if (t.overdue) return "Overdue"
  return t.due_at && isToday(t.due_at) ? "Today" : "Later"
}

function TaskRow({ t, me, onToggle }: { t: Task; me: boolean; onToggle: () => void }) {
  const [open, setOpen] = useState(false)
  const done = t.status === "done"
  const title = t.title.includes(": ") && t.contact ? t.title.split(": ").slice(1).join(": ") : t.title
  return (
    <li className="px-4 py-3" data-vip={t.contact?.is_vip || undefined}>
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex items-start gap-3">
          <Checkbox checked={done} onCheckedChange={onToggle} className="mt-0.5 size-5" aria-label={done ? `Mark "${title}" as not done` : `Mark "${title}" as done`} />
          <div className="min-w-0 flex-1">
            <p className={cn("flex items-center gap-1.5 font-medium", done && "text-muted-foreground line-through")}>
              {t.source === "ai_handoff" && !t.contact?.is_vip && <OndraMark className="size-3.5 shrink-0 text-ai" />}
              {t.source === "ai_handoff" && !t.contact?.is_vip && <span className="sr-only">Handed off by Ondra:</span>}
              <span className="truncate first-letter:uppercase">{title}</span>
            </p>
            <p className="flex min-w-0 items-center gap-1.5 truncate text-sm text-muted-foreground">
              {t.contact?.is_vip && <VipTag />}
              {t.contact?.name ?? "No client"}
              {!me && t.assignee?.name && `, ${t.assignee.name}`}
              {t.escalated && !done && ", escalated"}
            </p>
          </div>
          <span className={cn("shrink-0 text-sm tabular-nums", t.overdue && !done ? "font-medium text-overdue" : "text-muted-foreground")}>
            {due(t.due_at)}
          </span>
          {(t.brief || t.conversation_id) && (
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="icon" className="-my-1 size-8 shrink-0" aria-label={open ? "Hide details" : "Show details"}>
                <IconChevronDown className={cn("transition-transform", open && "rotate-180")} />
              </Button>
            </CollapsibleTrigger>
          )}
        </div>
        <CollapsibleContent>
          <div className="mt-2 ml-8 flex flex-col items-start gap-2">
            {t.brief && (
              <p className="text-sm text-muted-foreground">
                {t.source === "ai_handoff" && <span className="text-ai">Ondra&apos;s brief: </span>}
                {t.brief}
              </p>
            )}
            {t.conversation_id && (
              <Button asChild variant="outline" size="sm">
                <Link href={`/inbox?c=${t.conversation_id}`}>
                  <IconMessage /> Open conversation
                </Link>
              </Button>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}

function NewTask({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState("")
  const [urgency, setUrgency] = useState("normal")
  const create = useMutation({
    mutationFn: () => send("POST", "/tasks", { title, urgency }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] })
      toast("Task added")
      onDone()
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't add the task."),
  })
  return (
    <form className="grid gap-4 rounded-xl border p-4 sm:grid-cols-[1fr_9rem_auto] sm:items-end" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
      <div className="grid gap-2">
        <Label htmlFor="task-title">What needs doing</Label>
        <Input id="task-title" required autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Call Kevin about financing" />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="task-urgency">Urgency</Label>
        <Select value={urgency} onValueChange={setUrgency}>
          <SelectTrigger id="task-urgency" className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="high">Within 15 min</SelectItem>
            <SelectItem value="normal">Within 2 hours</SelectItem>
            <SelectItem value="low">Within a day</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={create.isPending}>Add task</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  )
}

export default function TasksPage() {
  useLiveInbox()
  const qc = useQueryClient()
  const [who, setWho] = useState<"mine" | "all">("mine")
  const [showDone, setShowDone] = useState(false)
  const [adding, setAdding] = useState(false)
  const open = useQuery({ queryKey: ["tasks", who, "open"], queryFn: () => api<{ items: Task[]; people?: Person[] }>(`/tasks?scope=${who}&status=open`) })
  const done = useQuery({
    queryKey: ["tasks", who, "done"],
    queryFn: () => api<{ items: Task[] }>(`/tasks?scope=${who}&status=done`),
    enabled: showDone,
  })
  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: Task["status"] }) => send("PATCH", `/tasks/${id}`, { status }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't update the task."),
  })

  function toggle(t: Task) {
    const next = t.status === "done" ? "open" : "done"
    update.mutate({ id: t.id, status: next })
    if (next === "done")
      toast.success(`Done: ${t.title.split(": ").slice(-1)[0]}`, {
        action: { label: "Undo", onClick: () => update.mutate({ id: t.id, status: "open" }) },
      })
  }

  const items = open.data?.items ?? []
  const groups = (["Overdue", "Today", "Later"] as const)
    .map((g) => ({ g, items: items.filter((t) => group(t) === g) }))
    .filter((x) => x.items.length)

  return (
    <>
      <SiteHeader title="Tasks" />
      <div className={cn("mx-auto flex w-full flex-col gap-6 px-4 py-6 lg:px-6", who === "mine" ? "max-w-3xl" : "min-w-0")}>
        <div className="flex items-center justify-between gap-3">
          <Tabs value={who} onValueChange={(v) => setWho(v as "mine" | "all")}>
            <TabsList aria-label="Whose tasks">
              <TabsTrigger value="mine">Mine</TabsTrigger>
              <TabsTrigger value="all">Everyone</TabsTrigger>
            </TabsList>
          </Tabs>
          {!adding && (
            <Button size="sm" onClick={() => setAdding(true)}>
              <IconPlus /> New task
            </Button>
          )}
        </div>
        {adding && <NewTask onDone={() => setAdding(false)} />}

        {open.isPending ? (
          <TableSkeleton rows={4} />
        ) : open.isError ? (
          <div className="space-y-3 rounded-xl border p-6 text-sm" role="alert">
            <p>Tasks didn&apos;t load. {open.error instanceof Error ? open.error.message : ""}</p>
            <Button variant="outline" onClick={() => open.refetch()}>Try again</Button>
          </div>
        ) : who === "all" && open.data.people ? (
          <TeamBoard tasks={items} people={open.data.people} onToggle={(t) => toggle(t as Task)} />
        ) : groups.length === 0 ? (
          <p className="rounded-xl border p-6 text-sm text-muted-foreground">You&apos;re clear. New handoffs from Ondra land here.</p>
        ) : (
          groups.map(({ g, items }) => (
            <section key={g} aria-labelledby={`g-${g}`}>
              <h2 id={`g-${g}`} className={cn("mb-2 text-sm font-medium", g === "Overdue" ? "text-overdue" : "text-muted-foreground")}>
                {g} <span className="tabular-nums">{items.length}</span>
              </h2>
              <ul className="divide-y rounded-xl border">
                {items.map((t) => (
                  <TaskRow key={t.id} t={t} me={who === "mine"} onToggle={() => toggle(t)} />
                ))}
              </ul>
            </section>
          ))
        )}

        <section>
          <button
            type="button"
            onClick={() => setShowDone((s) => !s)}
            aria-expanded={showDone}
            className="flex items-center gap-1.5 rounded-sm text-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            Done
            <IconChevronDown className={cn("size-4 transition-transform", showDone && "rotate-180")} aria-hidden="true" />
          </button>
          {showDone &&
            (done.isPending ? (
              <TableSkeleton rows={2} />
            ) : (done.data?.items ?? []).length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">Nothing finished yet.</p>
            ) : (
              <ul className="mt-2 divide-y rounded-xl border">
                {done.data!.items.map((t) => (
                  <TaskRow key={t.id} t={t} me={who === "mine"} onToggle={() => toggle(t)} />
                ))}
              </ul>
            ))}
        </section>
      </div>
    </>
  )
}

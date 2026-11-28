"use client"

/**
 * Tasks > Everyone. One job: see who has what on their plate, spot whose work is slipping, and move work to someone
 * who can take it. One column per person who takes work (overdue count in red at the top), plus "Nobody yet" when
 * something is unassigned. Drag a card to another person to give it to them (press and hold on a phone); the card's
 * menu does the same by keyboard. Ticking a card finishes it, same as the list.
 */

import { DndContext, type DragEndEvent, DragOverlay, MouseSensor, TouchSensor, useDraggable, useDroppable, useSensor, useSensors } from "@dnd-kit/core"
import { IconDotsVertical } from "@tabler/icons-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { VipTag } from "@/components/vip"
import { send } from "@/lib/api"
import { clock, daysAgo, fmt } from "@/lib/time"
import { cn } from "@/lib/utils"

export type BoardTask = {
  id: string; title: string; status: string; source: string; due_at: string | null; overdue: boolean
  assignee: { id: string; name: string | null } | null
  contact: { id: string; name: string; is_vip: boolean } | null
}
export type Person = { id: string; name: string; role: string }

const ROLE: Record<string, string> = { admin: "Admin", manager: "Manager", sales: "Sales", service: "Service", ops: "Operations" }
const NOBODY = "nobody"

/** Short enough for a card: "today, 3:08 pm", "yesterday, 9:30 am", "Monday, 10 am", then "Nov 20". */
function short(iso: string) {
  const days = daysAgo(iso)
  if (days === 0) return `today, ${clock(iso)}`
  if (days === 1) return `yesterday, ${clock(iso)}`
  if (days === -1) return `tomorrow, ${clock(iso)}`
  if (Math.abs(days) < 7) return `${fmt(iso, { weekday: "long" })}, ${clock(iso)}`
  return fmt(iso, { month: "short", day: "numeric" })
}

function Card({ t, people, onToggle, onGive, overlay }: {
  t: BoardTask; people: Person[]
  onToggle?: () => void; onGive?: (p: Person) => void; overlay?: boolean
}) {
  const drag = useDraggable({ id: t.id, disabled: overlay })
  const title = t.title.includes(": ") && t.contact ? t.title.split(": ").slice(1).join(": ") : t.title
  return (
    <li
      ref={drag.setNodeRef}
      {...drag.listeners}
      data-vip={t.contact?.is_vip || undefined}
      className={cn(
        "flex touch-manipulation cursor-grab items-start gap-2.5 rounded-xl border bg-card p-3 text-sm select-none hover:border-foreground/25",
        drag.isDragging && "opacity-40",
        overlay && "cursor-grabbing shadow-lg",
      )}
    >
      <Checkbox checked={t.status === "done"} onCheckedChange={onToggle} className="mt-0.5 size-[1.125rem]" aria-label={`Mark "${title}" as done`} />
      <div className="min-w-0 flex-1">
        <p className="flex items-start gap-1.5 font-medium">
          {t.source === "ai_handoff" && !t.contact?.is_vip && <OndraMark className="mt-0.5 size-3.5 shrink-0 text-ai" />}
          {t.source === "ai_handoff" && !t.contact?.is_vip && <span className="sr-only">Handed off by Ondra:</span>}
          <span className="line-clamp-2 first-letter:uppercase">{title}</span>
        </p>
        <p className="mt-0.5 flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
          {t.contact?.is_vip && <VipTag />}
          <span className="truncate">{t.contact?.name ?? "No client"}</span>
        </p>
        {t.due_at && (
          <p className={cn("mt-1 text-xs tabular-nums", t.overdue ? "font-medium text-overdue" : "text-muted-foreground")}>
            {t.overdue ? `Overdue since ${short(t.due_at)}` : `Due ${short(t.due_at)}`}
          </p>
        )}
      </div>
      {!overlay && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="-mt-1.5 -mr-1.5 size-8 shrink-0" aria-label={`Give "${title}" to someone`}><IconDotsVertical /></Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Give to</DropdownMenuLabel>
            {people.filter((p) => p.id !== t.assignee?.id).map((p) => (
              <DropdownMenuItem key={p.id} onSelect={() => onGive?.(p)}>{p.name}</DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </li>
  )
}

function Column({ id, name, role, tasks, dragging, children }: {
  id: string; name: string; role: string | null; tasks: BoardTask[]; dragging: boolean; children: React.ReactNode
}) {
  const drop = useDroppable({ id })
  const late = tasks.filter((t) => t.overdue).length
  return (
    <section
      ref={drop.setNodeRef}
      aria-label={name}
      className={cn("flex flex-col gap-2.5 rounded-xl bg-muted/40 p-2.5 transition-colors", dragging && drop.isOver && "bg-muted ring-2 ring-foreground/20")}
    >
      <header className="px-1 pt-0.5">
        <h2 className="truncate text-sm font-medium">{name}</h2>
        <p className="text-xs text-muted-foreground tabular-nums">
          {role && `${role}, `}{tasks.length === 0 ? "nothing open" : `${tasks.length} open`}
          {late > 0 && <span className="font-medium text-overdue">, {late} overdue</span>}
        </p>
      </header>
      {tasks.length === 0 ? (
        <p className="px-1 pb-1 text-xs text-muted-foreground">{dragging ? "Drop here to give it to them" : "Free to take something on."}</p>
      ) : (
        <ul className="flex flex-col gap-2">{children}</ul>
      )}
    </section>
  )
}

export function TeamBoard({ tasks, people, onToggle }: {
  tasks: BoardTask[]; people: Person[]; onToggle: (t: BoardTask) => void
}) {
  const qc = useQueryClient()
  const [dragging, setDragging] = useState<string | null>(null)
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
  )
  const give = useMutation({
    mutationFn: (v: { t: BoardTask; p: Person }) => send("PATCH", `/tasks/${v.t.id}`, { assignee_user_id: v.p.id }),
    onSuccess: (_r, v) => {
      const back = v.t.assignee
      toast(`Given to ${v.p.name}.`, back ? {
        action: { label: "Undo", onClick: () => send("PATCH", `/tasks/${v.t.id}`, { assignee_user_id: back.id }).then(() => qc.invalidateQueries({ queryKey: ["tasks"] })) },
      } : undefined)
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't give the task to them. Try again."),
    onSettled: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  })
  // Overdue first, then soonest due: the top of a column is what that person should do next.
  const order = (a: BoardTask, b: BoardTask) => Number(b.overdue) - Number(a.overdue) || (a.due_at ?? "9").localeCompare(b.due_at ?? "9")
  const of = (id: string) => tasks.filter((t) => (t.assignee?.id ?? NOBODY) === id).sort(order)
  // Busiest first, so slipping work is on screen without scrolling.
  const columns = [...people]
    .map((p) => ({ ...p, tasks: of(p.id) }))
    .sort((a, b) => b.tasks.filter((t) => t.overdue).length - a.tasks.filter((t) => t.overdue).length || b.tasks.length - a.tasks.length || a.name.localeCompare(b.name))
  const unassigned = of(NOBODY)
  const held = dragging ? tasks.find((t) => t.id === dragging) : null

  const onDragEnd = (e: DragEndEvent) => {
    setDragging(null)
    const t = tasks.find((x) => x.id === e.active.id)
    const p = people.find((x) => x.id === e.over?.id)
    if (t && p && t.assignee?.id !== p.id) give.mutate({ t, p })
  }

  return (
    <DndContext sensors={sensors} onDragStart={(e) => setDragging(String(e.active.id))} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}>
      <div className="relative -mx-4 overflow-x-auto px-4 pb-2 lg:-mx-6 lg:px-6">
        <div className="grid auto-cols-[17rem] grid-flow-col gap-3">
          {unassigned.length > 0 && (
            <Column id={NOBODY} name="Nobody yet" role={null} tasks={unassigned} dragging={!!dragging}>
              {unassigned.map((t) => <Card key={t.id} t={t} people={people} onToggle={() => onToggle(t)} onGive={(p) => give.mutate({ t, p })} />)}
            </Column>
          )}
          {columns.map((c) => (
            <Column key={c.id} id={c.id} name={c.name} role={ROLE[c.role] ?? c.role} tasks={c.tasks} dragging={!!dragging}>
              {c.tasks.map((t) => <Card key={t.id} t={t} people={people} onToggle={() => onToggle(t)} onGive={(p) => give.mutate({ t, p })} />)}
            </Column>
          ))}
        </div>
      </div>
      <DragOverlay dropAnimation={null}>
        {held ? <ul className="w-[17rem]"><Card t={held} people={people} overlay /></ul> : null}
      </DragOverlay>
    </DndContext>
  )
}

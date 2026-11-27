"use client"

/**
 * Deals. One job: see every open sale by how far along it is, know what each one needs next, and move it when it
 * moves. Drag a card to another stage (or use its menu, which also works by keyboard); dropping on Lost asks why.
 * Open a card for the whole deal. "Mine" shows the deals you've been given, and is where a salesperson starts.
 * Real deals only: one starts when Ondra or someone on the team records what a buyer wants, and Ondra gives it a
 * salesperson by the dealer's routing rules. A value is an estimate (the listed price of the car in stock they asked
 * about, else their own budget) and is left blank when there's nothing to base it on.
 */

import { IconBell, IconCalendarEvent, IconDotsVertical } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { DealSheet, LOST_REASONS, type Stage, stamp } from "@/components/deals/deal-sheet"
import { LoadError } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { useAuth } from "@/components/providers"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { VipTag } from "@/components/vip"
import { api, send } from "@/lib/api"
import { cn } from "@/lib/utils"

type Deal = {
  id: string; contact_id: string; client: string; vip: boolean; stage: Stage; wants: string | null; note: string | null
  owner: string | null; owner_id: string | null; value: number | null; value_from: string | null; by_ondra: boolean; lost_reason: string | null
  last_contact_at: string | null
  next_appointment: { starts_at: string; what: string } | null
  next_task: { title: string; due_at: string | null; overdue: boolean } | null
}
type Board = {
  stages: { stage: Stage; label: string; deals: Deal[] }[]
  open: number; open_value: number; open_without_value: number; open_by_ondra: number; can_move: boolean
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const compact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 })

/** "Today", "Yesterday", "3 days ago", then a date. For "last in touch" on a card. */
function ago(iso: string | null) {
  if (!iso) return "Not in touch yet"
  const days = Math.round((new Date(new Date().toDateString()).getTime() - new Date(new Date(iso).toDateString()).getTime()) / 86_400_000)
  if (days <= 0) return "In touch today"
  if (days === 1) return "In touch yesterday"
  if (days < 14) return `In touch ${days} days ago`
  return `In touch ${new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`
}

/** The one thing this deal needs next: a booked visit beats a task, and an overdue task says so in red. */
function Next({ d }: { d: Deal }) {
  if (d.stage === "lost") return d.lost_reason ? <p className="truncate text-xs text-muted-foreground">{d.lost_reason}</p> : null
  if (d.next_appointment)
    return (
      <p className="flex min-w-0 items-center gap-1.5 text-xs">
        <IconCalendarEvent className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="truncate"><span className="first-letter:uppercase">{d.next_appointment.what}</span>, {stamp(d.next_appointment.starts_at)}</span>
      </p>
    )
  if (d.next_task)
    return (
      <p className={cn("flex min-w-0 items-center gap-1.5 text-xs", d.next_task.overdue && "text-overdue")}>
        <IconBell className="size-3.5 shrink-0" aria-hidden="true" />
        <span className="truncate">{d.next_task.title}{d.next_task.overdue ? ", overdue" : ""}</span>
      </p>
    )
  if (d.stage === "won") return null
  return <p className="text-xs text-muted-foreground">Nothing booked or due</p>
}

function Card({ d, board, onOpen, onMove, dragging, setDragging }: {
  d: Deal; board: Board; onOpen: () => void; onMove: (stage: Stage, reason?: string) => void
  dragging: string | null; setDragging: (id: string | null) => void
}) {
  return (
    <article
      className={cn(
        "relative flex flex-col gap-1.5 rounded-xl border bg-card p-3 text-sm outline-none hover:border-foreground/25 has-[button[data-open]:focus-visible]:ring-2 has-[button[data-open]:focus-visible]:ring-ring",
        board.can_move && "cursor-grab active:cursor-grabbing",
        dragging === d.id && "opacity-40",
      )}
      data-vip={d.vip || undefined}
      draggable={board.can_move}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", d.id)
        e.dataTransfer.effectAllowed = "move"
        setDragging(d.id)
      }}
      onDragEnd={() => setDragging(null)}
    >
      <div className="flex items-start justify-between gap-1">
        <p className="flex min-w-0 items-center gap-1.5 font-medium">
          {d.vip && <VipTag />}
          {/* The whole card opens the deal; the button carries the name for screen readers and keyboard. */}
          <button type="button" data-open onClick={onOpen} className="truncate text-left outline-none after:absolute after:inset-0 after:rounded-xl">
            {d.client}
          </button>
        </p>
        {board.can_move && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="relative z-10 -mt-1.5 -mr-1.5 size-8 shrink-0" aria-label={`Move ${d.client}'s deal`}><IconDotsVertical /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Move to</DropdownMenuLabel>
              {board.stages.filter((s) => s.stage !== d.stage && s.stage !== "lost").map((s) => (
                <DropdownMenuItem key={s.stage} onSelect={() => onMove(s.stage)}>{s.label}</DropdownMenuItem>
              ))}
              {d.stage !== "lost" && (
                <>
                  <DropdownMenuLabel>Lost, because</DropdownMenuLabel>
                  {LOST_REASONS.map((r) => <DropdownMenuItem key={r} onSelect={() => onMove("lost", r)}>{r}</DropdownMenuItem>)}
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <p className="truncate text-muted-foreground" title={d.wants ?? undefined}>{d.wants ?? "Hasn't said what they want"}</p>
        {d.value != null && <span className="shrink-0 font-medium tabular-nums" title={`Estimate from the ${d.value_from}`}>{usd.format(d.value)}</span>}
      </div>
      <Next d={d} />
      <div className="mt-0.5 flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="flex min-w-0 items-center gap-1.5">
          {d.by_ondra && <OndraMark className="size-3.5 shrink-0 text-ai" />}
          {d.by_ondra && <span className="sr-only">Brought in by Ondra.</span>}
          <span className="truncate">{d.owner ?? "Nobody yet"}</span>
        </span>
        <span className="shrink-0 tabular-nums">{ago(d.last_contact_at)}</span>
      </div>
    </article>
  )
}

function Deals() {
  const qc = useQueryClient()
  const router = useRouter()
  const params = useSearchParams()
  const open = params.get("deal")
  const { me } = useAuth()
  const [whose, setWhose] = useState<"mine" | "everyone">(me?.role === "sales" ? "mine" : "everyone")
  const [dragging, setDragging] = useState<string | null>(null)
  const [over, setOver] = useState<Stage | null>(null)
  const [losing, setLosing] = useState<Deal | null>(null)
  const q = useQuery({ queryKey: ["deals"], queryFn: () => api<Board>("/deals") })

  const move = useMutation({
    mutationFn: (v: { d: Deal; stage: Stage; reason?: string }) => send("PATCH", `/deals/${v.d.id}`, { stage: v.stage, lost_reason: v.reason }),
    onMutate: async (v) => {
      // Move the card at once; the server confirms (or the error puts it back).
      await qc.cancelQueries({ queryKey: ["deals"] })
      const before = qc.getQueryData<Board>(["deals"])
      if (before)
        qc.setQueryData<Board>(["deals"], {
          ...before,
          stages: before.stages.map((s) => ({
            ...s,
            deals: s.stage === v.stage ? [{ ...v.d, stage: v.stage, lost_reason: v.reason ?? null }, ...s.deals.filter((x) => x.id !== v.d.id)] : s.deals.filter((x) => x.id !== v.d.id),
          })),
        })
      return { before }
    },
    onSuccess: (_r, v) => {
      const label = q.data?.stages.find((s) => s.stage === v.stage)?.label ?? v.stage
      const from = v.d.stage
      toast(`${v.d.client} moved to ${label}.`, {
        action: { label: "Undo", onClick: () => send("PATCH", `/deals/${v.d.id}`, { stage: from }).then(() => qc.invalidateQueries({ queryKey: ["deals"] }), () => toast("Couldn't undo. Move it back from its menu.")) },
      })
    },
    onError: (e, _v, ctx) => {
      if (ctx?.before) qc.setQueryData(["deals"], ctx.before)
      toast(e instanceof Error ? e.message : "Couldn't move the deal. Try again.")
    },
    onSettled: (_r, _e, v) => {
      qc.invalidateQueries({ queryKey: ["deals"] })
      qc.invalidateQueries({ queryKey: ["deal", v.d.id] })
      qc.invalidateQueries({ queryKey: ["analytics"] })
    },
  })

  const b = q.data
  const all = b?.stages.flatMap((s) => s.deals) ?? []
  const find = (id: string) => all.find((d) => d.id === id)
  const shown = (d: Deal) => whose === "everyone" || d.owner_id === me?.id
  const mineCount = all.filter((d) => d.owner_id === me?.id && !["won", "lost"].includes(d.stage)).length
  const drop = (stage: Stage, id: string) => {
    const d = find(id)
    setOver(null)
    setDragging(null)
    if (!d || d.stage === stage) return
    if (stage === "lost") setLosing(d)
    else move.mutate({ d, stage })
  }
  const setOpen = (id: string | null) => router.replace(id ? `/deals?deal=${id}` : "/deals", { scroll: false })

  return (
    <>
      <SiteHeader title="Deals" />
      <div className="flex min-w-0 flex-col gap-4 p-4 lg:p-6">
        {q.isPending ? (
          <div className="grid auto-cols-[17rem] grid-flow-col gap-3 overflow-hidden" aria-busy="true" aria-label="Loading">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-64 rounded-xl" />)}
          </div>
        ) : q.isError ? (
          <LoadError message={q.error.message} onRetry={() => q.refetch()} />
        ) : b && all.length === 0 ? (
          <div className="max-w-prose rounded-xl border p-6 text-sm">
            <p className="font-medium">No deals yet</p>
            <p className="mt-1 text-muted-foreground">A deal starts when a buyer says what they&apos;re looking for and Ondra or someone on your team records it. They show here by how far along they are.</p>
          </div>
        ) : b && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground tabular-nums">
                <span>
                  {b.open} open{b.open_value > 0 && `, about ${compact.format(b.open_value)}`}
                  {b.open_without_value > 0 && b.open_value > 0 && ` (${b.open_without_value} with no price to go on yet)`}
                </span>
                {b.open_by_ondra > 0 && (
                  <span data-slot="ai-note" className="flex items-center gap-1 text-ai"><OndraMark className="size-3.5" /> {b.open_by_ondra} brought in by Ondra</span>
                )}
              </p>
              <Tabs value={whose} onValueChange={(v) => setWhose(v as "mine" | "everyone")}>
                <TabsList aria-label="Whose deals">
                  <TabsTrigger value="mine">Mine<span className="ml-1.5 text-muted-foreground tabular-nums">{mineCount}</span></TabsTrigger>
                  <TabsTrigger value="everyone">Everyone</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            {whose === "mine" && mineCount === 0 && all.every((d) => !shown(d)) ? (
              <div className="max-w-prose rounded-xl border p-6 text-sm">
                <p className="font-medium">No deals of yours yet</p>
                <p className="mt-1 text-muted-foreground">When Ondra opens a deal it gives it to the next salesperson in turn, and a manager can hand you one from the deal itself. Everyone shows the whole board.</p>
              </div>
            ) : (
              <div className="-mx-4 overflow-x-auto px-4 pb-2 lg:-mx-6 lg:px-6">
                <div className="grid auto-cols-[17rem] grid-flow-col gap-3">
                  {b.stages.map((s) => {
                    const deals = s.deals.filter(shown)
                    const sum = deals.reduce((a, d) => a + (d.value ?? 0), 0)
                    return (
                      <section
                        key={s.stage}
                        aria-label={s.label}
                        className={cn("flex flex-col gap-2.5 rounded-xl bg-muted/40 p-2.5 transition-colors", over === s.stage && "bg-muted ring-2 ring-foreground/20")}
                        onDragOver={(e) => {
                          if (!dragging) return
                          e.preventDefault()
                          e.dataTransfer.dropEffect = "move"
                          if (over !== s.stage) setOver(s.stage)
                        }}
                        onDragLeave={(e) => {
                          if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(null)
                        }}
                        onDrop={(e) => {
                          e.preventDefault()
                          drop(s.stage, e.dataTransfer.getData("text/plain"))
                        }}
                      >
                        <h2 className="flex items-baseline justify-between px-1 pt-0.5 text-sm font-medium">
                          {s.label}
                          <span className="text-xs font-normal text-muted-foreground tabular-nums">{deals.length}{sum > 0 && `, ${compact.format(sum)}`}</span>
                        </h2>
                        {deals.length === 0 && (
                          <p className="px-1 pb-1 text-xs text-muted-foreground">
                            {dragging ? "Drop here" : s.stage === "won" || s.stage === "lost" ? "None in the last 30 days." : "None right now."}
                          </p>
                        )}
                        {deals.map((d) => (
                          <Card key={d.id} d={d} board={b} onOpen={() => setOpen(d.id)} onMove={(stage, reason) => move.mutate({ d, stage, reason })}
                            dragging={dragging} setDragging={setDragging} />
                        ))}
                      </section>
                    )
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* While dragging, Won and Lost wait at the bottom of the screen: the board is wider than most screens, and
          those two columns are the ones off the edge. */}
      {dragging && b?.can_move && (
        <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center gap-3 p-4 md:pl-[calc(var(--sidebar-width)+1rem)]">
          {(["won", "lost"] as const).map((stage) => (
            <div
              key={stage}
              className={cn(
                "pointer-events-auto flex h-16 w-56 items-center justify-center rounded-xl border-2 border-dashed bg-background text-sm font-medium shadow-sm transition-colors",
                over === stage ? "border-foreground bg-muted" : "border-foreground/30",
              )}
              onDragOver={(e) => {
                e.preventDefault()
                e.dataTransfer.dropEffect = "move"
                if (over !== stage) setOver(stage)
              }}
              onDragLeave={() => setOver(null)}
              onDrop={(e) => {
                e.preventDefault()
                drop(stage, e.dataTransfer.getData("text/plain"))
              }}
            >
              {stage === "won" ? "Drop to mark as won" : "Drop to mark as lost"}
            </div>
          ))}
        </div>
      )}

      <DealSheet id={open} onClose={() => setOpen(null)} onMove={(id, stage, reason) => {
        const d = find(id)
        if (d) move.mutate({ d, stage, reason })
      }} />

      {/* Dropped on Lost: ask why before moving, since the reason is what the owner learns from. */}
      <Dialog open={!!losing} onOpenChange={(o) => !o && setLosing(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-medium">Why was {losing?.client.split(" ")[0]}&apos;s deal lost?</DialogTitle>
            <DialogDescription>It moves to Lost with this reason. You can undo it.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            {LOST_REASONS.map((r) => (
              <Button key={r} variant="outline" className="justify-start" onClick={() => {
                if (losing) move.mutate({ d: losing, stage: "lost", reason: r })
                setLosing(null)
              }}>{r}</Button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default function DealsPage() {
  return (
    <Suspense fallback={null}>
      <Deals />
    </Suspense>
  )
}

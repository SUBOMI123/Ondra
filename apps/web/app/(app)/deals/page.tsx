"use client"

/**
 * Deals. One job: see every open sale by how far along it is, and move one when it moves.
 * Real deals only: one starts when Ondra or someone on the team records what a buyer wants. A value is an estimate
 * (the listed price of the car in stock they asked about, else their own budget) and is left blank when there's
 * nothing to base it on. Moving a deal is what the Today page's pipeline counts.
 */

import { IconDotsVertical } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { VipTag } from "@/components/vip"
import { api, send } from "@/lib/api"

type Stage = "new" | "qualified" | "appointment" | "negotiating" | "won" | "lost"
type Deal = {
  id: string; contact_id: string; client: string; vip: boolean; stage: Stage; wants: string | null; note: string | null
  owner: string | null; value: number | null; value_from: string | null; by_ondra: boolean; lost_reason: string | null
}
type Board = {
  stages: { stage: Stage; label: string; deals: Deal[] }[]
  open: number; open_value: number; open_without_value: number; open_by_ondra: number; can_move: boolean
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const compact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 })
const LOST_REASONS = ["Bought elsewhere", "Price", "Stopped replying", "Not ready to buy"]

function Card({ d, stages, canMove, onMove }: { d: Deal; stages: Board["stages"]; canMove: boolean; onMove: (stage: Stage, reason?: string) => void }) {
  return (
    <article className="relative flex flex-col gap-1 rounded-xl border bg-card p-3 text-sm" data-vip={d.vip || undefined}>
      <div className="flex items-start justify-between gap-1">
        <p className="flex min-w-0 items-center gap-1.5 font-medium">
          {d.vip && <VipTag />}
          <Link href={`/clients/profile?id=${d.contact_id}`} className="truncate rounded-sm outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring">{d.client}</Link>
        </p>
        {canMove && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="-mt-1.5 -mr-1.5 size-8 shrink-0" aria-label={`Move ${d.client}'s deal`}><IconDotsVertical /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Move to</DropdownMenuLabel>
              {stages.filter((s) => s.stage !== d.stage && s.stage !== "lost").map((s) => (
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
      <p className="truncate text-muted-foreground" title={d.wants ?? undefined}>{d.wants ?? "Hasn't said what they want yet"}</p>
      {(d.stage === "lost" ? d.lost_reason : d.note) && <p className="truncate text-xs text-muted-foreground" title={(d.stage === "lost" ? d.lost_reason : d.note) ?? undefined}>{d.stage === "lost" ? d.lost_reason : d.note}</p>}
      <div className="mt-1.5 flex items-center justify-between gap-2 text-xs">
        <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
          {d.by_ondra && <OndraMark className="size-3.5 shrink-0 text-ai" />}
          {d.by_ondra && <span className="sr-only">Brought in by Ondra.</span>}
          <span className="truncate">{d.owner ?? "Nobody yet"}</span>
        </span>
        {d.value != null && <span className="font-medium tabular-nums" title={`Estimate from the ${d.value_from}`}>{usd.format(d.value)}</span>}
      </div>
    </article>
  )
}

export default function DealsPage() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ["deals"], queryFn: () => api<Board>("/deals") })
  const move = useMutation({
    mutationFn: (v: { d: Deal; stage: Stage; reason?: string }) => send("PATCH", `/deals/${v.d.id}`, { stage: v.stage, lost_reason: v.reason }),
    onSuccess: (_r, v) => {
      qc.invalidateQueries({ queryKey: ["deals"] })
      qc.invalidateQueries({ queryKey: ["analytics"] })
      const label = q.data?.stages.find((s) => s.stage === v.stage)?.label ?? v.stage
      const from = v.d.stage
      toast(`${v.d.client} moved to ${label}.`, {
        action: { label: "Undo", onClick: () => send("PATCH", `/deals/${v.d.id}`, { stage: from }).then(() => qc.invalidateQueries({ queryKey: ["deals"] }), () => toast("Couldn't undo. Move it back from its menu.")) },
      })
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't move the deal. Try again."),
  })
  const b = q.data
  return (
    <>
      <SiteHeader title="Deals" />
      <div className="flex min-w-0 flex-col gap-4 p-4 lg:p-6">
        {q.isPending ? (
          <div className="grid auto-cols-[16rem] grid-flow-col gap-3 overflow-hidden" aria-busy="true" aria-label="Loading">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-64 rounded-xl" />)}
          </div>
        ) : q.isError ? (
          <LoadError message={q.error.message} onRetry={() => q.refetch()} />
        ) : b && b.stages.every((s) => s.deals.length === 0) ? (
          <div className="max-w-prose rounded-xl border p-6 text-sm">
            <p className="font-medium">No deals yet</p>
            <p className="mt-1 text-muted-foreground">A deal starts when a buyer says what they&apos;re looking for and Ondra or someone on your team records it. They show here by how far along they are.</p>
          </div>
        ) : b && (
          <>
            <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground tabular-nums">
              <span>
                {b.open} open{b.open_value > 0 && `, about ${compact.format(b.open_value)}`}
                {b.open_without_value > 0 && b.open_value > 0 && ` (${b.open_without_value} with no price to go on yet)`}
              </span>
              {b.open_by_ondra > 0 && (
                <span data-slot="ai-note" className="flex items-center gap-1 text-ai"><OndraMark className="size-3.5" /> {b.open_by_ondra} brought in by Ondra</span>
              )}
            </p>
            <div className="-mx-4 overflow-x-auto px-4 pb-2 lg:-mx-6 lg:px-6">
              <div className="grid auto-cols-[16rem] grid-flow-col gap-3">
                {b.stages.map((s) => {
                  const sum = s.deals.reduce((a, d) => a + (d.value ?? 0), 0)
                  return (
                    <section key={s.stage} className="flex flex-col gap-2.5 rounded-xl bg-muted/40 p-2.5" aria-label={s.label}>
                      <h2 className="flex items-baseline justify-between px-1 pt-0.5 text-sm font-medium">
                        {s.label}
                        <span className="text-xs font-normal text-muted-foreground tabular-nums">{s.deals.length}{sum > 0 && `, ${compact.format(sum)}`}</span>
                      </h2>
                      {s.deals.length === 0 && (
                        <p className="px-1 pb-1 text-xs text-muted-foreground">{s.stage === "won" || s.stage === "lost" ? "None in the last 30 days." : "None right now."}</p>
                      )}
                      {s.deals.map((d) => (
                        <Card key={d.id} d={d} stages={b.stages} canMove={b.can_move} onMove={(stage, reason) => move.mutate({ d, stage, reason })} />
                      ))}
                    </section>
                  )
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}

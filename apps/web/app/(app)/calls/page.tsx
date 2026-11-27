"use client"

/**
 * Calls. One job: who needs a call back, and what happened on each call.
 * A call Ondra is on sits on top. Call-backs come next, each saying why in words (including why no text went
 * out: the consent rule), then everything earlier. Details open in a side sheet with Ondra's summary and the
 * transcript. VIP calls ring the owner directly, so they never carry an Ondra summary or transcript.
 * Data: GET /calls, GET /calls/{id}, POST /calls/{id}/called-back; live updates refresh it.
 */

import {
  IconPhone,
  IconPhoneCall,
  IconPhoneIncoming,
  IconPhoneX,
} from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { api, send } from "@/lib/api"
import { useLiveInbox } from "@/lib/live"
import { cn } from "@/lib/utils"
import { VipTag } from "@/components/vip"
import { clock, fmt, isToday } from "@/lib/time"

type Handled = "ai" | "staff" | "owner" | "missed" | null
type Call = {
  id: string
  handled_by: Handled
  outcome: string | null
  started_at: string | null
  duration_s: number | null
  live: boolean
  needs_callback: boolean
  from_number: string | null
  contact: { id: string; name: string; is_vip: boolean } | null
  conversation_id: string | null
  transferred_to: string | null
  summary: string | null
  text_back: { sent: boolean; reason?: string } | null
  line: string
  recording_notice: boolean
}
type CallDetail = Call & {
  transcript: { who: "agent" | "caller"; text: string }[]
  recording_url: string | null
  problems?: { tool: string; crashed?: string; refused?: string }[]
}

const TOOL_WORDS: Record<string, string> = {
  book_appointment: "Booking",
  check_availability: "Checking open times",
  reschedule_or_cancel: "Changing the appointment",
  search_inventory: "Looking up stock",
  get_vehicle: "Looking up a car",
  search_knowledge: "Looking up an answer",
  handoff: "Passing it to the team",
  update_lead_fields: "Saving their details",
}

/* ---------------------------------------------------------------- formatting */

function length(s: number | null) {
  return s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : ""
}

function when(iso: string | null) {
  if (!iso) return ""
  const d = new Date(iso)
  const time = clock(d)
  return isToday(d) ? time : `${fmt(d, { month: "short", day: "numeric" })}, ${time}`
}

function phone(v?: string | null) {
  const m = v?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : (v ?? "")
}

function who(c: Call) {
  return c.contact && !c.contact.name.startsWith("+") ? c.contact.name : phone(c.from_number) || "Unknown caller"
}

/** Why a call is on the call-back list, or what happened, in plain words. */
function why(c: Call) {
  if (c.handled_by === "missed") {
    if (c.contact?.is_vip) return "Missed. Nobody picked up"
    if (c.text_back?.sent) return "Missed. Ondra texted them back"
    if (c.text_back?.reason === "opted out") return "Missed. No text sent: they opted out of texts"
    if (c.text_back) return "Missed. No text sent: they haven't agreed to texts"
    return "Missed call"
  }
  if (c.handled_by === "ai") return c.summary ?? "Answered by Ondra"
  if (c.handled_by === "staff" && c.transferred_to) return `Put through to ${c.transferred_to}`
  return c.line
}

/* ---------------------------------------------------------------- live call */

function Elapsed({ from }: { from: string }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  return <span className="tabular-nums">{length(Math.max(1, Math.round((now - new Date(from).getTime()) / 1000)))}</span>
}

function LiveCall({ c, onOpen }: { c: Call; onOpen: () => void }) {
  return (
    <section aria-label="Live call" className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-ai/30 bg-ai-subtle/40 p-4">
      <span className="relative flex size-9 shrink-0 items-center justify-center rounded-full bg-ai-subtle text-ai">
        <IconPhoneCall className="size-4" aria-hidden="true" />
        <span className="absolute inset-0 rounded-full border border-ai/40 motion-safe:animate-ping" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 font-medium">
          <OndraMark className="size-4 text-ai" /> Ondra is on a call now
        </p>
        <p className="text-sm text-muted-foreground">
          {who(c)}, {c.started_at && <Elapsed from={c.started_at} />}
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={onOpen}>
        Details
      </Button>
    </section>
  )
}

/* ---------------------------------------------------------------- list */

function CallRow({ c, onOpen }: { c: Call; onOpen: () => void }) {
  const vip = !!c.contact?.is_vip
  const missed = c.handled_by === "missed"
  const ai = c.handled_by === "ai"
  const Icon = missed ? IconPhoneX : IconPhoneIncoming
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        data-vip={vip || undefined}
        className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 px-4 py-3 text-left outline-none hover:bg-muted/50 focus-visible:bg-muted"
      >
        <span className="pt-1">
          <Icon
            className={cn("size-4 shrink-0", missed && vip ? "text-foreground" : ai ? "text-ai" : "text-muted-foreground")}
            aria-label={missed ? "Missed call" : "Incoming call"}
          />
        </span>
        <span className="min-w-0">
          <span className="flex items-center gap-1.5 font-medium">
            {vip && <VipTag />}
            <span className="truncate">{who(c)}</span>
          </span>
          <span className="mt-0.5 flex items-start gap-1.5 text-sm text-muted-foreground">
            {ai && <OndraMark className="mt-0.5 size-3.5 shrink-0 text-ai" />}
            <span className="line-clamp-2">{why(c)}</span>
          </span>
        </span>
        <span className="text-right text-xs text-muted-foreground tabular-nums">
          {when(c.started_at)}
          {c.duration_s ? <span className="block">{length(c.duration_s)}</span> : null}
        </span>
      </button>
    </li>
  )
}

function Group({ id, title, calls, onOpen, empty }: { id: string; title: string; calls: Call[]; onOpen: (c: Call) => void; empty: string }) {
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="mb-2 text-sm font-medium text-muted-foreground">
        {title} {calls.length > 0 && <span className="tabular-nums">{calls.length}</span>}
      </h2>
      {calls.length === 0 ? (
        <p className="rounded-xl border px-4 py-3 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="divide-y rounded-xl border">
          {calls.map((c) => (
            <CallRow key={c.id} c={c} onOpen={() => onOpen(c)} />
          ))}
        </ul>
      )}
    </section>
  )
}

/* ---------------------------------------------------------------- details */

function CallSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ["calls", id], queryFn: () => api<CallDetail>(`/calls/${id}`), enabled: !!id })
  const done = useMutation({
    mutationFn: () => send("POST", `/calls/${id}/called-back`),
    onSuccess: () => {
      toast("Marked as called back.")
      qc.invalidateQueries({ queryKey: ["calls"] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : "That didn't save. Try again."),
  })
  const c = q.data
  const vip = !!c?.contact?.is_vip
  const first = c ? who(c).split(" ")[0] : ""
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-md" data-vip={vip || undefined}>
        {!c ? (
          <div className="flex flex-col gap-3 p-4" aria-label="Loading call">
            <SheetTitle className="sr-only">Call</SheetTitle>
            {q.isError ? (
              <p className="text-sm text-muted-foreground">This call isn&apos;t available, or isn&apos;t visible to your role.</p>
            ) : (
              <>
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-4 w-56" />
                <Skeleton className="h-24 w-full" />
              </>
            )}
          </div>
        ) : (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-1.5">
                {vip && <VipTag />}
                {who(c)}
              </SheetTitle>
              <SheetDescription>
                {phone(c.from_number)}, {when(c.started_at)}
                {c.duration_s ? `, ${length(c.duration_s)}` : ""}
              </SheetDescription>
            </SheetHeader>
            <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 pb-4 text-sm">
              {c.needs_callback && (
                <div className="flex flex-wrap gap-2">
                  {c.from_number && (
                    <Button asChild>
                      <a href={`tel:${c.from_number}`}>
                        <IconPhone /> Call {first} back
                      </a>
                    </Button>
                  )}
                  <Button variant="outline" disabled={done.isPending} onClick={() => done.mutate()}>
                    Mark as called back
                  </Button>
                </div>
              )}
              <p className={cn(c.handled_by === "missed" && vip && "font-medium text-foreground", c.handled_by === "ai" && "text-ai")}>
                {vip && c.handled_by !== "missed"
                  ? "Rang you directly. Ondra doesn't answer VIP calls."
                  : c.handled_by === "ai"
                    ? "Answered by Ondra."
                    : why(c)}
              </p>
              {c.recording_notice && <p className="text-muted-foreground">Recording notice played</p>}

              {!vip && c.summary && (
                <section data-slot="ai-summary">
                  <h3 className="flex items-center gap-1.5 text-xs font-medium text-ai">
                    <OndraMark className="size-3.5" /> Summary by Ondra
                  </h3>
                  <p className="mt-1.5 leading-relaxed">{c.summary}</p>
                </section>
              )}

              {!!c.problems?.length && (
                <section>
                  <h3 className="mb-1.5 text-xs font-medium text-muted-foreground">What went wrong</h3>
                  <ul className="flex flex-col gap-1">
                    {c.problems.map((p, i) => (
                      <li key={i}>
                        {TOOL_WORDS[p.tool] ?? "A step"} {p.crashed ? "failed with an error." : `didn't go through: ${p.refused}`}
                      </li>
                    ))}
                  </ul>
                  {c.problems.some((p) => p.crashed) && (
                    <details className="mt-1.5 text-xs text-muted-foreground">
                      <summary className="cursor-pointer">Details for support</summary>
                      <ul className="mt-1 font-mono break-all">
                        {c.problems.filter((p) => p.crashed).map((p, i) => <li key={i}>{p.tool}: {p.crashed}</li>)}
                      </ul>
                    </details>
                  )}
                </section>
              )}

              {c.recording_url && (
                <section>
                  <h3 className="mb-2 text-xs font-medium text-muted-foreground">Recording</h3>
                  <audio controls preload="none" src={c.recording_url} className="w-full" />
                </section>
              )}

              {!vip && c.transcript.length > 0 && (
                <section>
                  <h3 className="mb-2 text-xs font-medium text-muted-foreground">Transcript</h3>
                  <ol className="flex flex-col gap-2.5">
                    {c.transcript.map((t, i) => (
                      <li key={i} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3">
                        <span className={cn("text-xs font-medium", t.who === "agent" ? "text-ai" : "text-muted-foreground")}>
                          {t.who === "agent" ? "Ondra" : first}
                        </span>
                        <span>{t.text}</span>
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              <p className="flex flex-wrap gap-4 text-muted-foreground">
                {c.conversation_id && (
                  <Link href={`/inbox?c=${c.conversation_id}`} className="underline-offset-4 hover:text-foreground hover:underline">
                    Open in Inbox
                  </Link>
                )}
                {c.contact && (
                  <Link href={`/clients/profile?id=${c.contact.id}`} className="underline-offset-4 hover:text-foreground hover:underline">
                    Client profile
                  </Link>
                )}
              </p>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

/* ---------------------------------------------------------------- page */

export default function CallsPage() {
  useLiveInbox()
  const q = useQuery({ queryKey: ["calls"], queryFn: () => api<{ items: Call[] }>("/calls") })
  const [open, setOpen] = useState<string | null>(null)
  // Deep link from the Inbox: /calls?call=<id> opens that call.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("call")
    if (id) setOpen(id)
  }, [])

  const items = q.data?.items ?? []
  const live = items.filter((c) => c.live)
  const callbacks = items.filter((c) => !c.live && c.needs_callback)
  const earlier = items.filter((c) => !c.live && !c.needs_callback)

  return (
    <>
      <SiteHeader title="Calls" />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-6 lg:px-6">
        {q.isPending ? (
          <TableSkeleton rows={6} />
        ) : q.isError ? (
          <LoadError message={q.error.message} onRetry={() => q.refetch()} />
        ) : items.length === 0 ? (
          <div className="rounded-xl border p-6">
            <p className="font-medium">No calls yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Calls to your dealership&apos;s number show up here once your phone line is connected to Ondra. Ondra answers,
              VIPs ring you directly, and missed calls land in a call-back list.
            </p>
          </div>
        ) : (
          <>
            {live.map((c) => (
              <LiveCall key={c.id} c={c} onOpen={() => setOpen(c.id)} />
            ))}
            <Group id="callbacks" title="Call back" calls={callbacks} onOpen={(c) => setOpen(c.id)} empty="Nobody is waiting for a call back." />
            <Group id="earlier" title="Earlier" calls={earlier} onOpen={(c) => setOpen(c.id)} empty="No other calls yet." />
          </>
        )}
      </div>
      <CallSheet id={open} onClose={() => setOpen(null)} />
    </>
  )
}

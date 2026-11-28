"use client"

/**
 * Calls. One job: ring back everyone who's waiting, and see what happened on every other call.
 * A call Ondra is on sits on top. Call-backs come next, one row per caller however many times they rang, each saying
 * why in words (including why no text went out: the consent rule), who's to ring them, and any try so far. Each row
 * dials in one tap and is marked done ("Spoke to them") or tried ("Left a message") right there. Everything earlier
 * says who rang back and how long it took. Filters: missed, Ondra answered, put through to a person.
 * Details open in a side sheet with Ondra's summary and the transcript. VIP calls ring their person directly, so they
 * never carry an Ondra summary or transcript.
 * Data: GET /calls?show=, GET /calls/{id}, POST /calls/{id}/called-back, POST /calls/{id}/reopen; live updates refresh it.
 */

import { IconChevronDown, IconPhone, IconPhoneCall, IconPhoneIncoming, IconPhoneOutgoing, IconPhoneX } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { useAuth } from "@/components/providers"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, send } from "@/lib/api"
import { useLiveInbox } from "@/lib/live"
import { cn } from "@/lib/utils"
import { VipTag } from "@/components/vip"
import { clock, daysAgo, fmt, isToday } from "@/lib/time"

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
  direction: "inbound" | "outbound"
  called_back: Stamp | null
  attempts: Stamp[]
  /** A call-back through the dealer's line: this call is one (outbound), or one is under way for this caller. */
  bridge: Bridge | null
  calling?: Bridge | null
  /** On the call-back list only: how many times they rang before anyone rang back, and who's to ring them. */
  rings?: number
  first_rang_at?: string | null
  callback_by?: string | null
}
type Stamp = { by: string | null; at: string | null; how?: "left_message" | "short" | "voicemail" | "no_answer" | "spoke"; seconds?: number | null }
type Bridge = { by: string | null; by_id: string | null; state: "ringing_you" | "asked" | "dialing_them" | "ended" | "you_missed" | "not_connected" | "failed"; result: string | null }
type Show = "all" | "missed" | "ondra" | "people"
const SHOWS: [Show, string][] = [["all", "All"], ["missed", "Missed"], ["ondra", "Ondra answered"], ["people", "Put through"]]
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

function times(n: number) {
  return n === 2 ? "twice" : `${n} times`
}

function firstName(name: string | null | undefined) {
  return name?.split(" ")[0] ?? "Someone"
}

/** "35 minutes later", "3 hours later", "the next day": how long the caller waited. */
function later(from: string | null, to: string | null) {
  if (!from || !to) return ""
  const mins = Math.max(1, Math.round((new Date(to).getTime() - new Date(from).getTime()) / 60000))
  if (mins < 60) return `${mins} ${mins === 1 ? "minute" : "minutes"} later`
  const h = Math.round(mins / 60)
  if (h < 24) return `${h} ${h === 1 ? "hour" : "hours"} later`
  return daysAgo(from) - daysAgo(to) === 1 ? "the next day" : `${Math.round(h / 24)} days later`
}

/** Who rang back, or who's to, and any tries so far: "Daniel left a message at 2:18 pm". */
function progress(c: Call) {
  if (c.called_back) return `Called back by ${firstName(c.called_back.by)} ${later(c.started_at, c.called_back.at)}`
  const last = c.attempts[c.attempts.length - 1]
  const did = last?.how === "no_answer" ? "called, no answer,"
    : last?.how === "voicemail" ? "called and got their voicemail"
      : last?.how === "short" ? `called for ${length(last.seconds ?? 0)}, likely voicemail,` : "left a message"
  const tried = last ? `${firstName(last.by)} ${did} ${isToday(last.at!) ? "at" : "on"} ${when(last.at)}` : ""
  // Who's to ring them, unless it's the same person who already tried ("Daniel left a message" says it).
  const owner = c.callback_by && (!last || last.by !== c.callback_by) ? `For ${firstName(c.callback_by)} to call back` : ""
  return [owner, tried].filter(Boolean).join(". ")
}

/** Why a call is on the call-back list, or what happened, in plain words. */
function why(c: Call) {
  if (c.direction === "outbound") return c.line  // "Daniel called them back", from the API
  if (c.handled_by === "missed") {
    const missed = (c.rings ?? 1) > 1 ? `Rang ${times(c.rings!)} since ${when(c.first_rang_at ?? null)}` : "Missed"
    if (c.contact?.is_vip) return `${missed}. Nobody picked up`
    if (c.text_back?.sent) return `${missed}. Ondra texted them back`
    if (c.text_back?.reason === "texted recently") return `${missed}. Ondra texted them back`
    if (c.text_back?.reason === "opted out") return `${missed}. No text sent: they opted out of texts`
    if (c.text_back) return `${missed}. No text sent: they haven't agreed to texts`
    return (c.rings ?? 1) > 1 ? missed : "Missed call"
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

/* ---------------------------------------------------------------- call-back actions */

function useCallBack() {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ["calls"] })
  return useMutation({
    mutationFn: (v: { c: Call; result: "reached" | "left_message" }) =>
      send<Call>("POST", `/calls/${v.c.id}/called-back`, { result: v.result }),
    onSuccess: (_r, { c, result }) => {
      const first = who(c).split(" ")[0]
      if (result === "left_message") toast(`Noted. ${first} stays on the call-back list.`)
      else
        toast(`${first} is marked as called back.`, {
          action: { label: "Undo", onClick: () => send("POST", `/calls/${c.id}/reopen`).then(refresh, () => toast("Couldn't undo it. Try again.")) },
        })
      refresh()
    },
    onError: (e) => toast(e instanceof Error ? e.message : "That didn't save. Try again."),
  })
}

function useBridge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (c: Call) => send<{ your_phone: string }>("POST", `/calls/${c.id}/bridge`),
    onSuccess: (r, c) => {
      toast(`Ondra is ringing you on ${phone(r.your_phone)}. Pick up and press 1 to call ${who(c).split(" ")[0]}.`)
      qc.invalidateQueries({ queryKey: ["calls"] })
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't start the call. Try again."),
  })
}

/** Where a call-back through Ondra has got to, in words, while it's happening. */
function Calling({ b, c }: { b: Bridge; c: Call }) {
  const { me } = useAuth()
  const mine = !!me && b.by_id === me.id
  const first = who(c).split(" ")[0]
  const text =
    b.state === "dialing_them" ? `${mine ? "You're" : `${firstName(b.by)} is`} on the line to ${first}.`
      : b.state === "asked" ? (mine ? `Press 1 on your phone to call ${first}.` : `${firstName(b.by)} is about to call ${first}.`)
        : mine ? "Ondra is ringing your phone. Pick up and press 1." : `Ondra is ringing ${firstName(b.by)} to call ${first} back.`
  return (
    <p role="status" className="flex items-center gap-2 text-sm">
      <IconPhoneCall className="size-4 shrink-0 text-muted-foreground motion-safe:animate-pulse" aria-hidden="true" /> {text}
    </p>
  )
}

function CallBackActions({ c, compact }: { c: Call; compact?: boolean }) {
  const done = useCallBack()
  const bridge = useBridge()
  const first = who(c).split(" ")[0]
  if (c.calling) return <Calling b={c.calling} c={c} />
  return (
    <div className="flex flex-wrap items-center gap-2">
      {c.from_number && (
        <Button variant={compact ? "outline" : "default"} size={compact ? "sm" : "default"} disabled={bridge.isPending}
          onClick={() => bridge.mutate(c)} aria-label={`Call ${who(c)} back. Ondra rings your phone first`}>
          <IconPhone /> Call {first} back
        </Button>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size={compact ? "sm" : "default"} disabled={done.isPending}>
            Called back <IconChevronDown />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => done.mutate({ c, result: "reached" })}>Spoke to {first}</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => done.mutate({ c, result: "left_message" })}>No answer, left a message</DropdownMenuItem>
          {c.from_number && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                {/* Not logged, and they'll see your own number. For when the dealership line can't be used. */}
                <a href={`tel:${c.from_number}`}>Call from your own phone, <span className="tabular-nums">{phone(c.from_number)}</span></a>
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

/* ---------------------------------------------------------------- list */

function CallRow({ c, onOpen }: { c: Call; onOpen: () => void }) {
  const vip = !!c.contact?.is_vip
  const missed = c.handled_by === "missed"
  const ai = c.handled_by === "ai"
  const out = c.direction === "outbound"
  const Icon = missed ? IconPhoneX : out ? IconPhoneOutgoing : IconPhoneIncoming
  const note = missed ? progress(c) : ""
  return (
    <li data-vip={vip || undefined} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 gap-y-2 px-4 py-3 hover:bg-muted/50">
      <span className="pt-1">
        <Icon
          className={cn("size-4 shrink-0", missed && vip ? "text-foreground" : ai ? "text-ai" : "text-muted-foreground")}
          aria-label={missed ? "Missed call" : out ? "Call back" : "Incoming call"}
        />
      </span>
      <button type="button" onClick={onOpen} className="min-w-0 rounded-sm text-left outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <span className="flex items-center gap-1.5 font-medium">
          {vip && <VipTag />}
          <span className="truncate">{who(c)}</span>
        </span>
        <span className="mt-0.5 flex items-start gap-1.5 text-sm text-muted-foreground">
          {ai && <OndraMark className="mt-0.5 size-3.5 shrink-0 text-ai" />}
          {ai && <span className="sr-only">Summary by Ondra:</span>}
          <span className="line-clamp-2">{why(c)}</span>
        </span>
        {note && <span className="mt-0.5 block text-sm text-muted-foreground">{note}</span>}
      </button>
      <span className="text-right text-xs text-muted-foreground tabular-nums">
        {when(c.started_at)}
        {c.duration_s ? <span className="block">{length(c.duration_s)}</span> : null}
      </span>
      {c.needs_callback && (
        <div className="col-start-2 col-end-4">
          <CallBackActions c={c} compact />
        </div>
      )}
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
  const q = useQuery({ queryKey: ["calls", id], queryFn: () => api<CallDetail>(`/calls/${id}`), enabled: !!id })
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
              {c.needs_callback && <CallBackActions c={c} />}
              <p className={cn(c.handled_by === "missed" && vip && "font-medium text-foreground", c.handled_by === "ai" && "text-ai")}>
                {vip && c.handled_by !== "missed"
                  ? "Rang you directly. Ondra doesn't answer VIP calls."
                  : c.handled_by === "ai"
                    ? "Answered by Ondra."
                    : why(c)}
              </p>
              {c.handled_by === "missed" && progress(c) && <p className="text-muted-foreground">{progress(c)}</p>}
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

const EMPTY: Record<Show, string> = {
  all: "No other calls yet.",
  missed: "No missed calls.",
  ondra: "Ondra hasn't answered a call yet.",
  people: "No calls have been put through to your team yet.",
}

export default function CallsPage() {
  useLiveInbox()
  const [show, setShowState] = useState<Show>("all")
  const q = useQuery({ queryKey: ["calls", "list", show], queryFn: () => api<{ items: Call[] }>(`/calls?show=${show}`) })
  const [open, setOpen] = useState<string | null>(null)
  // Deep links: /calls?call=<id> opens that call (from the Inbox); /calls?show=missed picks a filter.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search)
    const id = p.get("call")
    if (id) setOpen(id)
    const s = p.get("show") as Show | null
    if (s && SHOWS.some(([k]) => k === s)) setShowState(s)
  }, [])
  const setShow = (s: Show) => {
    setShowState(s)
    const url = new URL(window.location.href)
    if (s === "all") url.searchParams.delete("show")
    else url.searchParams.set("show", s)
    window.history.replaceState(null, "", url)
  }

  const items = q.data?.items ?? []
  const live = items.filter((c) => c.live)
  const callbacks = items.filter((c) => !c.live && c.needs_callback)
  const earlier = items.filter((c) => !c.live && !c.needs_callback)
  const nothingAtAll = show === "all" && items.length === 0

  return (
    <>
      <SiteHeader title="Calls" />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 lg:px-6">
        {!nothingAtAll && (
          <Tabs value={show} onValueChange={(v) => setShow(v as Show)}>
            <TabsList aria-label="Show" className="max-w-full justify-start overflow-x-auto">
              {SHOWS.map(([k, label]) => <TabsTrigger key={k} value={k}>{label}</TabsTrigger>)}
            </TabsList>
          </Tabs>
        )}
        {q.isPending ? (
          <TableSkeleton rows={6} />
        ) : q.isError ? (
          <LoadError message={q.error.message} onRetry={() => q.refetch()} />
        ) : nothingAtAll ? (
          <div className="rounded-xl border p-6">
            <p className="font-medium">No calls yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Calls to your dealership&apos;s number show up here once your phone line is connected to Ondra. Ondra answers,
              VIPs ring you directly, and missed calls land in a call-back list.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-8">
            {live.map((c) => (
              <LiveCall key={c.id} c={c} onOpen={() => setOpen(c.id)} />
            ))}
            {(show === "all" || show === "missed") && (
              <Group id="callbacks" title="Call back" calls={callbacks} onOpen={(c) => setOpen(c.id)} empty="Nobody is waiting for a call back." />
            )}
            <Group
              id="earlier"
              title={show === "all" || show === "missed" ? "Earlier" : (SHOWS.find(([k]) => k === show)?.[1] ?? "Calls")}
              calls={earlier}
              onOpen={(c) => setOpen(c.id)}
              empty={EMPTY[show]}
            />
          </div>
        )}
      </div>
      <CallSheet id={open} onClose={() => setOpen(null)} />
    </>
  )
}

"use client"

/**
 * Inbox. One job: show what needs a person, and let them act on it fast.
 * Ondra handles most conversations end to end, so the default view is "Needs you", each row says why in plain
 * words, and everything Ondra handled sits one tab away. Blue appears only on what Ondra wrote or did.
 * Data: GET /conversations and /conversations/{id}; actions post to the API; live updates refresh it.
 */

import {
  IconArrowLeft,
  IconBan,
  IconBrandWhatsapp,
  IconCheck,
  IconChevronDown,
  IconCrownFilled,
  IconHandStop,
  IconLayoutSidebarRight,
  IconMail,
  IconMessage,
  IconPhone,
  IconSearch,
  IconSend,
} from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Message, MessageContent, MessageFooter } from "@/components/ui/message"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { api, send } from "@/lib/api"
import { useLiveInbox } from "@/lib/live"
import { cn } from "@/lib/utils"

/* ---------------------------------------------------------------- API shapes */

type Channel = "sms" | "whatsapp" | "email" | "phone"
type Bucket = "needs" | "ondra" | "team"
type Summary = {
  id: string
  channel: Channel
  status: string
  ai_mode: "auto" | "draft" | "off"
  contact: { id: string; name: string; is_vip: boolean }
  last_message: { body: string; direction: string | null; author: string | null; at: string | null; is_draft: boolean }
  bucket: Bucket
  reason: string | null
  overdue: boolean
}
type ListData = { items: Summary[]; counts: Record<Bucket, number> }
type Msg = { id: string; direction: string; author: "customer" | "ai" | "user" | "system"; author_name: string | null; body: string | null; status: string; is_draft: boolean; at: string }
type Detail = {
  id: string
  channel: Channel
  status: string
  ai_mode: "auto" | "draft" | "off"
  contact: { id: string; name: string; is_vip: boolean; language: string | null; opted_out: boolean; identities: { kind: string; value: string }[] }
  messages: Msg[]
  deal: { type: string; stage: string; vehicle_of_interest: Record<string, unknown>; budget_max: number | null; payment_method: string | null; timeline: string | null } | null
  tasks: { id: string; title: string; urgency: string; due_at: string | null; overdue: boolean; assignee: string | null }[]
  brief: string | null
}

const CHANNEL: Record<Channel, { icon: typeof IconPhone; label: string }> = {
  phone: { icon: IconPhone, label: "Phone" },
  sms: { icon: IconMessage, label: "Text" },
  email: { icon: IconMail, label: "Email" },
  whatsapp: { icon: IconBrandWhatsapp, label: "WhatsApp" },
}

type View = "needs" | "ondra" | "all"

/* ---------------------------------------------------------------- formatting */

function initials(name: string) {
  const parts = name.replace(/^\+/, "").split(/\s+/).filter(Boolean)
  return parts.length > 1 ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase() : name.replace(/\D/g, "").slice(-2) || name.slice(0, 2)
}

function when(iso: string | null) {
  if (!iso) return ""
  const d = new Date(iso)
  const today = new Date().toDateString() === d.toDateString()
  return today
    ? d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase()
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function dueText(iso: string | null) {
  if (!iso) return ""
  const d = new Date(iso)
  return d.toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit" }).replace(" AM", " am").replace(" PM", " pm")
}

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

/* ---------------------------------------------------------------- list */

function Row({ c, active, onSelect }: { c: Summary; active: boolean; onSelect: () => void }) {
  const Ch = CHANNEL[c.channel]?.icon ?? IconMessage
  const vip = c.contact.is_vip
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onSelect}
      data-vip={vip || undefined}
      className={cn(
        "relative grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 px-4 py-3 text-left outline-none hover:bg-muted/50 focus-visible:bg-muted",
        active && "bg-muted before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-foreground",
      )}
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground" aria-hidden="true">
        {initials(c.contact.name)}
      </span>
      <span className="min-w-0">
        <span className="flex items-center gap-1.5">
          {vip && <IconCrownFilled className="size-3.5 shrink-0 text-vip" aria-label="VIP" />}
          <span className="truncate font-medium">{c.contact.name}</span>
        </span>
        <span className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
          {c.bucket === "needs" ? (
            <span className={cn("truncate", (vip || c.overdue) && "text-vip")}>{c.overdue ? `Overdue: ${c.reason}` : c.reason}</span>
          ) : c.bucket === "ondra" ? (
            <>
              <OndraMark className="size-3.5 shrink-0 text-ai" />
              <span className="truncate">{c.last_message.body}</span>
            </>
          ) : (
            <>
              <Ch className="size-3.5 shrink-0" aria-hidden="true" />
              <span className="truncate">{c.last_message.body}</span>
            </>
          )}
        </span>
      </span>
      <span className="pt-0.5 text-xs whitespace-nowrap text-muted-foreground tabular-nums">{when(c.last_message.at)}</span>
    </button>
  )
}

function ListSkeleton() {
  return (
    <div className="divide-y border-t" aria-label="Loading conversations">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex gap-3 px-4 py-3">
          <Skeleton className="size-9 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3.5 w-48" />
          </div>
        </div>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------------- thread */

function Draft({ m, conversationId }: { m: Msg; conversationId: string }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(m.body ?? "")
  const refreshAll = () => {
    qc.invalidateQueries({ queryKey: ["conversation", conversationId] })
    qc.invalidateQueries({ queryKey: ["conversations"] })
  }
  const approve = useMutation({
    mutationFn: (body?: string) => send("POST", `/messages/${m.id}/approve`, body ? { body } : {}),
    onSuccess: () => { toast.success("Sent"); refreshAll() },
    onError: (e) => toast(errorText(e)),
  })
  const discard = useMutation({
    mutationFn: () => send("POST", `/messages/${m.id}/discard`),
    onSuccess: () => { toast("Draft discarded"); refreshAll() },
    onError: (e) => toast(errorText(e)),
  })
  const busy = approve.isPending || discard.isPending
  return (
    <div className="ml-auto max-w-lg rounded-xl border border-dashed border-ai/60 bg-ai-subtle/40 p-3 text-sm" data-slot="ai-draft">
      <p className="flex items-center gap-1.5 text-xs font-medium text-ai">
        <OndraMark className="size-3.5" /> Draft by Ondra, waiting for you
      </p>
      {editing ? (
        <Textarea value={text} onChange={(e) => setText(e.target.value)} aria-label="Edit draft" className="mt-2 min-h-24 bg-background" />
      ) : (
        <p className="mt-1.5 leading-relaxed whitespace-pre-wrap">{m.body}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {editing ? (
          <>
            <Button size="sm" disabled={busy || !text.trim()} onClick={() => approve.mutate(text)}>
              <IconSend /> Send edited
            </Button>
            <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setText(m.body ?? "") }}>Cancel</Button>
          </>
        ) : (
          <>
            <Button size="sm" disabled={busy} onClick={() => approve.mutate(undefined)}>
              <IconCheck /> Approve and send
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Edit</Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => discard.mutate()}>Discard</Button>
          </>
        )}
      </div>
    </div>
  )
}

function Bubbled({ m }: { m: Msg }) {
  const end = m.direction === "outbound"
  const ai = m.author === "ai"
  return (
    <Message align={end ? "end" : "start"}>
      <MessageContent className="max-w-lg">
        <Bubble variant={m.author === "user" ? "default" : "muted"} align={end ? "end" : "start"}>
          <BubbleContent className={cn("whitespace-pre-wrap", ai && "bg-ai-subtle! text-foreground")}>{m.body}</BubbleContent>
        </Bubble>
        <MessageFooter className="gap-1.5">
          {ai && (
            <span className="flex items-center gap-1 text-ai">
              <OndraMark className="size-3.5" /> {m.author_name ? `Sent by Ondra, approved by ${m.author_name.split(" ")[0]}` : "Sent by Ondra"}
            </span>
          )}
          {m.author === "user" && <span>{m.author_name}</span>}
          {m.status === "failed" && <span>Not delivered</span>}
          <span className="tabular-nums">{when(m.at)}</span>
        </MessageFooter>
      </MessageContent>
    </Message>
  )
}

function Composer({ d }: { d: Detail }) {
  const qc = useQueryClient()
  const [text, setText] = useState("")
  const first = d.contact.name.split(" ")[0]
  const reply = useMutation({
    mutationFn: () => send("POST", `/conversations/${d.id}/reply`, { body: text }),
    onSuccess: () => {
      setText("")
      qc.invalidateQueries({ queryKey: ["conversation", d.id] })
      qc.invalidateQueries({ queryKey: ["conversations"] })
    },
    onError: (e) => toast(errorText(e)),
  })
  if (d.contact.opted_out)
    return (
      <p className="flex items-center gap-2 border-t p-4 text-sm text-muted-foreground">
        <IconBan className="size-4 shrink-0" aria-hidden="true" />
        Opted out on every channel. Nobody can message {first} until they opt back in.
      </p>
    )
  return (
    <form className="flex items-end gap-2 border-t p-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) reply.mutate() }}>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && text.trim()) reply.mutate() }}
        placeholder={d.contact.is_vip ? `Reply to ${first} yourself` : `Reply to ${first}`}
        aria-label="Reply"
        className="min-h-10 resize-none"
        rows={1}
      />
      <Button size="icon" type="submit" aria-label="Send" disabled={!text.trim() || reply.isPending}>
        <IconSend />
      </Button>
    </form>
  )
}

function Thread({ id, onBack, panelOpen, togglePanel, openDetails }: {
  id: string; onBack: () => void; panelOpen: boolean; togglePanel: () => void; openDetails: () => void
}) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ["conversation", id], queryFn: () => api<Detail>(`/conversations/${id}`) })
  const end = useRef<HTMLDivElement>(null)
  // Block body on purpose: newer browsers return a Promise from scrollIntoView, and an effect must return nothing
  // or a cleanup function (returning the Promise crashed the page when switching threads).
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" })
  }, [q.data?.messages.length])
  const mode = useMutation({
    mutationFn: (to: "takeover" | "handback") => send("POST", `/conversations/${id}/${to}`),
    onSuccess: (_, to) => {
      toast(to === "takeover" ? "You're handling this. Ondra will stay quiet." : "Ondra is handling this again.")
      qc.invalidateQueries({ queryKey: ["conversation", id] })
      qc.invalidateQueries({ queryKey: ["conversations"] })
    },
    onError: (e) => toast(errorText(e)),
  })

  if (q.isPending)
    return (
      <section className="flex min-h-0 flex-1 flex-col gap-4 p-6" aria-label="Loading conversation">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-16 w-2/3" />
        <Skeleton className="ml-auto h-16 w-2/3" />
      </section>
    )
  if (q.isError)
    return (
      <section className="flex flex-1 flex-col items-start gap-3 p-6 text-sm" role="alert">
        <p>This conversation didn&apos;t load. {errorText(q.error)}</p>
        <Button variant="outline" onClick={() => q.refetch()}>Try again</Button>
      </section>
    )

  const d = q.data
  const vip = d.contact.is_vip
  const Ch = CHANNEL[d.channel]?.icon ?? IconMessage
  const ondraOn = d.ai_mode !== "off"
  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col" aria-label={`Conversation with ${d.contact.name}`} data-vip={vip || undefined}>
      <header className="flex items-center gap-3 border-b px-4 py-2.5">
        <Button variant="ghost" size="icon" className="@2xl/inbox:hidden" onClick={onBack} aria-label="Back to conversations">
          <IconArrowLeft />
        </Button>
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-1.5 font-medium">
            {vip && <IconCrownFilled className="size-4 text-vip" aria-label="VIP" />}
            <span className="truncate">{d.contact.name}</span>
          </h2>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Ch className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{vip ? "VIP. Rings you directly, and Ondra stays out." : CHANNEL[d.channel]?.label}</span>
          </p>
        </div>
        {!vip && !d.contact.opted_out && (
          <Button variant="outline" size="sm" disabled={mode.isPending} onClick={() => mode.mutate(ondraOn ? "takeover" : "handback")}>
            {ondraOn ? (
              <>
                <IconHandStop /> Take over
              </>
            ) : (
              <>
                <OndraMark className="size-4" /> Hand back to Ondra
              </>
            )}
          </Button>
        )}
        {/* Wide inbox: show or hide the details column. Narrow inbox: open details in a sheet. */}
        <Button
          variant="ghost"
          size="icon"
          className="hidden @6xl/inbox:inline-flex"
          onClick={togglePanel}
          aria-pressed={panelOpen}
          aria-label={panelOpen ? "Hide details" : "Show details"}
          title={panelOpen ? "Hide details" : "Show details"}
        >
          <IconLayoutSidebarRight />
        </Button>
        <Button variant="ghost" size="icon" className="@6xl/inbox:hidden" onClick={openDetails} aria-label="Show details" title="Show details">
          <IconLayoutSidebarRight />
        </Button>
      </header>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-5 lg:px-8">
        {d.messages.length === 0 && <p className="text-sm text-muted-foreground">No messages yet.</p>}
        {d.messages.map((m) =>
          m.is_draft && m.status === "queued" ? <Draft key={m.id} m={m} conversationId={d.id} /> : m.is_draft ? null : <Bubbled key={m.id} m={m} />,
        )}
        <div ref={end} />
      </div>

      <Composer d={d} />
    </section>
  )
}

/* ---------------------------------------------------------------- details */

function Field({ k, v }: { k: string; v?: string | null }) {
  if (!v) return null
  return (
    <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-2 text-sm">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="min-w-0 break-words">{v}</dd>
    </div>
  )
}

function phone(v?: string) {
  const m = v?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : v
}

function Details({ id, inSheet = false }: { id: string; inSheet?: boolean }) {
  const q = useQuery({ queryKey: ["conversation", id], queryFn: () => api<Detail>(`/conversations/${id}`) })
  const d = q.data
  const cls = cn("min-h-0 flex-col gap-6 overflow-y-auto", inSheet ? "flex px-4 pb-4" : "hidden w-80 shrink-0 border-l p-5 @6xl/inbox:flex")
  if (!d) return <aside className={cls} aria-label="Details"><Skeleton className="h-24 w-full" /></aside>
  const task = d.tasks[0]
  const voi = d.deal?.vehicle_of_interest ?? {}
  const ident = (k: string) => d.contact.identities.find((i) => i.kind === k)?.value
  return (
    <aside className={cls} aria-label="Details" data-vip={d.contact.is_vip || undefined}>
      {!d.contact.is_vip && d.brief && (
        <section data-slot="ai-brief">
          <h3 className="flex items-center gap-1.5 text-xs font-medium text-ai">
            <OndraMark className="size-3.5" /> Summary by Ondra
          </h3>
          <p className="mt-1.5 text-sm leading-relaxed">{d.brief}</p>
        </section>
      )}

      {task && (
        <section>
          <h3 className="text-xs font-medium text-muted-foreground">Next</h3>
          <p className="mt-1.5 text-sm font-medium">{task.title.split(": ").slice(-1)[0]}</p>
          <p className={cn("text-sm tabular-nums", task.overdue ? "text-vip" : "text-muted-foreground")}>
            {task.overdue ? `Overdue, was due ${dueText(task.due_at)}` : `Due ${dueText(task.due_at)}`}
            {task.assignee ? `, ${task.assignee.split(" ")[0]}` : ""}
          </p>
        </section>
      )}

      {d.deal && (
        <section>
          <h3 className="mb-2 text-xs font-medium text-muted-foreground">Deal</h3>
          <dl className="grid gap-1.5">
            <Field k="Vehicle" v={(voi.description as string) ?? null} />
            <Field k="Budget" v={d.deal.budget_max ? `Up to $${d.deal.budget_max.toLocaleString("en-US")}` : null} />
            <Field k="Payment" v={d.deal.payment_method} />
            <Field k="Trade-in" v={(voi.trade_in as string) ?? null} />
            <Field k="Timeline" v={d.deal.timeline} />
            <Field k="Stage" v={d.deal.stage} />
          </dl>
        </section>
      )}

      <Collapsible>
        <CollapsibleTrigger className="flex w-full items-center justify-between rounded-sm text-xs font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring [&[data-state=open]>svg]:rotate-180">
          Contact and consent
          <IconChevronDown className="size-4 transition-transform" aria-hidden="true" />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <dl className="mt-3 grid gap-1.5">
            <Field k="Phone" v={phone(ident("phone") ?? ident("whatsapp"))} />
            <Field k="Email" v={ident("email")} />
            <Field k="Language" v={d.contact.language === "es" ? "Spanish" : d.contact.language === "en" ? "English" : d.contact.language} />
            <Field k="Messages" v={d.contact.opted_out ? "Opted out on every channel" : "Allowed"} />
          </dl>
        </CollapsibleContent>
      </Collapsible>
    </aside>
  )
}

/* ---------------------------------------------------------------- page */

export default function InboxPage() {
  useLiveInbox()
  const [view, setView] = useState<View>("needs")
  const [q, setQ] = useState("")
  const [selected, setSelected] = useState<string | null>(null)
  // Deep link from Tasks: /inbox?c=<conversation id> opens that conversation.
  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get("c")
    if (c) {
      setSelected(c)
      setMobileThread(true)
    }
  }, [])
  const [mobileThread, setMobileThread] = useState(false)
  const [panelOpen, setPanelOpen] = useState(true)
  const [detailsSheet, setDetailsSheet] = useState(false)
  // The sidebar stays however the user left it. The columns below respond to the Inbox's own width
  // (container queries), so they fit with the sidebar open or closed.

  const list = useQuery({ queryKey: ["conversations"], queryFn: () => api<ListData>("/conversations?view=all") })
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api<{ replies: { draft_mode: boolean } }>("/settings") })

  const items = useMemo(() => {
    const all = list.data?.items ?? []
    const byView = all.filter((c) => (view === "all" ? true : c.bucket === view))
    const needle = q.trim().toLowerCase()
    const found = needle ? byView.filter((c) => `${c.contact.name} ${c.last_message.body}`.toLowerCase().includes(needle)) : byView
    // VIPs first among what needs you: their waiting costs the most. Then overdue.
    return view === "needs"
      ? [...found].sort((a, b) => Number(b.contact.is_vip) - Number(a.contact.is_vip) || Number(b.overdue) - Number(a.overdue))
      : found
  }, [list.data, view, q])
  // Open on the most urgent thing until the user picks one.
  const currentId = selected ?? items[0]?.id ?? list.data?.items[0]?.id ?? null
  const current = list.data?.items.find((c) => c.id === currentId)

  return (
    <>
      <SiteHeader title="Inbox" />
      {settings.data?.replies.draft_mode && (
        <p className="flex items-center gap-2 border-b bg-ai-subtle/50 px-4 py-2 text-sm lg:px-6">
          <OndraMark className="size-4 shrink-0 text-ai" />
          <span>
            <span className="font-medium">Draft mode is on.</span>{" "}
            <span className="text-muted-foreground">Ondra writes and you approve before anything is sent.</span>
          </span>
        </p>
      )}
      <div className="@container/inbox flex min-h-0 flex-1 md:h-[calc(100svh-var(--header-height)-3.25rem)] md:flex-none md:overflow-hidden">
        <div className={cn("min-h-0 w-full flex-col border-r @2xl/inbox:flex @2xl/inbox:w-72 @2xl/inbox:shrink-0 @5xl/inbox:w-80", mobileThread ? "hidden" : "flex")}>
          <div className="flex flex-col gap-3 p-3">
            <Tabs value={view} onValueChange={(v) => setView(v as View)}>
              <TabsList className="w-full">
                <TabsTrigger value="needs">
                  Needs you <span className="text-muted-foreground tabular-nums">{list.data?.counts.needs ?? ""}</span>
                </TabsTrigger>
                <TabsTrigger value="ondra">
                  Ondra handled <span className="text-muted-foreground tabular-nums">{list.data?.counts.ondra ?? ""}</span>
                </TabsTrigger>
                <TabsTrigger value="all">All</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="relative">
              <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" aria-label="Search conversations" className="pl-8" />
            </div>
          </div>
          {list.isPending ? (
            <ListSkeleton />
          ) : list.isError ? (
            <div className="space-y-3 border-t p-6 text-sm" role="alert">
              <p>Conversations didn&apos;t load. {errorText(list.error)}</p>
              <Button variant="outline" onClick={() => list.refetch()}>Try again</Button>
            </div>
          ) : (
            <div role="listbox" aria-label="Conversations" className="min-h-0 flex-1 divide-y overflow-y-auto border-t">
              {items.length === 0 ? (
                <p className="p-6 text-sm text-muted-foreground">
                  {view === "needs" && !q ? "Nothing needs you right now. Ondra is handling everything else." : "No conversations match."}
                </p>
              ) : (
                items.map((c) => (
                  <Row key={c.id} c={c} active={c.id === currentId} onSelect={() => { setSelected(c.id); setMobileThread(true) }} />
                ))
              )}
            </div>
          )}
        </div>
        <div className={cn("min-h-0 min-w-0 flex-1 @2xl/inbox:flex", mobileThread ? "flex" : "hidden")}>
          {currentId ? (
            <>
              <Thread
                key={currentId}
                id={currentId}
                onBack={() => setMobileThread(false)}
                panelOpen={panelOpen}
                togglePanel={() => setPanelOpen((o) => !o)}
                openDetails={() => setDetailsSheet(true)}
              />
              {panelOpen && <Details id={currentId} />}
            </>
          ) : (
            !list.isPending && (
              <p className="m-auto max-w-sm p-6 text-center text-sm text-muted-foreground">
                No conversations yet. When customers text, email or WhatsApp your dealership, they show up here.
              </p>
            )
          )}
        </div>
      </div>
      {currentId && (
        <Sheet open={detailsSheet} onOpenChange={setDetailsSheet}>
          <SheetContent className="w-full sm:max-w-sm" data-vip={current?.contact.is_vip || undefined}>
            <SheetHeader>
              <SheetTitle>{current?.contact.name ?? "Details"}</SheetTitle>
              <SheetDescription>Details</SheetDescription>
            </SheetHeader>
            <Details id={currentId} inSheet />
          </SheetContent>
        </Sheet>
      )}
    </>
  )
}

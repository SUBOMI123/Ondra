"use client"

/**
 * Inbox. One job: show what needs a person, and let them act on it fast.
 * Ondra handles most conversations end to end, so the default view is "Needs you", each row says why in plain
 * words, and everything Ondra handled sits one tab away. Blue appears only on what Ondra wrote or did.
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
  IconPhoneIncoming,
  IconPlayerPlayFilled,
  IconSearch,
  IconSend,
} from "@tabler/icons-react"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Message, MessageContent, MessageFooter } from "@/components/ui/message"
import { useSidebar } from "@/components/ui/sidebar"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { CONVERSATIONS, type Channel, type Conversation, type ThreadEvent } from "@/lib/examples"
import { cn } from "@/lib/utils"

const CHANNEL: Record<Channel, { icon: typeof IconPhone; label: string }> = {
  phone: { icon: IconPhone, label: "Phone" },
  sms: { icon: IconMessage, label: "Text" },
  email: { icon: IconMail, label: "Email" },
  whatsapp: { icon: IconBrandWhatsapp, label: "WhatsApp" },
}

type View = "needs" | "ondra" | "all"

/* ---------------------------------------------------------------- list */

function Row({ c, active, onSelect }: { c: Conversation; active: boolean; onSelect: () => void }) {
  const Ch = CHANNEL[c.channel].icon
  const optedOut = c.status.kind === "optout"
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onSelect}
      data-vip={c.vip || undefined}
      className={cn(
        "relative grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 px-4 py-3 text-left outline-none hover:bg-muted/50 focus-visible:bg-muted",
        active && "bg-muted before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-foreground",
      )}
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground" aria-hidden="true">
        {c.initials}
      </span>
      <span className="min-w-0">
        <span className="flex items-center gap-1.5">
          {c.vip && <IconCrownFilled className="size-3.5 shrink-0 text-vip" aria-label="VIP" />}
          <span className={cn("truncate", c.unread ? "font-semibold" : "font-medium")}>{c.client}</span>
        </span>
        <span className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
          {c.bucket === "needs" ? (
            <span className={cn("truncate", c.vip && "text-vip")}>{c.reason}</span>
          ) : c.bucket === "ondra" ? (
            <>
              <OndraMark className="size-3.5 shrink-0 text-ai" />
              <span className="truncate">{c.snippet}</span>
            </>
          ) : (
            <>
              {optedOut ? <IconBan className="size-3.5 shrink-0" aria-hidden="true" /> : <Ch className="size-3.5 shrink-0" aria-hidden="true" />}
              <span className="truncate">{optedOut ? "Opted out" : c.snippet}</span>
            </>
          )}
        </span>
      </span>
      <span className="pt-0.5 text-xs whitespace-nowrap text-muted-foreground tabular-nums">{c.time}</span>
    </button>
  )
}

/* ---------------------------------------------------------------- thread */

function Event({ e, onApprove }: { e: ThreadEvent; onApprove: () => void }) {
  if (e.kind === "event")
    return (
      <p className={cn("flex items-center justify-center gap-1.5 text-center text-xs", e.ai ? "text-ai" : "text-muted-foreground")}>
        {e.ai && <OndraMark className="size-3.5" />}
        {e.text}
      </p>
    )

  if (e.kind === "call") {
    const missed = e.duration === "0:00"
    return (
      <div className="flex max-w-lg items-start gap-3 rounded-xl border bg-card p-3 text-sm">
        <IconPhoneIncoming className={cn("mt-0.5 size-4 shrink-0", e.answeredBy === "Ondra" ? "text-ai" : "text-muted-foreground")} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-medium">
            {missed ? "Missed call" : e.answeredBy === "Ondra" ? "Call answered by Ondra" : `Call, ${e.duration}`}
            <span className="ml-2 text-xs font-normal text-muted-foreground tabular-nums">{e.time}</span>
          </p>
          <p className="mt-0.5 text-muted-foreground">{e.summary}</p>
        </div>
        {!missed && (
          <Button variant="ghost" size="icon" className="size-8 shrink-0" aria-label={`Play recording, ${e.duration}`} title={`Play recording, ${e.duration}`}>
            <IconPlayerPlayFilled />
          </Button>
        )}
      </div>
    )
  }

  if (e.kind === "draft")
    return (
      <div className="ml-auto max-w-lg rounded-xl border border-dashed border-ai/60 bg-ai-subtle/40 p-3 text-sm" data-slot="ai-draft">
        <p className="flex items-center gap-1.5 text-xs font-medium text-ai">
          <OndraMark className="size-3.5" /> Draft by Ondra, waiting for you
        </p>
        <p className="mt-1.5 leading-relaxed">{e.body}</p>
        <div className="mt-3 flex items-center gap-2">
          <Button size="sm" onClick={onApprove}>
            <IconCheck /> Approve and send
          </Button>
          <Button size="sm" variant="ghost">
            Edit
          </Button>
        </div>
      </div>
    )

  const end = e.author !== "customer"
  return (
    <Message align={end ? "end" : "start"}>
      <MessageContent className="max-w-lg">
        <Bubble variant={e.author === "staff" ? "default" : "muted"} align={end ? "end" : "start"}>
          <BubbleContent className={cn(e.author === "ondra" && "bg-ai-subtle! text-foreground")}>{e.body}</BubbleContent>
        </Bubble>
        <MessageFooter className="gap-1.5">
          {e.author === "ondra" && (
            <span className="flex items-center gap-1 text-ai">
              <OndraMark className="size-3.5" /> Sent by Ondra
            </span>
          )}
          {e.author === "staff" && <span>{e.name}</span>}
          <span className="tabular-nums">{e.time}</span>
        </MessageFooter>
      </MessageContent>
    </Message>
  )
}

function Composer({ c }: { c: Conversation }) {
  const first = c.client.split(" ")[0]
  if (c.status.kind === "optout")
    return (
      <p className="flex items-center gap-2 border-t p-4 text-sm text-muted-foreground">
        <IconBan className="size-4 shrink-0" aria-hidden="true" />
        Opted out on every channel. Nobody can message {first} until they opt back in.
      </p>
    )
  return (
    <div className="flex items-end gap-2 border-t p-3">
      <Textarea placeholder={c.vip ? `Reply to ${first} yourself` : `Reply to ${first}`} aria-label="Reply" className="min-h-10 resize-none" rows={1} />
      <Button size="icon" aria-label="Send">
        <IconSend />
      </Button>
    </div>
  )
}

function Thread({ c, onBack, panelOpen, togglePanel }: { c: Conversation; onBack: () => void; panelOpen: boolean; togglePanel: () => void }) {
  const [ondraOn, setOndraOn] = useState(c.handledBy === "ondra")
  const [approved, setApproved] = useState(false)
  const Ch = CHANNEL[c.channel].icon
  const optedOut = c.status.kind === "optout"
  const events = approved
    ? c.events.map((e): ThreadEvent => (e.kind === "draft" ? { kind: "message", author: "ondra", body: e.body, time: "Just now" } : e))
    : c.events

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col" aria-label={`Conversation with ${c.client}`} data-vip={c.vip || undefined}>
      <header className="flex items-center gap-3 border-b px-4 py-2.5">
        <Button variant="ghost" size="icon" className="md:hidden" onClick={onBack} aria-label="Back to conversations">
          <IconArrowLeft />
        </Button>
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-1.5 font-medium">
            {c.vip && <IconCrownFilled className="size-4 text-vip" aria-label="VIP" />}
            <span className="truncate">{c.client}</span>
          </h2>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Ch className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{c.vip ? "VIP. Rings you directly, and Ondra stays out." : CHANNEL[c.channel].label}</span>
          </p>
        </div>
        {!c.vip && !optedOut && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setOndraOn((on) => !on)
              toast(ondraOn ? "You're handling this. Ondra will stay quiet." : "Ondra is handling this again.")
            }}
          >
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
        <Button
          variant="ghost"
          size="icon"
          className="hidden xl:inline-flex"
          onClick={togglePanel}
          aria-pressed={panelOpen}
          aria-label={panelOpen ? "Hide details" : "Show details"}
          title={panelOpen ? "Hide details" : "Show details"}
        >
          <IconLayoutSidebarRight />
        </Button>
      </header>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-5 lg:px-8">
        {events.map((e, i) => (
          <Event key={i} e={e} onApprove={() => { setApproved(true); toast.success(`Sent to ${c.client}`) }} />
        ))}
      </div>

      <Composer c={c} />
    </section>
  )
}

/* ---------------------------------------------------------------- details */

function Field({ k, v }: { k: string; v?: string }) {
  if (!v) return null
  return (
    <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-2 text-sm">
      <dt className="text-muted-foreground">{k}</dt>
      <dd>{v}</dd>
    </div>
  )
}

function Details({ c }: { c: Conversation }) {
  const task = c.tasks?.[0]
  const next = c.upcoming?.[0] ?? (task && { title: task.title, when: task.due })
  const overdue = !c.upcoming && task?.overdue
  return (
    <aside className="hidden min-h-0 w-80 shrink-0 flex-col gap-6 overflow-y-auto border-l p-5 xl:flex" aria-label="Details" data-vip={c.vip || undefined}>
      {!c.vip && c.brief && (
        <section data-slot="ai-brief">
          <h3 className="flex items-center gap-1.5 text-xs font-medium text-ai">
            <OndraMark className="size-3.5" /> Summary by Ondra
          </h3>
          <p className="mt-1.5 text-sm leading-relaxed">{c.brief}</p>
        </section>
      )}

      {next && (
        <section>
          <h3 className="text-xs font-medium text-muted-foreground">Next</h3>
          <p className="mt-1.5 text-sm font-medium">{next.title}</p>
          <p className={cn("text-sm tabular-nums", overdue ? "text-vip" : "text-muted-foreground")}>
            {overdue ? `Overdue, was due ${next.when}` : next.when}
          </p>
        </section>
      )}

      {c.deal && (
        <section>
          <h3 className="mb-2 text-xs font-medium text-muted-foreground">Deal</h3>
          <dl className="grid gap-1.5">
            <Field k="Vehicle" v={c.deal.vehicle} />
            <Field k="Budget" v={c.deal.budget} />
            <Field k="Financing" v={c.deal.financing} />
            <Field k="Trade-in" v={c.deal.tradeIn} />
            <Field k="Stage" v={c.deal.stage} />
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
            <Field k="Phone" v={c.contact.phone} />
            <Field k="Email" v={c.contact.email} />
            <Field k="Language" v={c.contact.language} />
            {c.consent.map((k) => (
              <Field key={k.channel} k={k.channel} v={k.status} />
            ))}
          </dl>
        </CollapsibleContent>
      </Collapsible>
    </aside>
  )
}

/* ---------------------------------------------------------------- page */

export default function InboxPage() {
  const { setOpen } = useSidebar()
  const [view, setView] = useState<View>("needs")
  const [q, setQ] = useState("")
  // Open on the most urgent thing: a VIP waiting, if there is one.
  const [selected, setSelected] = useState<string>(
    (CONVERSATIONS.find((c) => c.bucket === "needs" && c.vip) ?? CONVERSATIONS.find((c) => c.bucket === "needs") ?? CONVERSATIONS[0]).id,
  )
  const [mobileThread, setMobileThread] = useState(false)
  const [panelOpen, setPanelOpen] = useState(true)

  // The thread is the work; give it the room the app sidebar would take. Users can reopen it.
  useEffect(() => setOpen(false), [setOpen])

  const counts = {
    needs: CONVERSATIONS.filter((c) => c.bucket === "needs").length,
    ondra: CONVERSATIONS.filter((c) => c.bucket === "ondra").length,
  }
  const items = useMemo(() => {
    const byView = CONVERSATIONS.filter((c) => (view === "all" ? true : c.bucket === view))
    const needle = q.trim().toLowerCase()
    const found = needle ? byView.filter((c) => `${c.client} ${c.snippet}`.toLowerCase().includes(needle)) : byView
    // VIPs first among what needs you: their waiting costs the most.
    return view === "needs" ? [...found].sort((a, b) => Number(!!b.vip) - Number(!!a.vip)) : found
  }, [view, q])
  const current = items.find((c) => c.id === selected) ?? CONVERSATIONS.find((c) => c.id === selected) ?? CONVERSATIONS[0]

  return (
    <>
      <SiteHeader title="Inbox" note="Example data until channels go live in Step 2" />
      <p className="flex items-center gap-2 border-b bg-ai-subtle/50 px-4 py-2 text-sm lg:px-6">
        <OndraMark className="size-4 shrink-0 text-ai" />
        <span>
          <span className="font-medium">Draft mode is on.</span>{" "}
          <span className="text-muted-foreground">For your first week, Ondra writes and you approve.</span>
        </span>
      </p>
      <div className="flex min-h-0 flex-1 md:h-[calc(100svh-var(--header-height)-3.25rem)] md:flex-none md:overflow-hidden">
        <div className={cn("min-h-0 w-full flex-col border-r md:flex md:w-80 md:shrink-0", mobileThread ? "hidden" : "flex")}>
          <div className="flex flex-col gap-3 p-3">
            <Tabs value={view} onValueChange={(v) => setView(v as View)}>
              <TabsList className="w-full">
                <TabsTrigger value="needs">
                  Needs you <span className="text-muted-foreground tabular-nums">{counts.needs}</span>
                </TabsTrigger>
                <TabsTrigger value="ondra">
                  Ondra handled <span className="text-muted-foreground tabular-nums">{counts.ondra}</span>
                </TabsTrigger>
                <TabsTrigger value="all">All</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="relative">
              <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" aria-label="Search conversations" className="pl-8" />
            </div>
          </div>
          <div role="listbox" aria-label="Conversations" className="min-h-0 flex-1 divide-y overflow-y-auto border-t">
            {items.length === 0 ? (
              <p className="p-6 text-sm text-muted-foreground">
                {view === "needs" && !q ? "Nothing needs you right now. Ondra is handling everything else." : "No conversations match."}
              </p>
            ) : (
              items.map((c) => (
                <Row key={c.id} c={c} active={c.id === current.id} onSelect={() => { setSelected(c.id); setMobileThread(true) }} />
              ))
            )}
          </div>
        </div>
        <div className={cn("min-h-0 min-w-0 flex-1 md:flex", mobileThread ? "flex" : "hidden")}>
          <Thread key={current.id} c={current} onBack={() => setMobileThread(false)} panelOpen={panelOpen} togglePanel={() => setPanelOpen((o) => !o)} />
          {panelOpen && <Details c={current} />}
        </div>
      </div>
    </>
  )
}

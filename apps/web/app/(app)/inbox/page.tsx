"use client"

import {
  IconArrowLeft,
  IconBan,
  IconBrandWhatsapp,
  IconCheck,
  IconCrownFilled,
  IconHandStop,
  IconMail,
  IconMessage,
  IconPencil,
  IconPhone,
  IconPhoneIncoming,
  IconPlayerPlayFilled,
  IconSearch,
  IconSend,
  IconTrash,
} from "@tabler/icons-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { Badge } from "@/components/ui/badge"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Message, MessageContent, MessageFooter } from "@/components/ui/message"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { CONVERSATIONS, type Channel, type Conversation, type ThreadEvent } from "@/lib/examples"
import { cn } from "@/lib/utils"

const CHANNEL: Record<Channel, { icon: typeof IconPhone; label: string }> = {
  phone: { icon: IconPhone, label: "Phone" },
  sms: { icon: IconMessage, label: "Text" },
  email: { icon: IconMail, label: "Email" },
  whatsapp: { icon: IconBrandWhatsapp, label: "WhatsApp" },
}

type Filter = "all" | "mine" | "vip" | "drafts"

function StatusBadge({ status }: { status: Conversation["status"] }) {
  const cls = {
    ai: "border-transparent bg-ai-subtle text-ai",
    draft: "border-dashed border-ai text-ai",
    vip: "border-transparent bg-vip-subtle text-vip",
    team: "text-muted-foreground",
    optout: "text-muted-foreground",
  }[status.kind]
  return (
    <Badge variant="outline" className={cn("gap-1 px-1.5", cls)}>
      {(status.kind === "ai" || status.kind === "draft") && <OndraMark className="size-3.5" />}
      {status.kind === "vip" && <IconCrownFilled />}
      {status.kind === "optout" && <IconBan />}
      {status.text}
    </Badge>
  )
}

function Avatar({ c, size = "size-9" }: { c: Pick<Conversation, "initials" | "vip">; size?: string }) {
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full text-xs font-semibold",
        size,
        c.vip ? "bg-vip-subtle text-vip" : "bg-muted text-muted-foreground",
      )}
      aria-hidden="true"
    >
      {c.initials}
    </span>
  )
}

/* ---------------------------------------------------------------- list */

function ConversationList({
  items,
  selected,
  onSelect,
  filter,
  setFilter,
  q,
  setQ,
}: {
  items: Conversation[]
  selected: string
  onSelect: (id: string) => void
  filter: Filter
  setFilter: (f: Filter) => void
  q: string
  setQ: (q: string) => void
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col border-r">
      <div className="flex flex-col gap-3 border-b p-3">
        <div className="relative">
          <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search conversations" aria-label="Search conversations" className="pl-8" />
        </div>
        <ToggleGroup type="single" variant="outline" size="sm" value={filter} onValueChange={(v) => v && setFilter(v as Filter)} className="w-full" aria-label="Filter conversations">
          <ToggleGroupItem value="all" className="flex-1">All</ToggleGroupItem>
          <ToggleGroupItem value="mine" className="flex-1">Mine</ToggleGroupItem>
          <ToggleGroupItem value="vip" className="flex-1">VIP</ToggleGroupItem>
          <ToggleGroupItem value="drafts" className="flex-1">Drafts</ToggleGroupItem>
        </ToggleGroup>
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto" role="listbox" aria-label="Conversations">
        {items.length === 0 && <li className="p-6 text-sm text-muted-foreground">Nothing here. Try another filter.</li>}
        {items.map((c) => {
          const Ch = CHANNEL[c.channel].icon
          const active = c.id === selected
          return (
            <li key={c.id} role="option" aria-selected={active}>
              <button
                type="button"
                onClick={() => onSelect(c.id)}
                className={cn(
                  "relative grid w-full grid-cols-[auto_minmax(0,1fr)_auto] gap-x-3 gap-y-1.5 border-b px-3 py-3 text-left outline-none hover:bg-muted/50 focus-visible:bg-muted",
                  active && "bg-muted before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-foreground",
                )}
              >
                <Avatar c={c} />
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 font-medium">
                    {c.vip && <IconCrownFilled className="size-3.5 shrink-0 text-vip" aria-label="VIP" />}
                    <span className="truncate">{c.client}</span>
                    {c.unread && <span className="size-1.5 shrink-0 rounded-full bg-foreground" aria-label="Unread" />}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                    <Ch className="size-3.5 shrink-0" aria-hidden="true" />
                    <span className="truncate">{c.snippet}</span>
                  </div>
                </div>
                <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">{c.time}</span>
                <div className="col-start-2 col-end-4">
                  <StatusBadge status={c.status} />
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/* ---------------------------------------------------------------- thread */

function Event({ e, vip, onApprove }: { e: ThreadEvent; vip?: boolean; onApprove: () => void }) {
  if (e.kind === "event")
    return (
      <div className={cn("flex items-center gap-3 py-1 text-xs", e.ai ? "text-ai" : "text-muted-foreground")}>
        <span className="h-px flex-1 bg-border" />
        <span className="flex items-center gap-1.5 text-center">
          {e.ai && <OndraMark className="size-3.5" />}
          {e.text}
          <span className="text-muted-foreground tabular-nums">{e.time}</span>
        </span>
        <span className="h-px flex-1 bg-border" />
      </div>
    )

  if (e.kind === "call")
    return (
      <div className="flex max-w-xl items-start gap-3 rounded-xl border bg-card p-3 text-sm">
        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-full", e.answeredBy === "Ondra" ? "bg-ai-subtle text-ai" : "bg-muted text-muted-foreground")}>
          <IconPhoneIncoming className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-medium">{e.duration === "0:00" ? "Missed call" : `Call, ${e.duration}`}</span>
            <span className="text-xs text-muted-foreground tabular-nums">{e.time}</span>
          </div>
          <p className="mt-0.5 text-muted-foreground">
            {e.answeredBy === "Ondra" ? "Answered by Ondra. " : e.answeredBy === "No one" ? "" : `Answered by ${e.answeredBy}. `}
            {e.summary}
          </p>
          {e.duration !== "0:00" && !vip && (
            <div className="mt-2 flex gap-2">
              <Button variant="outline" size="sm" className="h-7">
                <IconPlayerPlayFilled /> Recording
              </Button>
              <Button variant="ghost" size="sm" className="h-7">Transcript</Button>
            </div>
          )}
        </div>
      </div>
    )

  if (e.kind === "draft")
    return (
      <Message align="end">
        <MessageContent className="max-w-xl">
          <div className="rounded-xl border border-dashed border-ai bg-card p-3 text-sm">
            <p className="flex items-center gap-1.5 text-xs font-medium text-ai">
              <OndraMark className="size-3.5" /> Draft from Ondra, waiting for you
            </p>
            <p className="mt-2 leading-relaxed">{e.body}</p>
            <p className="mt-2 text-xs text-muted-foreground">{e.reason}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" onClick={onApprove}>
                <IconCheck /> Approve and send
              </Button>
              <Button size="sm" variant="outline">
                <IconPencil /> Edit
              </Button>
              <Button size="sm" variant="ghost">
                <IconTrash /> Discard
              </Button>
            </div>
          </div>
        </MessageContent>
      </Message>
    )

  const end = e.author !== "customer"
  return (
    <Message align={end ? "end" : "start"}>
      <MessageContent className="max-w-xl">
        <Bubble variant={e.author === "staff" ? "default" : "muted"} align={end ? "end" : "start"}>
          <BubbleContent className={cn(e.author === "ondra" && "border-ai/20 bg-ai-subtle! text-foreground")}>{e.body}</BubbleContent>
        </Bubble>
        <MessageFooter className="gap-1.5">
          {e.author === "ondra" && (
            <span className="flex items-center gap-1 text-ai">
              <OndraMark className="size-3.5" /> Sent by Ondra
            </span>
          )}
          {e.author === "staff" && <span>{e.name}</span>}
          {e.author === "customer" && e.channel && <span>{CHANNEL[e.channel].label}</span>}
          <span className="tabular-nums">{e.time}</span>
        </MessageFooter>
      </MessageContent>
    </Message>
  )
}

function Thread({ c, onBack }: { c: Conversation; onBack: () => void }) {
  const [handledBy, setHandledBy] = useState(c.handledBy)
  const [approved, setApproved] = useState(false)
  const Ch = CHANNEL[c.channel].icon
  const optedOut = c.status.kind === "optout"
  const events = approved
    ? c.events.map((e): ThreadEvent => (e.kind === "draft" ? { kind: "message", author: "ondra", body: e.body, time: "Just now" } : e))
    : c.events

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col" aria-label={`Conversation with ${c.client}`}>
      <div className="flex items-center gap-3 border-b px-4 py-3">
        <Button variant="ghost" size="icon" className="md:hidden" onClick={onBack} aria-label="Back to conversations">
          <IconArrowLeft />
        </Button>
        <Avatar c={c} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 font-medium">
            {c.vip && <IconCrownFilled className="size-4 text-vip" aria-label="VIP" />}
            <span className="truncate">{c.client}</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Ch className="size-3.5" aria-hidden="true" />
            <span className="truncate">
              {CHANNEL[c.channel].label}
              {c.assignee ? `, assigned to ${c.assignee}` : ""}
            </span>
          </div>
        </div>
        {!c.vip && !optedOut && (
          handledBy === "ondra" ? (
            <Button variant="outline" size="sm" onClick={() => { setHandledBy("you"); toast("You're handling this conversation. Ondra will stay quiet.") }}>
              <IconHandStop /> Take over
            </Button>
          ) : (
            <Button variant="outline" size="sm" className="border-ai/40 text-ai" onClick={() => { setHandledBy("ondra"); toast("Ondra is handling this conversation again.") }}>
              <OndraMark className="size-4" /> Hand back to Ondra
            </Button>
          )
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-muted/30 px-4 py-5">
        {events.map((e, i) => (
          <Event key={i} e={e} vip={c.vip} onApprove={() => { setApproved(true); toast.success(`Sent to ${c.client}`) }} />
        ))}
      </div>

      <div className="border-t p-3">
        {optedOut ? (
          <p className="flex items-center gap-2 rounded-lg border p-3 text-sm text-muted-foreground">
            <IconBan className="size-4 shrink-0" aria-hidden="true" />
            {c.client.split(" ")[0]} opted out. Nobody can message them until they text START or opt in again.
          </p>
        ) : (
          <>
            {c.vip && (
              <p className="mb-2 flex items-center gap-1.5 text-xs text-vip">
                <IconCrownFilled className="size-3.5" aria-hidden="true" /> VIP: Ondra won&apos;t reply or draft here. Your message goes from your dealership&apos;s number.
              </p>
            )}
            <div className="flex items-end gap-2">
              <Textarea placeholder={`Reply to ${c.client.split(" ")[0]}`} aria-label="Reply" className="min-h-10 resize-none" rows={1} />
              {!c.vip && (
                <Button variant="outline" size="icon" className="border-ai/40 text-ai" aria-label="Ask Ondra to draft a reply" title="Ask Ondra to draft a reply">
                  <OndraMark className="size-4" />
                </Button>
              )}
              <Button size="icon" aria-label="Send">
                <IconSend />
              </Button>
            </div>
          </>
        )}
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- client panel */

function Row({ k, v }: { k: string; v?: string }) {
  if (!v) return null
  return (
    <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-2 text-sm">
      <dt className="text-muted-foreground">{k}</dt>
      <dd>{v}</dd>
    </div>
  )
}

function ClientPanel({ c }: { c: Conversation }) {
  return (
    <aside className="hidden min-h-0 flex-col gap-5 overflow-y-auto border-l p-4 xl:flex" aria-label="Client details">
      {c.vip ? (
        <div className="rounded-lg bg-vip-subtle p-3 text-sm text-vip">
          <p className="flex items-center gap-1.5 font-medium">
            <IconCrownFilled className="size-4" aria-hidden="true" /> VIP: Ondra stays out of this one
          </p>
          <p className="mt-1 text-foreground/80">Calls ring you directly and messages wait for your reply.</p>
        </div>
      ) : (
        c.brief && (
          <div className="rounded-lg bg-ai-subtle p-3 text-sm">
            <p className="flex items-center gap-1.5 font-medium text-ai">
              <OndraMark className="size-4" /> Brief from Ondra
            </p>
            <p className="mt-1">{c.brief}</p>
          </div>
        )
      )}

      <section>
        <h3 className="mb-2 text-sm font-medium">Contact</h3>
        <dl className="grid gap-1.5">
          <Row k="Phone" v={c.contact.phone} />
          <Row k="Email" v={c.contact.email} />
          <Row k="WhatsApp" v={c.contact.whatsapp ? c.contact.phone : undefined} />
          <Row k="Language" v={c.contact.language} />
        </dl>
      </section>

      {c.deal && (
        <section>
          <h3 className="mb-2 flex items-center justify-between text-sm font-medium">
            Deal <Badge variant="outline" className="font-normal text-muted-foreground">{c.deal.stage}</Badge>
          </h3>
          <dl className="grid gap-1.5">
            <Row k="Vehicle" v={c.deal.vehicle} />
            <Row k="Stock" v={c.deal.stock} />
            <Row k="Budget" v={c.deal.budget} />
            <Row k="Financing" v={c.deal.financing} />
            <Row k="Trade-in" v={c.deal.tradeIn} />
            <Row k="Timeline" v={c.deal.timeline} />
          </dl>
          {!c.vip && (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-ai">
              <OndraMark className="size-3.5" /> Filled in by Ondra from the conversation
            </p>
          )}
        </section>
      )}

      {c.upcoming && (
        <section>
          <h3 className="mb-2 text-sm font-medium">Coming up</h3>
          {c.upcoming.map((u) => (
            <div key={u.title} className="flex justify-between gap-2 rounded-lg border p-2.5 text-sm">
              <span>{u.title}</span>
              <span className="text-muted-foreground tabular-nums">{u.when}</span>
            </div>
          ))}
        </section>
      )}

      {c.tasks && (
        <section>
          <h3 className="mb-2 text-sm font-medium">Tasks</h3>
          {c.tasks.map((t) => (
            <div key={t.title} className="rounded-lg border p-2.5 text-sm">
              {t.title}
              <p className={cn("mt-0.5 text-xs tabular-nums", t.overdue ? "text-vip" : "text-muted-foreground")}>
                {t.overdue ? "Overdue, was due " : "Due "}
                {t.due}
              </p>
            </div>
          ))}
        </section>
      )}

      <Separator />
      <section>
        <h3 className="mb-2 text-sm font-medium">Consent</h3>
        <dl className="grid gap-1.5">
          {c.consent.map((k) => (
            <Row key={k.channel} k={k.channel} v={k.status} />
          ))}
        </dl>
      </section>
    </aside>
  )
}

/* ---------------------------------------------------------------- page */

export default function InboxPage() {
  const [filter, setFilter] = useState<Filter>("all")
  const [q, setQ] = useState("")
  const [selected, setSelected] = useState(CONVERSATIONS[0].id)
  const [mobileThread, setMobileThread] = useState(false)

  const items = useMemo(
    () =>
      CONVERSATIONS.filter((c) =>
        filter === "vip" ? c.vip : filter === "drafts" ? c.status.kind === "draft" : filter === "mine" ? c.assignee === "Daniel Okafor" : true,
      ).filter((c) => !q || c.client.toLowerCase().includes(q.toLowerCase()) || c.snippet.toLowerCase().includes(q.toLowerCase())),
    [filter, q],
  )
  const current = CONVERSATIONS.find((c) => c.id === selected) ?? CONVERSATIONS[0]

  return (
    <>
      <SiteHeader title="Inbox" note="Example data until channels go live in Step 2" />
      <div className="grid min-h-0 flex-1 md:h-[calc(100svh-var(--header-height)-1rem)] md:flex-none md:grid-rows-[minmax(0,1fr)] md:overflow-hidden md:grid-cols-[20rem_minmax(0,1fr)] xl:grid-cols-[20rem_minmax(0,1fr)_20rem]">
        <div className={cn("min-h-0", mobileThread ? "hidden md:flex md:flex-col" : "flex flex-col")}>
          <ConversationList
            items={items}
            selected={selected}
            onSelect={(id) => { setSelected(id); setMobileThread(true) }}
            filter={filter}
            setFilter={setFilter}
            q={q}
            setQ={setQ}
          />
        </div>
        <div className={cn("min-h-0", mobileThread ? "flex flex-col" : "hidden md:flex md:flex-col")}>
          <Thread key={current.id} c={current} onBack={() => setMobileThread(false)} />
        </div>
        <ClientPanel c={current} />
      </div>
    </>
  )
}

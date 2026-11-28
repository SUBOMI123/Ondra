"use client"

/**
 * One deal, opened from the board. One job: everything a salesperson needs before they pick up the phone, and the
 * two moves they make most (move the stage, give it to someone) without leaving the board.
 * Order follows the call: who and how to reach them, what they want and can spend, what's next, what was said,
 * how the deal has moved. A VIP's deal shows nothing Ondra wrote (there's nothing to show, by the product rule).
 */

import { IconCalendarEvent, IconExternalLink, IconMessage, IconPhone, IconBell } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useState } from "react"
import { toast } from "sonner"

import { LoadError } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { VipTag } from "@/components/vip"
import { api, send } from "@/lib/api"
import { cn } from "@/lib/utils"
import { clock, daysAgo, fmt } from "@/lib/time"

export type Stage = "new" | "qualified" | "appointment" | "negotiating" | "won" | "lost"
export const STAGES: { stage: Stage; label: string }[] = [
  { stage: "new", label: "New" }, { stage: "qualified", label: "Qualified" }, { stage: "appointment", label: "Appointment" },
  { stage: "negotiating", label: "Negotiating" }, { stage: "won", label: "Won" }, { stage: "lost", label: "Lost" },
]
export const LOST_REASONS = ["Bought elsewhere", "Price", "Stopped replying", "Not ready to buy"]

type Detail = {
  id: string; stage: Stage; stage_label: string; lost_reason: string | null
  client: { id: string; name: string; vip: boolean; phone: string | null; email: string | null; preferred_channel: string | null; language: string | null }
  owner: { id: string; name: string | null } | null; owner_given: boolean
  wants: string | null; car: { id: string; name: string; stock_number: string; price: number | null; status: string } | null
  trade_in: string | null; budget_min: number | null; budget_max: number | null; payment_method: string | null
  timeline: string | null; destination: string | null; source_channel: string | null; by_ondra: boolean; created_at: string
  last_contact_at: string | null
  next_appointment: { starts_at: string; what: string } | null
  next_task: { title: string; due_at: string | null; overdue: boolean } | null
  conversation_id: string | null
  messages: { from: "customer" | "ai" | "user" | "system"; who: string | null; body: string | null; at: string; channel: string }[]
  history: { from: Stage; to: Stage; at: string; by: string | null }[]
  can_move: boolean; people: { id: string; name: string }[]
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const CHANNEL: Record<string, string> = { sms: "text", whatsapp: "WhatsApp", email: "email", phone: "phone", web: "your website", owner: "the WhatsApp assistant" }

export function stamp(iso: string) {
  const time = clock(iso)
  const days = -daysAgo(iso)
  if (days === 0) return `today, ${time}`
  if (days === 1) return `tomorrow, ${time}`
  if (days === -1) return `yesterday, ${time}`
  if (days > 1 && days < 7) return `${fmt(iso, { weekday: "long" })}, ${time}`
  return `${fmt(iso, { month: "short", day: "numeric" })}, ${time}`
}

function formatPhone(e164?: string | null) {
  const m = e164?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : (e164 ?? "")
}

function money(d: Detail) {
  if (d.budget_min && d.budget_max) return `${usd.format(d.budget_min)} to ${usd.format(d.budget_max)}`
  if (d.budget_max) return `Up to ${usd.format(d.budget_max)}`
  if (d.budget_min) return `From ${usd.format(d.budget_min)}`
  return null
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-3 py-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words first-letter:uppercase">{children}</dd>
    </div>
  )
}

function Section({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  )
}

const PAYING = { cash: "Cash", finance: "Finance", lease: "Lease", unknown: "Not sure yet" } as const

/** Correct what Ondra picked up from the conversation, or fill in what it couldn't. */
function EditWants({ d, onDone }: { d: Detail; onDone: () => void }) {
  const qc = useQueryClient()
  const [start] = useState({
    wants: d.wants ?? "", budget_max: d.budget_max ? String(d.budget_max) : "", payment_method: d.payment_method ?? "unknown",
    trade_in: d.trade_in ?? "", timeline: d.timeline ?? "",
  })
  const [f, setF] = useState(start)
  const changed = (Object.keys(f) as (keyof typeof f)[]).filter((k) => f[k] !== start[k])
  const save = useMutation({
    // Only what changed, so the audit log says what someone actually corrected.
    mutationFn: () => send("PATCH", `/deals/${d.id}`, Object.fromEntries(changed.map((k) =>
      [k, k === "budget_max" ? (f.budget_max ? Number(f.budget_max.replace(/[^\d.]/g, "")) : null) : f[k]]))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deal", d.id] })
      qc.invalidateQueries({ queryKey: ["deals"] })
      toast("Saved.")
      onDone()
    },
  })
  const field = (k: keyof typeof f, label: string, placeholder: string, extra?: React.ComponentProps<typeof Input>) => (
    <div className="grid gap-1.5">
      <Label htmlFor={`deal-${k}`}>{label}</Label>
      <Input id={`deal-${k}`} value={f[k]} placeholder={placeholder} onChange={(e) => setF({ ...f, [k]: e.target.value })} {...extra} />
    </div>
  )
  return (
    <form className="grid gap-3 rounded-xl border p-4" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
      {field("wants", "Wants", "2022 Toyota RAV4 XLE")}
      <div className="grid gap-3 sm:grid-cols-2">
        {field("budget_max", "Budget, up to", "$30,000", { inputMode: "numeric" })}
        <div className="grid gap-1.5">
          <Label htmlFor="deal-paying">Paying by</Label>
          <Select value={f.payment_method} onValueChange={(v) => setF({ ...f, payment_method: v })}>
            <SelectTrigger id="deal-paying" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>{Object.entries(PAYING).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>
      {field("trade_in", "Trade-in", "2016 Honda Civic, about 88,000 miles")}
      {field("timeline", "When", "This weekend")}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" disabled={save.isPending || changed.length === 0}>{save.isPending ? "Saving…" : "Save"}</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
        {save.isError && <p role="alert" className="text-sm">{save.error.message}</p>}
      </div>
    </form>
  )
}

function Body({ d, onMove }: { d: Detail; onMove: (stage: Stage, reason?: string) => void }) {
  const qc = useQueryClient()
  const give = useMutation({
    mutationFn: (owner_user_id: string) => send("PATCH", `/deals/${d.id}`, { owner_user_id }),
    onSuccess: (_r, id) => {
      qc.invalidateQueries({ queryKey: ["deals"] })
      qc.invalidateQueries({ queryKey: ["deal", d.id] })
      toast(`${d.client.name}'s deal is now ${d.people.find((p) => p.id === id)?.name ?? "theirs"}'s.`)
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't change who has it. Try again."),
  })
  const [editing, setEditing] = useState(false)
  const first = d.client.name.split(" ")[0]
  const said = d.messages.filter((m) => m.body)
  const wants = d.car?.name ?? d.wants
  const facts: [string, React.ReactNode][] = [
    ["Wants", wants ?? `Hasn't said yet`],
    ...(d.car ? [["In stock", (
      <span key="car" className="tabular-nums">
        Stock <span className="font-mono text-xs">{d.car.stock_number}</span>
        {d.car.price != null && `, listed at ${usd.format(d.car.price)}`}
        {d.car.status !== "available" && `, ${d.car.status === "hold" ? "on hold" : "sold"}`}
      </span>
    )] as [string, React.ReactNode]] : []),
    ...(money(d) ? [["Budget", <span key="b" className="tabular-nums">{money(d)}</span>] as [string, React.ReactNode]] : []),
    ...(d.payment_method ? [["Paying by", PAYING[d.payment_method as keyof typeof PAYING] ?? d.payment_method] as [string, React.ReactNode]] : []),
    ["Trade-in", d.trade_in ?? "None mentioned"],
    ...(d.timeline ? [["When", d.timeline] as [string, React.ReactNode]] : []),
    ...(d.destination ? [["Delivery to", d.destination] as [string, React.ReactNode]] : []),
  ]

  return (
    <div className="flex flex-col gap-6 px-4 pb-6 sm:px-6" data-vip={d.client.vip || undefined}>
      <div className="flex flex-wrap gap-2">
        {d.conversation_id && (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/inbox?c=${d.conversation_id}`}><IconMessage /> Message</Link>
          </Button>
        )}
        {d.client.phone && (
          <Button size="sm" asChild>
            <a href={`tel:${d.client.phone}`}><IconPhone /> Call {first}</a>
          </Button>
        )}
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/clients/profile?id=${d.client.id}`}><IconExternalLink /> Profile</Link>
        </Button>
      </div>

      {d.can_move ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="deal-stage">Stage</Label>
            <Select value={d.stage === "lost" ? `lost:${d.lost_reason ?? ""}` : d.stage}
              onValueChange={(v) => (v.startsWith("lost:") ? onMove("lost", v.slice(5)) : onMove(v as Stage))}>
              <SelectTrigger id="deal-stage" className="w-full"><SelectValue>{d.stage === "lost" ? `Lost${d.lost_reason ? `: ${d.lost_reason}` : ""}` : d.stage_label}</SelectValue></SelectTrigger>
              <SelectContent>
                {STAGES.filter((s) => s.stage !== "lost").map((s) => <SelectItem key={s.stage} value={s.stage}>{s.label}</SelectItem>)}
                <SelectGroup>
                  <SelectLabel>Lost, because</SelectLabel>
                  {LOST_REASONS.map((r) => <SelectItem key={r} value={`lost:${r}`}>{r}</SelectItem>)}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="deal-owner">Salesperson</Label>
            <Select value={d.owner?.id} onValueChange={(v) => give.mutate(v)} disabled={give.isPending}>
              <SelectTrigger id="deal-owner" className="w-full">
                <SelectValue placeholder="Nobody yet" />
              </SelectTrigger>
              <SelectContent>
                {d.people.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
      ) : (
        <p className="text-sm">{d.stage_label}. {d.owner?.name ? `${d.owner.name} has it.` : "Nobody has it yet."}</p>
      )}

      <Section title="What they want" action={d.can_move && !editing ? <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>Edit</Button> : null}>
        {editing ? (
          <EditWants d={d} onDone={() => setEditing(false)} />
        ) : (
          <dl className="divide-y border-y">
            {facts.map(([k, v]) => <Fact key={k} label={k}>{v}</Fact>)}
          </dl>
        )}
      </Section>

      <Section title="What's next">
        {!d.next_appointment && !d.next_task ? (
          <p className="text-sm text-muted-foreground">Nothing booked or due. If {first} is worth chasing, book a visit or set a task.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {d.next_appointment && (
              <li className="flex items-start gap-2">
                <IconCalendarEvent className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span><span className="first-letter:uppercase">{d.next_appointment.what}</span>, {stamp(d.next_appointment.starts_at)}</span>
              </li>
            )}
            {d.next_task && (
              <li className="flex items-start gap-2">
                <IconBell className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span>
                  {d.next_task.title}
                  {d.next_task.due_at && (
                    <span className={cn("tabular-nums", d.next_task.overdue ? "text-overdue" : "text-muted-foreground")}>
                      {d.next_task.overdue ? `, overdue since ${stamp(d.next_task.due_at)}` : `, due ${stamp(d.next_task.due_at)}`}
                    </span>
                  )}
                </span>
              </li>
            )}
          </ul>
        )}
      </Section>

      <Section title={said.length ? `Latest ${CHANNEL[said[0].channel] ?? said[0].channel} conversation` : "Conversation"}>
        {said.length === 0 ? (
          <p className="text-sm text-muted-foreground">No messages yet.</p>
        ) : (
          <ol className="flex flex-col gap-3">
            {said.map((m, i) => {
              const ai = m.from === "ai" && !d.client.vip
              const who = m.from === "customer" ? first : ai ? "Ondra" : m.from === "user" ? (m.who ?? "Your team") : "Note"
              return (
                <li key={i} className="text-sm">
                  <p className="flex items-baseline gap-2">
                    <span className={cn("flex items-center gap-1 font-medium", ai && "text-ai")}>{ai && <OndraMark className="size-3.5" />}{who}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">{stamp(m.at)}</span>
                  </p>
                  <p className="mt-0.5 text-pretty text-muted-foreground">{m.body}</p>
                </li>
              )
            })}
          </ol>
        )}
        {d.conversation_id && (
          <Link href={`/inbox?c=${d.conversation_id}`} className="w-fit text-sm underline underline-offset-4">Open the whole conversation</Link>
        )}
      </Section>

      <Section title="How it's moved">
        <ol className="flex flex-col gap-1.5 text-sm text-muted-foreground">
          <li>
            {d.by_ondra ? <span className="text-ai">Opened by Ondra</span> : "Opened"}
            {d.source_channel && CHANNEL[d.source_channel] ? ` from a ${CHANNEL[d.source_channel]} conversation` : ""}, {stamp(d.created_at)}
          </li>
          {d.history.map((h, i) => (
            <li key={i}>
              {STAGES.find((s) => s.stage === h.from)?.label ?? h.from} to {STAGES.find((s) => s.stage === h.to)?.label ?? h.to}
              {h.by ? ` by ${h.by}` : ""}, {stamp(h.at)}
            </li>
          ))}
        </ol>
      </Section>
    </div>
  )
}

export function DealSheet({ id, onClose, onMove }: { id: string | null; onClose: () => void; onMove: (id: string, stage: Stage, reason?: string) => void }) {
  const q = useQuery({ queryKey: ["deal", id], queryFn: () => api<Detail>(`/deals/${id}`), enabled: !!id })
  const d = q.data
  return (
    <Sheet open={!!id} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-lg">
        <SheetHeader className="px-4 pt-5 pb-4 sm:px-6">
          <SheetTitle className="flex items-center gap-2 pr-8 text-xl font-normal tracking-tight">
            {d?.client.vip && <VipTag size="lg" />}
            {d ? d.client.name : "Deal"}
          </SheetTitle>
          <SheetDescription className="tabular-nums">
            {d ? [formatPhone(d.client.phone) || d.client.email, d.last_contact_at ? `last in touch ${stamp(d.last_contact_at)}` : "not in touch yet"].filter(Boolean).join(", ") : "Loading"}
          </SheetDescription>
        </SheetHeader>
        {q.isPending ? (
          <div className="flex flex-col gap-3 px-4 sm:px-6" aria-label="Loading">
            <Skeleton className="h-9 w-full" /><Skeleton className="h-40 w-full" /><Skeleton className="h-32 w-full" />
          </div>
        ) : q.isError ? (
          <div className="px-4 sm:px-6"><LoadError message={q.error.message} onRetry={() => q.refetch()} /></div>
        ) : d ? (
          <Body d={d} onMove={(stage, reason) => onMove(d.id, stage, reason)} />
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

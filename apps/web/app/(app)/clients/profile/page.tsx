"use client"

/**
 * Client profile. One job: everything about this person in one place, before you call them.
 * Header: who they are and how to reach them, with the two actions people take. Main: one timeline across every
 * channel. Side: Ondra's summary, the deal, what's next, and consent. VIPs get no Ondra summary.
 * The client comes from the API; their conversation history is example data until Step 3.
 */

import {
  IconArrowLeft,
  IconBan,
  IconBell,
  IconBrandWhatsapp,
  IconCalendarEvent,
  IconMail,
  IconMessage,
  IconPhone,
  IconPhoneIncoming,
  IconPhoneX,
} from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { api, ApiError, type Contact } from "@/lib/api"
import { cn } from "@/lib/utils"
import { VipTag } from "@/components/vip"
import { VipButton, VipPanel } from "@/components/vip-control"

const CHANNEL = {
  phone: { icon: IconPhone, label: "Phone" },
  sms: { icon: IconMessage, label: "Text" },
  email: { icon: IconMail, label: "Email" },
  whatsapp: { icon: IconBrandWhatsapp, label: "WhatsApp" },
} as const

function formatPhone(e164?: string) {
  const m = e164?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : (e164 ?? "")
}

type TimelineEntry =
  | { kind: "message"; at: string; channel: string; direction: string; author: string; author_name: string | null; body: string | null; status: string }
  | { kind: "task"; at: string; title: string; status: string; source: string; assignee_name: string | null }
  | { kind: "appointment"; at: string; status: string; service_type: string | null; source: string }
  | { kind: "call"; at: string; handled_by: "ai" | "staff" | "owner" | "missed" | null; outcome: string | null; duration_s: number | null; summary: string | null }
type Timeline = {
  items: TimelineEntry[]
  opted_out: boolean
  deal: { stage: string; vehicle: string | null; budget_max: number | null } | null
  next_task: { title: string; due_at: string | null; overdue: boolean } | null
  brief: string | null
  latest_conversation_id: string | null
}

function stamp(iso: string) {
  const d = new Date(iso)
  const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase()
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })}, ${time}`
}

function TimelineItem({ e, first }: { e: TimelineEntry; first: string }) {
  let icon = <IconMessage className="size-4" aria-hidden="true" />
  let who = first
  let text = ""
  let ai = false
  if (e.kind === "message") {
    ai = e.author === "ai"
    who = ai ? "Ondra" : e.author === "user" ? (e.author_name ?? "Your team") : first
    text = (e.body ?? "") + (e.status === "failed" ? " (not delivered)" : "")
    icon = ai ? <OndraMark className="size-4" /> : e.channel === "email" ? <IconMail className="size-4" aria-hidden="true" /> : <IconMessage className="size-4" aria-hidden="true" />
  } else if (e.kind === "task") {
    ai = e.source === "ai_handoff"
    who = ai ? "Handed to your team by Ondra" : e.status === "done" ? "Task done" : "Task"
    text = e.title.split(": ").slice(-1)[0] + (e.assignee_name ? `, ${e.assignee_name}` : "")
    icon = ai ? <OndraMark className="size-4" /> : <IconBell className="size-4" aria-hidden="true" />
  } else if (e.kind === "call") {
    // A VIP's calls never reach Ondra, and the API sends no summary for them.
    ai = e.handled_by === "ai"
    const length = e.duration_s ? `, ${Math.floor(e.duration_s / 60)}:${String(e.duration_s % 60).padStart(2, "0")}` : ""
    who = e.handled_by === "missed" ? "Missed call" : ai ? "Call answered by Ondra" : e.handled_by === "owner" ? "Call put through to the owner" : e.handled_by ? "Call taken by your team" : "On a call now"
    text = (e.summary ?? "") + (e.summary ? "" : length.replace(/^, /, "Length "))
    icon = e.handled_by === "missed" ? <IconPhoneX className="size-4" aria-hidden="true" /> : <IconPhoneIncoming className="size-4" aria-hidden="true" />
  } else {
    ai = e.source === "ai"
    who = ai ? "Booked by Ondra" : "Appointment"
    text = `${e.service_type ?? "Visit"}, ${e.status}`
    icon = <IconCalendarEvent className="size-4" aria-hidden="true" />
  }
  return (
    <li className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-3 pb-5 last:pb-0">
      <span className={cn("relative z-10 flex size-8 items-center justify-center rounded-full border bg-background", ai ? "text-ai" : "text-muted-foreground")}>{icon}</span>
      <div className="min-w-0 pt-1">
        <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className={cn("font-medium", ai && "text-ai")}>{who}</span>
          <span className="text-xs text-muted-foreground tabular-nums">{stamp(e.at)}</span>
        </p>
        <p className="mt-0.5 text-sm break-words text-muted-foreground">{text}</p>
      </div>
    </li>
  )
}

function Profile({ id }: { id: string }) {
  const [vipOpen, setVipOpen] = useState(false)
  const q = useQuery({ queryKey: ["contact", id], queryFn: () => api<Contact>(`/contacts/${id}`) })
  const tl = useQuery({ queryKey: ["timeline", id], queryFn: () => api<Timeline>(`/contacts/${id}/timeline`), enabled: q.isSuccess })
  if (q.isPending) return <div className="p-6"><TableSkeleton rows={4} /></div>
  if (q.isError)
    return (
      <div className="p-6">
        {q.error instanceof ApiError && q.error.status === 404 ? (
          <p className="rounded-xl border p-6 text-sm text-muted-foreground">This client doesn&apos;t exist, or isn&apos;t visible to your role.</p>
        ) : (
          <LoadError message={q.error.message} onRetry={() => q.refetch()} />
        )}
      </div>
    )

  const c = q.data
  const first = c.display_name.split(" ")[0]
  const phone = c.identities.find((i) => i.kind === "phone")?.value
  const email = c.identities.find((i) => i.kind === "email")?.value
  const pref = CHANNEL[c.preferred_channel as keyof typeof CHANNEL]
  const t = tl.data

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-6 lg:px-6" data-vip={c.is_vip || undefined}>
      <div className="flex flex-col gap-4">
        <Link href="/clients" className="flex w-fit items-center gap-1.5 rounded-sm text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
          <IconArrowLeft className="size-4" aria-hidden="true" /> Clients
        </Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-2xl font-medium tracking-tight">
              {c.is_vip && <VipTag size="lg" />}
              {c.display_name}
            </h2>
            <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
              {pref && (
                <span className="flex items-center gap-1.5">
                  <pref.icon className="size-4" aria-hidden="true" /> Prefers {pref.label.toLowerCase()}
                </span>
              )}
              {phone && <span className="tabular-nums">{formatPhone(phone)}</span>}
              {email && <span>{email}</span>}
            </p>
            {c.is_vip && <p className="mt-2 text-sm text-muted-foreground">A person always handles {first}: Ondra never replies, and calls ring straight through.</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <Link href={t?.latest_conversation_id ? `/inbox?c=${t.latest_conversation_id}` : "/inbox"}>
                <IconMessage /> Message
              </Link>
            </Button>
            {phone && (
              <Button asChild>
                <a href={`tel:${phone}`}><IconPhone /> Call</a>
              </Button>
            )}
            <VipButton c={c} onOpen={() => setVipOpen(true)} />
          </div>
        </div>
        {vipOpen && <VipPanel c={c} onClose={() => setVipOpen(false)} />}
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section aria-labelledby="timeline">
          <h3 id="timeline" className="mb-4 text-sm font-medium text-muted-foreground">
            History
          </h3>
          {tl.isPending ? (
            <TableSkeleton rows={4} />
          ) : t && t.items.length > 0 ? (
            <ol className="relative before:absolute before:top-2 before:bottom-2 before:left-4 before:w-px before:bg-border">
              {t.items.map((e, i) => (
                <TimelineItem key={i} e={e} first={first} />
              ))}
            </ol>
          ) : (
            <p className="rounded-xl border p-6 text-sm text-muted-foreground">
              No conversations yet. Calls, texts, emails and WhatsApp messages with {first} will show up here.
            </p>
          )}
        </section>

        <aside className="flex flex-col gap-6" aria-label="About this client">
          {!c.is_vip && t?.brief && (
            <section data-slot="ai-summary">
              <h3 className="flex items-center gap-1.5 text-xs font-medium text-ai">
                <OndraMark className="size-3.5" /> Summary by Ondra
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed">{t.brief}</p>
            </section>
          )}
          {t?.deal && (
            <section>
              <h3 className="text-xs font-medium text-muted-foreground">Deal</h3>
              <p className="mt-1.5 text-sm font-medium">{t.deal.vehicle ?? "Vehicle not chosen yet"}</p>
              <p className="text-sm text-muted-foreground first-letter:uppercase">
                {t.deal.stage}
                {t.deal.budget_max ? `, up to $${t.deal.budget_max.toLocaleString("en-US")}` : ""}
              </p>
            </section>
          )}
          {t?.next_task && (
            <section>
              <h3 className="text-xs font-medium text-muted-foreground">Next</h3>
              <p className="mt-1.5 text-sm font-medium first-letter:uppercase">{t.next_task.title.split(": ").slice(-1)[0]}</p>
              <p className={cn("text-sm tabular-nums", t.next_task.overdue ? "text-overdue" : "text-muted-foreground")}>
                {t.next_task.due_at ? `${t.next_task.overdue ? "Overdue, was due" : "Due"} ${stamp(t.next_task.due_at)}` : ""}
              </p>
            </section>
          )}
          <section>
            <h3 className="text-xs font-medium text-muted-foreground">Messages</h3>
            <p className="mt-1.5 text-sm">
              {t?.opted_out ? `Opted out on every channel. Nobody can message ${first} until they opt back in.` : "Allowed"}
            </p>
          </section>
        </aside>
      </div>
    </div>
  )
}

function ProfileFromQuery() {
  const id = useSearchParams().get("id")
  if (!id) return <p className="p-6 text-sm text-muted-foreground">Pick a client from the list.</p>
  return <Profile id={id} />
}

export default function ClientProfilePage() {
  return (
    <>
      <SiteHeader title="Client" />
      <Suspense fallback={<div className="p-6"><TableSkeleton rows={4} /></div>}>
        <ProfileFromQuery />
      </Suspense>
    </>
  )
}

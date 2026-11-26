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
  IconCrownFilled,
  IconMail,
  IconMessage,
  IconPhone,
  IconPhoneIncoming,
} from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { api, ApiError, type Contact } from "@/lib/api"
import { CONVERSATIONS, type ThreadEvent } from "@/lib/examples"
import { cn } from "@/lib/utils"

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

function TimelineItem({ e, first }: { e: ThreadEvent; first: string }) {
  let icon = <IconMessage className="size-4" aria-hidden="true" />
  let who = first
  let text = ""
  let ai = false
  if (e.kind === "message") {
    ai = e.author === "ondra"
    who = e.author === "ondra" ? "Ondra" : e.author === "staff" ? (e.name ?? "Your team") : first
    text = e.body
    icon = ai ? <OndraMark className="size-4" /> : e.channel === "email" ? <IconMail className="size-4" aria-hidden="true" /> : <IconMessage className="size-4" aria-hidden="true" />
  } else if (e.kind === "call") {
    ai = e.answeredBy === "Ondra"
    who = e.duration === "0:00" ? "Missed call" : ai ? "Call answered by Ondra" : "Call"
    text = e.summary
    icon = <IconPhoneIncoming className="size-4" aria-hidden="true" />
  } else if (e.kind === "event") {
    ai = !!e.ai
    who = ai ? "Ondra" : "Update"
    text = e.text
    icon = ai ? <OndraMark className="size-4" /> : /opted out/i.test(e.text) ? <IconBan className="size-4" aria-hidden="true" /> : <IconBell className="size-4" aria-hidden="true" />
  } else {
    ai = true
    who = "Draft by Ondra, waiting for approval"
    text = e.body
    icon = <OndraMark className="size-4" />
  }
  const time = "time" in e ? e.time : ""
  return (
    <li className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-3 pb-5 last:pb-0">
      <span className={cn("relative z-10 flex size-8 items-center justify-center rounded-full border bg-background", ai ? "text-ai" : "text-muted-foreground")}>{icon}</span>
      <div className="min-w-0 pt-1">
        <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className={cn("font-medium", ai && "text-ai")}>{who}</span>
          <span className="text-xs text-muted-foreground tabular-nums">{time}</span>
        </p>
        <p className="mt-0.5 text-sm text-muted-foreground">{text}</p>
      </div>
    </li>
  )
}

function Profile({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["contact", id], queryFn: () => api<Contact>(`/contacts/${id}`) })
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
  const history = CONVERSATIONS.find((x) => x.client === c.display_name)

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-6 lg:px-6" data-vip={c.is_vip || undefined}>
      <div className="flex flex-col gap-4">
        <Link href="/clients" className="flex w-fit items-center gap-1.5 rounded-sm text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
          <IconArrowLeft className="size-4" aria-hidden="true" /> Clients
        </Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-2xl font-medium tracking-tight">
              {c.is_vip && <IconCrownFilled className="size-5 text-vip" aria-label="VIP" />}
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
            {c.is_vip && <p className="mt-2 text-sm text-muted-foreground">VIP. Calls ring you directly, and Ondra never replies to {first}.</p>}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <Link href="/inbox">
                <IconMessage /> Message
              </Link>
            </Button>
            <Button>
              <IconPhone /> Call
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section aria-labelledby="timeline">
          <h3 id="timeline" className="mb-4 text-sm font-medium text-muted-foreground">
            History
          </h3>
          {history ? (
            <ol className="relative before:absolute before:top-2 before:bottom-2 before:left-4 before:w-px before:bg-border">
              {[...history.events].reverse().map((e, i) => (
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
          {!c.is_vip && history?.brief && (
            <section data-slot="ai-summary">
              <h3 className="flex items-center gap-1.5 text-xs font-medium text-ai">
                <OndraMark className="size-3.5" /> Summary by Ondra
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed">{history.brief}</p>
            </section>
          )}
          {history?.deal && (
            <section>
              <h3 className="text-xs font-medium text-muted-foreground">Deal</h3>
              <p className="mt-1.5 text-sm font-medium">{history.deal.vehicle}</p>
              <p className="text-sm text-muted-foreground">{history.deal.stage}</p>
            </section>
          )}
          {history?.upcoming?.[0] && (
            <section>
              <h3 className="text-xs font-medium text-muted-foreground">Next</h3>
              <p className="mt-1.5 text-sm font-medium">{history.upcoming[0].title}</p>
              <p className="text-sm text-muted-foreground tabular-nums">{history.upcoming[0].when}</p>
            </section>
          )}
          <section>
            <h3 className="text-xs font-medium text-muted-foreground">Consent</h3>
            <dl className="mt-1.5 grid gap-1 text-sm">
              {(history?.consent ?? [{ channel: "Text", status: "Not recorded yet" }]).map((k) => (
                <div key={k.channel} className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-2">
                  <dt className="text-muted-foreground">{k.channel}</dt>
                  <dd>{k.status}</dd>
                </div>
              ))}
            </dl>
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
      <SiteHeader title="Client" note="History is example data until Step 3" />
      <Suspense fallback={<div className="p-6"><TableSkeleton rows={4} /></div>}>
        <ProfileFromQuery />
      </Suspense>
    </>
  )
}

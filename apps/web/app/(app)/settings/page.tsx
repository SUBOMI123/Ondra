"use client"

/**
 * Settings. One job: find the thing you want to change, and see at a glance what's set and whether anything needs you.
 * An index, not a form: four groups (your dealership, your team, Ondra, you), one row per page. Each row says in
 * plain words what's set right now, read from the same API the page uses, and calls out what's waiting on someone.
 * Rows a role can't open are left out, and "You" is the owner's alone.
 */

import {
  IconArrowsSplit,
  IconBook,
  IconBrandWhatsapp,
  IconBuildingStore,
  IconCalendarEvent,
  IconChevronRight,
  IconMessage2,
  IconMessages,
  IconPlug,
  IconRepeat,
  IconUsers,
  type Icon,
} from "@tabler/icons-react"
import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import Link from "next/link"

import { SiteHeader } from "@/components/dashboard/site-header"
import { useAuth } from "@/components/providers"
import { type Day, type SettingsData, useSettings } from "@/components/settings/shell"
import { ROLE_LABEL, type TeamData } from "@/components/settings/team"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"

// --- plain-words summaries -------------------------------------------------------------------------------------

function clock(hhmm: string) {
  const [h, m] = hhmm.split(":").map(Number)
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, "0")}` : ""} ${h < 12 ? "am" : "pm"}`
}

function list(words: string[]) {
  return words.length <= 1 ? (words[0] ?? "") : `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

function hoursToday(d: SettingsData) {
  const tz = d.business.timezone
  const day = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: tz }).format(new Date()).toLowerCase().slice(0, 3) as Day
  const span = d.business.hours[day]
  const city = tz.split("/").pop()?.replace(/_/g, " ")
  return `${span ? `Open today ${clock(span[0])} to ${clock(span[1])}` : "Closed today"}, ${city} time`
}

const CHANNEL_WORD = { sms: "texts", whatsapp: "WhatsApp", email: "email", phone: "calls" } as const

function channels(d: SettingsData): Status {
  const on = d.channels.filter((c) => c.active)
  if (d.channels.length === 0) return { text: "Nothing connected yet", needs: "Connect one" }
  const kinds = [...new Set(on.map((c) => CHANNEL_WORD[c.channel]))]
  const off = d.channels.length - on.length
  const test = on.filter((c) => !c.live).length
  const words = kinds.length ? `${list(kinds)} reach Ondra` : "All turned off"
  const mode = test === 0 ? "" : test === on.length ? ", all in test mode" : `, ${test} in test mode`
  return { text: `${words.charAt(0).toUpperCase()}${words.slice(1)}${mode}${off ? `. ${off} turned off` : ""}` }
}

function replies(d: SettingsData) {
  const price = { none: "never shares prices", listed: "shares listed prices", range: "shares a price range" }[d.replies.price_disclosure]
  return d.replies.draft_mode ? `Draft mode: you approve every reply. ${price.charAt(0).toUpperCase()}${price.slice(1)}` : `Replies on its own and ${price}`
}

// --- rows ------------------------------------------------------------------------------------------------------

type Status = { text: string; needs?: string }
type Row = { href: string; title: string; icon: Icon; status: Status | null; hidden?: boolean }

/** A summary from a query: null while loading, a fallback when it fails, hidden when the role can't open it. */
function from<T>(q: UseQueryResult<T>, make: (d: T) => Status, failed: string) {
  const forbidden = q.error instanceof ApiError && q.error.status === 403
  return { status: q.isPending ? null : q.isError ? { text: failed } : make(q.data), hidden: forbidden }
}

function SettingsRow({ r }: { r: Row }) {
  return (
    <li>
      <Link
        href={r.href}
        className="grid grid-cols-[1.25rem_minmax(0,1fr)_1rem] items-center gap-x-4 px-4 py-3.5 outline-none hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
      >
        <r.icon className="size-5 text-muted-foreground" aria-hidden="true" />
        <span className="flex min-w-0 flex-col gap-0.5 sm:flex-row sm:items-center sm:gap-4">
          <span className="min-w-0 flex-1">
            <span className="block font-medium">{r.title}</span>
            {r.status === null ? (
              <Skeleton className="mt-1 h-4 w-56 max-w-full" />
            ) : (
              <span className="block text-sm text-pretty text-muted-foreground">{r.status.text}</span>
            )}
          </span>
          {r.status?.needs && (
            <span className="flex shrink-0 items-center gap-1.5 text-sm font-medium">
              <span className="size-1.5 rounded-full bg-foreground" aria-hidden="true" />
              {r.status.needs}
            </span>
          )}
        </span>
        <IconChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
      </Link>
    </li>
  )
}

function Group({ id, title, description, rows }: { id: string; title: string; description: string; rows: Row[] }) {
  const shown = rows.filter((r) => !r.hidden)
  if (shown.length === 0) return null
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <div>
        <h2 id={id} className="text-base font-medium">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <ul className="divide-y overflow-hidden rounded-xl border">
        {shown.map((r) => <SettingsRow key={r.href} r={r} />)}
      </ul>
    </section>
  )
}

// --- page ------------------------------------------------------------------------------------------------------

type Health = { state: "off" | "ok" | "warning" | "error" }
type FollowUps = { sequences: { active: boolean }[]; scheduled: number; awaiting_approval: number }
type Assistant = { briefing_on: boolean; briefing_time: string; alerts_on: boolean }

export default function SettingsPage() {
  const { me } = useAuth()
  const isOwner = me?.role === "owner"
  const opts = { retry: false } as const
  const settings = useSettings()
  const team = useQuery({ queryKey: ["users", "summary"], queryFn: () => api<TeamData>("/users?limit=1"), ...opts })
  const routing = useQuery({ queryKey: ["routing"], queryFn: () => api<{ rules: { active: boolean }[] }>("/routing"), ...opts })
  const integrations = useQuery({ queryKey: ["integrations"], queryFn: () => api<{ crm: Health; inventory: Health; dms: Health }>("/integrations"), ...opts })
  const knowledge = useQuery({ queryKey: ["knowledge"], queryFn: () => api<{ unanswered: unknown[]; answers: unknown[] }>("/knowledge"), ...opts })
  const followUps = useQuery({ queryKey: ["follow-ups"], queryFn: () => api<FollowUps>("/follow-ups"), ...opts })
  const types = useQuery({ queryKey: ["appointment-types"], queryFn: () => api<{ items: { name: string; active: boolean }[] }>("/appointment-types"), ...opts })
  const assistant = useQuery({ queryKey: ["owner-assistant"], queryFn: () => api<Assistant>("/settings/owner-assistant"), enabled: isOwner, ...opts })

  const canEdit = settings.data?.can_edit ?? true
  const s = (make: (d: SettingsData) => Status) => from(settings, make, "Couldn't load this")

  const dealership: Row[] = [
    { href: "/settings/business", title: "Business and hours", icon: IconBuildingStore, ...s((d) => ({ text: hoursToday(d) })) },
    { href: "/settings/channels", title: "Channels", icon: IconMessages, ...s(channels) },
    {
      href: "/settings/integrations", title: "Integrations", icon: IconPlug,
      ...from(integrations, (d) => {
        const parts = [["leads to your CRM", d.crm], ["inventory import", d.inventory], ["service system", d.dms]] as const
        const broken = parts.filter(([, h]) => h.state === "error").map(([n]) => n)
        const on = parts.filter(([, h]) => h.state !== "off").map(([n]) => n)
        const text = on.length === 0 ? "Nothing connected yet" : `${list(on)} connected`
        return {
          text: text.charAt(0).toUpperCase() + text.slice(1),
          needs: broken.length ? `${broken.length === 1 ? broken[0].charAt(0).toUpperCase() + broken[0].slice(1) : `${broken.length} integrations`} not working` : undefined,
        }
      }, "Couldn't check your integrations"),
    },
  ]
  const people: Row[] = [
    {
      href: "/settings/team", title: "People", icon: IconUsers,
      ...from(team, (d) => {
        const c = d.counts
        const roles = Object.entries(c.role).sort((a, b) => b[1] - a[1]).map(([r, n]) => `${n} ${ROLE_LABEL[r] ?? r}`)
        return {
          text: `${plural(c.status.active, "person", "people")}: ${list(roles)}`,
          needs: c.status.invited > 0 ? `${c.status.invited} invited, not joined` : undefined,
        }
      }, "Couldn't load the team"),
    },
    {
      href: "/settings/routing", title: "Who gets what", icon: IconArrowsSplit,
      ...from(routing, (d) => {
        const on = d.rules.filter((r) => r.active).length
        return { text: on === 0 ? "The usual teams: sales to Sales, service to Service, complaints to Managers" : `${plural(on, "rule")} of your own, then the usual teams` }
      }, "Couldn't load your rules"),
    },
  ]
  const ondra: Row[] = [
    { href: "/settings/replies", title: "How it replies", icon: IconMessage2, ...s((d) => ({ text: replies(d) })) },
    {
      href: "/settings/knowledge", title: "What it knows", icon: IconBook,
      ...from(knowledge, (d) => ({
        text: d.answers.length === 0 ? "No answers yet" : `${plural(d.answers.length, "answer")} to what customers ask`,
        needs: d.unanswered.length > 0 ? `${plural(d.unanswered.length, "question")} to answer` : undefined,
      }), "Couldn't load what Ondra knows"),
    },
    {
      href: "/settings/follow-ups", title: "Follow-ups", icon: IconRepeat,
      ...from(followUps, (d) => {
        const on = d.sequences.filter((x) => x.active).length
        return {
          text: on === 0 ? "Off, so customers who go quiet get no check-in" : `${plural(on, "follow-up")} on, ${d.scheduled} scheduled`,
          needs: d.awaiting_approval > 0 ? `${d.awaiting_approval} to approve` : undefined,
        }
      }, "Couldn't load follow-ups"),
    },
    {
      href: "/settings/booking", title: "Booking", icon: IconCalendarEvent,
      ...from(types, (d) => {
        const names = d.items.filter((t) => t.active).map((t) => t.name)
        return { text: names.length === 0 ? "Nothing customers can book yet" : names.length <= 3 ? `Customers can book ${list(names)}` : `Customers can book ${names.slice(0, 2).join(", ")} and ${names.length - 2} more` }
      }, "Couldn't load what customers can book"),
    },
  ]
  const you: Row[] = [
    {
      href: "/settings/assistant", title: "Your WhatsApp assistant", icon: IconBrandWhatsapp, hidden: !isOwner,
      status: assistant.isPending ? null : assistant.isError ? { text: "Couldn't load this" } : {
        text: `${assistant.data.briefing_on ? `Morning briefing at ${clock(assistant.data.briefing_time)}` : "Morning briefing off"}, VIP alerts ${assistant.data.alerts_on ? "on" : "off"}`,
      },
    },
  ]

  return (
    <>
      <SiteHeader title="Settings" note={settings.data && !canEdit ? "View only. Owners and admins can change these." : undefined} />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 px-4 py-6 lg:px-6">
        <Group id="g-dealership" title="Your dealership" description="When you're open, and the numbers and systems Ondra works with." rows={dealership} />
        <Group id="g-team" title="Your team" description="Who works here, and who gets each message, call and handoff." rows={people} />
        <Group id="g-ondra" title="Ondra" description="How it talks to customers, what it can answer, and what it can book." rows={ondra} />
        <Group id="g-you" title="You" description="Just for the owner." rows={you} />
      </div>
    </>
  )
}

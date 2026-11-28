"use client"

/**
 * Today. One job: open it and know in five seconds what needs you, then whether things are on track.
 * It opens with a handover note (how many things need attention, and what Ondra did while you were away), then what needs
 * you beside today's bookings, then the week: the dealership's for admins and managers (with who's behind), your own
 * for everyone else. Every number opens the events it was counted from. Blue is Ondra's work and nothing else; red
 * is overdue and nothing else.
 */

import { IconAlertTriangle, IconChevronDown, IconFlame, IconPhoneX } from "@tabler/icons-react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useState } from "react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { useAuth } from "@/components/providers"
import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { ClientAvatar, VipTag } from "@/components/vip"

type NeedItem = { task_id: string; client: string | null; title: string; conversation_id: string | null; since?: string; due_at?: string | null }
type Overnight = {
  from: string; to: string; leads: number; responses_by_ai: number; responses_by_team: number; appointments_booked: number
  appointments_booked_by_ai: number; median_first_response_seconds: number | null; calls_by_ai: number; calls_missed: number
}
type Today = {
  timezone: string
  needs: {
    vips: NeedItem[]; drafts: number; overdue: NeedItem[]; overdue_count: number; hot: NeedItem[]; scope: "everyone" | "mine"
    callbacks: { count: number; overdue: number; oldest: { client: string; since: string } | null }
  }
  overnight: Overnight | null
  appointments: { id: string; starts_at: string; kind: string; client: string; with: string | null; by_ondra: boolean; vip: boolean }[]
  team: { user_id: string; name: string; overdue: number; callbacks: number }[]
}
type Totals = Record<string, number> & {
  leads_by_channel: Record<string, number>; handled_by: { ai: number; team: number }
  median_first_response_seconds: number | null; median_first_response_seconds_ai: number | null
  median_callback_seconds: number | null
}
type Report = {
  from: string; to: string; days: number; timezone: string; totals: Totals; previous: Totals
  series: { day: string; leads: number; responses_by_ai: number; responses_by_team: number; appointments_booked: number }[]
  pipeline: { by_stage: Record<string, number>; in_play: number; in_play_by_ai: number }
  labels: Record<string, string>
  people: { user_id: string; name: string; first_replies: number; median_first_response_seconds: number }[]
  callback_people: { user_id: string; name: string; callbacks: number; median_callback_seconds: number }[]
}
type Trace = {
  label: string; count: number
  events: { event_id: string; type: string; at: string; who: string | null; detail: Record<string, string | number | boolean>; backfilled: boolean }[]
}

const CHANNEL: Record<string, string> = { sms: "Text", whatsapp: "WhatsApp", email: "Email", phone: "Calls", owner: "Added from the WhatsApp assistant", unknown: "Not recorded" }
const STAGE: Record<string, string> = { new: "New", qualified: "Qualified", appointment: "Appointment", negotiating: "Negotiating", won: "Won", lost: "Lost" }
const chartConfig = { responses_by_ai: { label: "Ondra", color: "var(--chart-1)" }, responses_by_team: { label: "Your team", color: "var(--chart-staff)" } } satisfies ChartConfig

/** By the dealership's clock, like every time on the page. */
function greeting(tz: string) {
  const h = Number(new Date().toLocaleString("en-US", { hour: "numeric", hourCycle: "h23", timeZone: tz }))
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"
}

/** "41 s", "3 min 05 s", "1 h 12 min". A dash when there's nothing to measure. */
function duration(seconds: number | null | undefined) {
  if (seconds == null) return "—"
  const s = Math.round(seconds)
  if (s < 60) return `${s} s`
  if (s < 600) return s % 60 ? `${Math.floor(s / 60)} min ${s % 60} s` : `${s / 60} min`
  if (s < 3600) return `${Math.round(s / 60)} min`
  return `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")} min`
}

function clock(iso: string, tz: string) {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: tz }).toLowerCase()
}

/** "1:08 pm" today, "yesterday, 1:08 pm", or "Nov 24, 1:08 pm". */
function since(iso: string, tz: string) {
  const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: tz })
  const then = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today.getTime() - 86_400_000)
  if (day(then) === day(today)) return clock(iso, tz)
  if (day(then) === day(yesterday)) return `yesterday, ${clock(iso, tz)}`
  return `${then.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: tz })}, ${clock(iso, tz)}`
}

function dayLabel(iso: string, long = false) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", long ? { weekday: "long", month: "short", day: "numeric" } : { month: "short", day: "numeric" })
}

function n(count: number, one: string, many = `${one}s`) {
  return `${count} ${count === 1 ? one : many}`
}

/* ------------------------------------------------------------ what's behind a number */

function describe(e: Trace["events"][number]) {
  const d = e.detail
  if (e.type === "callback.first_try") {
    const rang = typeof d.rings === "number" && d.rings > 1 ? `Rang ${d.rings} times. ` : ""
    const did = d.result === "reached" ? "Spoke to them" : d.result === "no_answer" ? "Called, no answer," : d.result === "short" ? "A short call, likely voicemail," : d.result === "voicemail" ? "Got their voicemail," : "Left a message"
    return { by: typeof d.by === "string" ? d.by : null, text: `${rang}${did} ${duration(Number(d.seconds))} after the first ring, counting open hours` }
  }
  const by = d.by === "ai" || d.source === "ai" || d.handled_by === "ai" ? "Ondra" : d.by === "user" || d.source === "staff" || d.handled_by === "staff" ? "your team"
    : d.by === "owner" || d.handled_by === "owner" ? "a person directly" : d.handled_by === "missed" ? "nobody (missed)" : null
  const parts: string[] = []
  if (typeof d.channel === "string") parts.push(CHANNEL[d.channel] ?? d.channel)
  if (typeof d.type === "string") parts.push(d.type)
  if (typeof d.seconds === "number") parts.push(`answered in ${duration(d.seconds)}`)
  if (d.after_hours === true) parts.push("after hours")
  return { by, text: parts.join(", ") }
}

function TraceSheet({ metric, days, tz, onClose }: { metric: string | null; days: number; tz: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["analytics", "trace", metric, days], queryFn: () => api<Trace>(`/analytics/trace?metric=${metric}&days=${days}`), enabled: !!metric })
  return (
    <Sheet open={!!metric} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{q.data?.label ?? "What's behind this number"}</SheetTitle>
          <SheetDescription>{q.data ? `${n(q.data.count, "event")} in the last ${days} days. The number on the page is a count of exactly these.` : "Loading the events this number was counted from."}</SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-6">
          {q.isPending ? <Skeleton className="h-40 w-full" /> : q.isError ? <p role="alert" className="text-sm">{q.error.message}</p> : q.data.events.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing in this period.</p>
          ) : (
            <ul className="divide-y">
              {q.data.events.map((e) => {
                const d = describe(e)
                return (
                  <li key={e.event_id} className="grid gap-0.5 py-2.5 text-sm">
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="min-w-0 truncate font-medium">{e.who ?? "Not linked to a client"}</span>
                      <span className="shrink-0 text-muted-foreground tabular-nums">{dayLabel(e.at.slice(0, 10))}, {clock(e.at, tz)}</span>
                    </span>
                    <span className="text-muted-foreground">
                      {d.by === "Ondra" ? <span data-slot="ai-note" className="text-ai">By Ondra</span> : d.by ? `By ${d.by}` : null}
                      {d.by && d.text ? ". " : ""}{d.text}{e.backfilled ? `${d.by || d.text ? ". " : ""}Recorded from earlier history` : ""}
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

/* ------------------------------------------------------------ tiles and lists */

function Delta({ now, before, days, lowerIsBetter }: { now: number | null; before: number | null; days: number; lowerIsBetter?: boolean }) {
  if (now == null || before == null || before === 0 || now === before) return null
  const up = now > before
  const pct = Math.round((Math.abs(now - before) / before) * 100)
  // The arrow and the word always say the same thing. For a time, shorter is the good direction, so it reads "faster".
  const word = lowerIsBetter ? (up ? "slower" : "faster") : up ? "more" : "fewer"
  return <span className="text-xs text-muted-foreground tabular-nums">{up ? "\u25B2" : "\u25BC"} {pct}% {word} than the {days} days before</span>
}

function Tile({ label, value, context, delta, onOpen }: { label: string; value: string; context?: React.ReactNode; delta?: React.ReactNode; onOpen?: () => void }) {
  return (
    <div className="relative flex flex-col gap-1">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-normal tracking-tight tabular-nums">{value}</p>
      {context && <div className="text-xs">{context}</div>}
      {delta}
      {onOpen && (
        <button type="button" onClick={onOpen} className="mt-auto self-start pt-2 text-xs text-muted-foreground underline-offset-4 outline-none hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring">
          See what&apos;s behind this<span className="sr-only">: {label}</span>
        </button>
      )}
    </div>
  )
}

function BarList({ rows, empty }: { rows: { key: string; label: string; value: number }[]; empty: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  if (rows.every((r) => r.value === 0)) return <p className="text-sm text-muted-foreground">{empty}</p>
  return (
    <ul className="grid gap-2.5">
      {rows.map((r) => (
        <li key={r.key} className="grid grid-cols-[7.5rem_minmax(0,1fr)_2.5rem] items-center gap-3 text-sm">
          <span className="truncate">{r.label}</span>
          <span className="h-2 rounded-full bg-muted" aria-hidden="true"><span className="block h-2 rounded-full bg-foreground/70" style={{ width: `${(r.value / max) * 100}%`, minWidth: r.value ? 4 : 0 }} /></span>
          <span className="text-right tabular-nums">{r.value}</span>
        </li>
      ))}
    </ul>
  )
}

function RepliesChart({ r }: { r: Report }) {
  const total = r.totals.responses_by_ai + r.totals.responses_by_team
  if (total === 0) return <p className="text-sm text-muted-foreground">No customer was waiting for a reply in this period. When someone writes in, their first answer shows here, by who gave it.</p>
  if (r.series.filter((d) => d.responses_by_ai + d.responses_by_team > 0).length < 2)
    return <p className="text-sm">All {n(total, "first reply", "first replies")} came on one day, so there&apos;s no trend to draw yet.</p>
  return (
    <>
      <div className="mb-3 flex gap-4 text-xs tabular-nums">
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-[2px] bg-ai" aria-hidden="true" /><span className="text-muted-foreground">Ondra</span> {r.totals.responses_by_ai}</span>
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-[2px] bg-chart-staff" aria-hidden="true" /><span className="text-muted-foreground">Your team</span> {r.totals.responses_by_team}</span>
      </div>
      <ChartContainer config={chartConfig} className="h-52 w-full" role="img"
        aria-label={`First replies per day for the last ${r.days} days: ${r.totals.responses_by_ai} by Ondra and ${r.totals.responses_by_team} by your team.`}>
        <BarChart data={r.series} accessibilityLayer margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} minTickGap={24} tickFormatter={(v: string) => dayLabel(v)} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={28} tickCount={4} />
          <ChartTooltip cursor={{ fill: "var(--muted)", opacity: 0.5 }} content={({ active, payload, label }) => active && payload?.length ? (
            <div className="grid gap-1 rounded-lg border bg-background px-3 py-2 text-xs shadow-md">
              <p className="font-medium">{dayLabel(String(label), true)}</p>
              {payload.map((p) => (
                <p key={String(p.dataKey)} className="flex items-center gap-2 tabular-nums">
                  <span className="h-0.5 w-3 rounded" style={{ background: p.color }} aria-hidden="true" />
                  <span className="font-medium">{p.value}</span>
                  <span className="text-muted-foreground">{p.dataKey === "responses_by_ai" ? "by Ondra" : "by your team"}</span>
                </p>
              ))}
            </div>
          ) : null} />
          <Bar dataKey="responses_by_ai" stackId="a" fill="var(--color-responses_by_ai)" maxBarSize={32} stroke="var(--card)" strokeWidth={2} radius={[4, 4, 0, 0]} animationDuration={300} />
          <Bar dataKey="responses_by_team" stackId="a" fill="var(--color-responses_by_team)" maxBarSize={32} stroke="var(--card)" strokeWidth={2} radius={[4, 4, 0, 0]} animationDuration={300} />
        </BarChart>
      </ChartContainer>
      <table className="sr-only">
        <caption>First replies per day, by who gave them</caption>
        <thead><tr><th>Day</th><th>Ondra</th><th>Your team</th></tr></thead>
        <tbody>{r.series.map((d) => <tr key={d.day}><td>{dayLabel(d.day, true)}</td><td>{d.responses_by_ai}</td><td>{d.responses_by_team}</td></tr>)}</tbody>
      </table>
    </>
  )
}

/* ------------------------------------------------------------ the handover note */

/** The page's opening: how many things need you, and what Ondra did while the dealership was closed. The Ondra line
 * only appears when Ondra did something; zeros are not news. */
function Handover({ first, count, everyone, t, tz }: { first?: string; count: number | null; everyone: boolean; t?: Today; tz: string }) {
  const o = t?.overnight
  const did = o ? [
    o.responses_by_ai > 0 && `answered ${n(o.responses_by_ai, "customer")}`,
    o.appointments_booked_by_ai > 0 && `booked ${n(o.appointments_booked_by_ai, "appointment")}`,
    o.calls_by_ai > 0 && `took ${n(o.calls_by_ai, "call")}`,
  ].filter(Boolean) as string[] : []
  const list = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`)
  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: tz })
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{greeting(tz)}{first ? `, ${first}` : ""}. It&apos;s {today}.</p>
      {count === null ? (
        <Skeleton className="h-10 w-80 max-w-full" />
      ) : (
        <p className="text-3xl font-normal tracking-[-0.035em] text-balance sm:text-4xl">
          {count === 0 ? (everyone ? "Nothing needs attention right now." : "Nothing needs your attention right now.") : `${count === 1 ? "One thing needs" : `${count} things need`} ${everyone ? "" : "your "}attention.`}
        </p>
      )}
      {o && did.length > 0 && (
        <p data-slot="ai-note" className="flex items-start gap-2 text-pretty text-ai">
          <OndraMark className="mt-1 size-4 shrink-0" />
          <span>While you were closed, from {clock(o.from, tz)}, Ondra {list(did)}.{o.calls_missed > 0 ? ` ${n(o.calls_missed, "call was", "calls were")} missed.` : ""}</span>
        </p>
      )}
    </div>
  )
}

/* ------------------------------------------------------------ what needs you */

function Row({ icon, title, detail, action, vip }: { icon: React.ReactNode; title: React.ReactNode; detail?: React.ReactNode; action: React.ReactNode; vip?: boolean }) {
  return (
    <li className="relative flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5 sm:flex-nowrap" data-vip={vip || undefined}>
      {icon}
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        {detail && <p className="text-sm text-pretty text-muted-foreground sm:truncate">{detail}</p>}
      </div>
      {/* Phones: the action goes under the words, lined up with them, so the reason is read in full. */}
      <div className="w-full shrink-0 pl-13 sm:w-auto sm:pl-0">{action}</div>
    </li>
  )
}

const dot = "flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground"

function Needs({ q, tz }: { q: ReturnType<typeof useQuery<Today>>; tz: string }) {
  const needs = q.data?.needs
  return (
    <section aria-labelledby="needs" className="flex min-w-0 flex-col gap-3">
      <h2 id="needs" className="text-sm font-medium text-muted-foreground">{needs?.scope === "everyone" ? "Needs attention" : "Needs you"}</h2>
      {q.isPending ? <Skeleton className="h-56 w-full rounded-xl" /> : q.isError ? (
        <LoadError message={q.error.message} onRetry={() => q.refetch()} />
      ) : needCount(needs!) === 0 ? (
        <p className="rounded-xl border p-5 text-sm text-muted-foreground">VIPs waiting, replies to approve, missed callers and overdue tasks show here the moment there are any.</p>
      ) : (
        <ul className="divide-y rounded-xl border bg-card">
          {needs!.vips.map((v) => (
            <Row key={v.task_id} vip icon={<ClientAvatar name={v.client ?? ""} vip />} title={`${v.client} is waiting`}
              detail={`${v.title.replace(`${v.client}: `, "")}, since ${v.since ? since(v.since, tz) : "earlier"}.`}
              action={<Button asChild size="sm"><Link href={v.conversation_id ? `/inbox?c=${v.conversation_id}` : "/tasks"}>Reply yourself</Link></Button>} />
          ))}
          {needs!.callbacks.count > 0 && (
            <Row icon={<span className={dot} aria-hidden="true"><IconPhoneX className="size-4" /></span>}
              title={<>{n(needs!.callbacks.count, "caller")} to ring back{needs!.callbacks.overdue > 0 && <span className="text-overdue">, {needs!.callbacks.overdue} overdue</span>}</>}
              detail={needs!.callbacks.oldest ? `${needs!.callbacks.count > 1 ? "Longest waiting: " : ""}${needs!.callbacks.oldest.client}, since ${since(needs!.callbacks.oldest.since, tz)}.` : undefined}
              action={<Button asChild variant="outline" size="sm"><Link href="/calls?show=missed">Call back</Link></Button>} />
          )}
          {needs!.drafts > 0 && (
            <Row icon={<span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ai-subtle text-ai" aria-hidden="true"><OndraMark className="size-4" /></span>}
              title={`${n(needs!.drafts, "reply", "replies")} to approve`}
              detail={<span data-slot="ai-note" className="text-ai">Written by Ondra, waiting for a person to send {needs!.drafts === 1 ? "it" : "them"}.</span>}
              action={<Button asChild variant="outline" size="sm"><Link href="/inbox?filter=drafts">Review</Link></Button>} />
          )}
          {needs!.overdue_count > 0 && (
            <Row icon={<span className={dot} aria-hidden="true"><IconAlertTriangle className="size-4" /></span>}
              title={<span className="text-overdue">{n(needs!.overdue_count, "task")} overdue</span>}
              detail={`${needs!.overdue.slice(0, 2).map((o) => o.title).join(". ")}${needs!.overdue_count > 2 ? ", and more" : ""}.`}
              action={<Button asChild variant="outline" size="sm"><Link href="/tasks">Open tasks</Link></Button>} />
          )}
          {needs!.hot.map((h) => (
            <Row key={h.task_id} icon={<span className={dot} aria-hidden="true"><IconFlame className="size-4" /></span>} title={h.title}
              detail={`Marked urgent${h.due_at ? `, due ${since(h.due_at, tz)}` : ""}.`}
              action={<Button asChild variant="outline" size="sm"><Link href={h.conversation_id ? `/inbox?c=${h.conversation_id}` : "/tasks"}>Open</Link></Button>} />
          ))}
        </ul>
      )}
    </section>
  )
}

function needCount(x: Today["needs"]) {
  return x.vips.length + x.drafts + x.callbacks.count + x.overdue_count + x.hot.length
}

/* ------------------------------------------------------------ today's bookings */

function Agenda({ q, tz, everyone }: { q: ReturnType<typeof useQuery<Today>>; tz: string; everyone: boolean }) {
  const appts = q.data?.appointments ?? []
  return (
    <section aria-labelledby="booked" className="flex min-w-0 flex-col gap-3">
      <h2 id="booked" className="flex items-baseline justify-between text-sm font-medium text-muted-foreground">
        {everyone ? "Booked today" : "Your bookings today"}
        <Link href="/calendar" className="font-normal underline-offset-4 hover:text-foreground hover:underline">Calendar</Link>
      </h2>
      {q.isPending ? <Skeleton className="h-40 w-full rounded-xl" /> : appts.length === 0 ? (
        <p className="text-sm text-muted-foreground">{everyone ? "Nothing booked today yet." : "Nothing booked with you today."} Test drives and service Ondra or your team book for today show here.</p>
      ) : (
        <ol className="relative flex flex-col border-l pl-5">
          {appts.map((a) => (
            <li key={a.id} data-vip={a.vip || undefined} className="relative pb-5 last:pb-0">
              <span className={cn("absolute top-1.5 -left-[1.6rem] size-2.5 rounded-full border-2 border-background", a.by_ondra && !a.vip ? "bg-ai" : "bg-foreground")} aria-hidden="true" />
              <p className="text-sm text-muted-foreground tabular-nums">{clock(a.starts_at, tz)}</p>
              <p className="flex items-center gap-1.5 font-medium">{a.vip && <VipTag />}<span className="truncate">{a.client}</span></p>
              <p className="text-sm text-muted-foreground">{a.kind}{a.with && everyone ? `, with ${a.with}` : ""}</p>
              {a.by_ondra && !a.vip && <p data-slot="ai-note" className="text-sm text-ai">Booked by Ondra</p>}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

/* ------------------------------------------------------------ the week */

function PeriodPicker({ days, setDays }: { days: number; setDays: (d: number) => void }) {
  return (
    <ToggleGroup type="single" variant="outline" size="sm" value={String(days)} onValueChange={(v) => v && setDays(Number(v))} aria-label="Period">
      <ToggleGroupItem value="7" className="px-3">7 days</ToggleGroupItem>
      <ToggleGroupItem value="30" className="px-3">30 days</ToggleGroupItem>
    </ToggleGroup>
  )
}

function Behind({ team }: { team: Today["team"] }) {
  return (
    <div className="flex flex-col gap-3">
      <h3 className="font-medium">Who&apos;s behind</h3>
      {team.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nobody has overdue tasks or callers waiting.</p>
      ) : (
        <ul className="divide-y border-y text-sm">
          {team.map((p) => (
            <li key={p.user_id} className="flex items-baseline justify-between gap-4 py-2.5">
              <span className="truncate">{p.name}</span>
              <span className="shrink-0 text-muted-foreground tabular-nums">
                {p.overdue > 0 && <span className="text-overdue">{n(p.overdue, "overdue task")}</span>}
                {p.overdue > 0 && p.callbacks > 0 && ", "}
                {p.callbacks > 0 && n(p.callbacks, "caller", "callers")}{p.callbacks > 0 && " to ring back"}
              </span>
            </li>
          ))}
        </ul>
      )}
      {team.length > 0 && <Link href="/tasks" className="self-start text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">Move work on the Tasks board</Link>}
    </div>
  )
}

function DealershipWeek({ r, report, days, setDays, team, trace }: { r?: Report; report: ReturnType<typeof useQuery<Report>>; days: number; setDays: (d: number) => void; team: Today["team"]; trace: (m: string) => void }) {
  // The detail behind the four numbers (each day, each person, each channel), opened from the section's own header
  // and shown right under the numbers it explains.
  const [more, setMore] = useState(false)
  return (
    <section aria-labelledby="week" className="flex flex-col gap-6 border-t pt-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="week" className="text-xl font-normal tracking-tight">The last {days} days</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" aria-expanded={more} aria-controls="more-numbers" onClick={() => setMore((m) => !m)}>
            {more ? "Fewer numbers" : "More numbers"}
            <IconChevronDown className={cn("transition-transform", more && "rotate-180")} aria-hidden="true" />
          </Button>
          <PeriodPicker days={days} setDays={setDays} />
        </div>
      </div>
      {report.isPending ? <Skeleton className="h-28 w-full rounded-xl" /> : report.isError ? (
        <LoadError message={report.error.message} onRetry={() => report.refetch()} />
      ) : r && (
        <div className={cn("flex flex-col gap-10", report.isFetching && "opacity-60")} aria-busy={report.isFetching || undefined}>
          <div className="grid grid-cols-2 gap-x-6 gap-y-8 lg:grid-cols-4">
            <Tile label="Leads" value={String(r.totals.leads)} onOpen={() => trace("leads")}
              delta={<Delta now={r.totals.leads} before={r.previous.leads} days={r.days} />}
              context={<span><span data-slot="ai-note" className="text-ai">{r.totals.leads_by_ai} by Ondra</span><span className="text-muted-foreground">, {r.totals.leads_after_hours} after hours</span></span>} />
            <Tile label="First reply, median" value={duration(r.totals.median_first_response_seconds)} onOpen={() => trace("responses")}
              delta={<Delta now={r.totals.median_first_response_seconds} before={r.previous.median_first_response_seconds} days={r.days} lowerIsBetter />}
              context={<span><span data-slot="ai-note" className="text-ai">{r.totals.responses_by_ai} by Ondra</span><span className="text-muted-foreground">, {r.totals.responses_by_team} by your team</span></span>} />
            <Tile label="Appointments booked" value={String(r.totals.appointments_booked)} onOpen={() => trace("appointments_booked")}
              delta={<Delta now={r.totals.appointments_booked} before={r.previous.appointments_booked} days={r.days} />}
              context={<span><span data-slot="ai-note" className="text-ai">{r.totals.appointments_booked_by_ai} by Ondra</span><span className="text-muted-foreground">, {r.totals.appointments_showed} showed, {r.totals.appointments_no_show} didn&apos;t</span></span>} />
            <Tile label="Time to call back, median" value={duration(r.totals.median_callback_seconds)} onOpen={() => trace("callbacks")}
              delta={<Delta now={r.totals.median_callback_seconds} before={r.previous.median_callback_seconds} days={r.days} lowerIsBetter />}
              context={<span className="text-muted-foreground">{n(r.totals.calls_missed, "missed call")}, counted while you&apos;re open</span>} />
          </div>

          {more && (
            <div id="more-numbers" className="flex flex-col gap-10 border-t pt-8">
              <div>
                <h3 className="font-medium">Who answered first</h3>
                <p className="mb-4 text-sm text-muted-foreground">Each time a customer wrote in and was waiting, who gave the first reply.</p>
                <RepliesChart r={r} />
              </div>
              <div className="grid gap-10 md:grid-cols-2">
                <People title="First replies by person" rows={r.people.map((p) => ({ id: p.user_id, name: p.name, count: p.first_replies, seconds: p.median_first_response_seconds }))} count="Replies" empty="No person answered a waiting customer first in this period." />
                <People title="Call-backs by person" rows={r.callback_people.map((p) => ({ id: p.user_id, name: p.name, count: p.callbacks, seconds: p.median_callback_seconds }))} count="Rung back" empty="Nobody rang a missed caller back in this period." />
              </div>
              <div className="grid gap-10 md:grid-cols-2">
                <div>
                  <h3 className="mb-4 font-medium">Where leads came from</h3>
                  <BarList empty="No leads in this period." rows={Object.entries(r.totals.leads_by_channel).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ key: k, label: CHANNEL[k] ?? k, value: v }))} />
                </div>
                <Tile label="Follow-ups sent" value={String(r.totals.follow_ups_sent)} onOpen={() => trace("follow_ups_sent")}
                  delta={<Delta now={r.totals.follow_ups_sent} before={r.previous.follow_ups_sent} days={r.days} />} />
              </div>
            </div>
          )}

          <div className="grid gap-10 md:grid-cols-2">
            <Behind team={team} />
            <div className="flex flex-col gap-3">
              <h3 className="font-medium">Deals in play</h3>
              <p className="-mt-2 text-sm text-muted-foreground">
                {n(r.pipeline.in_play, "open deal")}{r.pipeline.in_play > 0 && <>, <span data-slot="ai-note" className="text-ai">{r.pipeline.in_play_by_ai} brought in by Ondra</span></>}.
              </p>
              <BarList empty="No deals yet. A deal starts when Ondra or your team records what a buyer wants." rows={Object.entries(r.pipeline.by_stage).map(([k, v]) => ({ key: k, label: STAGE[k] ?? k, value: v }))} />
            </div>
          </div>

        </div>
      )}
    </section>
  )
}

function People({ title, rows, count, empty }: { title: string; rows: { id: string; name: string; count: number; seconds: number }[]; count: string; empty: string }) {
  return (
    <div>
      <h3 className="mb-3 font-medium">{title}</h3>
      {rows.length === 0 ? <p className="text-sm text-muted-foreground">{empty}</p> : (
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr><th className="pb-2 font-normal">Who</th><th className="pb-2 text-right font-normal">{count}</th><th className="pb-2 text-right font-normal">Median</th></tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((p) => (
              <tr key={p.id}><td className="py-2">{p.name}</td><td className="py-2 text-right tabular-nums">{p.count}</td><td className="py-2 text-right tabular-nums">{duration(p.seconds)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

type BoardDeal = { stage: string; value: number | null }

/** A salesperson's own week: their deals, how fast they answered, how fast they rang back. Not the dealership's. */
function YourWeek({ r, report, days, setDays, meId }: { r?: Report; report: ReturnType<typeof useQuery<Report>>; days: number; setDays: (d: number) => void; meId?: string }) {
  const deals = useQuery({ queryKey: ["deals", "mine-summary"], queryFn: () => api<{ stages: { stage: string; deals: BoardDeal[] }[] }>("/deals?whose=mine") })
  const open = (deals.data?.stages ?? []).filter((s) => !["won", "lost"].includes(s.stage)).flatMap((s) => s.deals)
  const won = deals.data?.stages.find((s) => s.stage === "won")?.deals.length ?? 0
  const value = open.reduce((a, d) => a + (d.value ?? 0), 0)
  const mine = r?.people.find((p) => p.user_id === meId)
  const calls = r?.callback_people.find((p) => p.user_id === meId)
  return (
    <section aria-labelledby="week" className="flex flex-col gap-6 border-t pt-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="week" className="text-xl font-normal tracking-tight">Your last {days} days</h2>
        <PeriodPicker days={days} setDays={setDays} />
      </div>
      {report.isPending || deals.isPending ? <Skeleton className="h-28 w-full rounded-xl" /> : report.isError ? (
        <LoadError message={report.error.message} onRetry={() => report.refetch()} />
      ) : (
        <div className="grid grid-cols-2 gap-x-6 gap-y-8 lg:grid-cols-3">
          <div className="flex flex-col gap-1">
            <p className="text-sm text-muted-foreground">Your open deals</p>
            <p className="text-3xl font-normal tracking-tight tabular-nums">{open.length}</p>
            <p className="text-xs text-muted-foreground">{value > 0 ? `About ${compact.format(value)}, ` : ""}{n(won, "won", "won")} in the last 30 days</p>
            <Link href="/deals" className="mt-auto self-start pt-2 text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">Open your deals</Link>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-sm text-muted-foreground">Your first replies</p>
            <p className="text-3xl font-normal tracking-tight tabular-nums">{mine ? duration(mine.median_first_response_seconds) : "—"}</p>
            <p className="text-xs text-muted-foreground">{mine ? `Median wait, over ${n(mine.first_replies, "reply", "replies")} where you answered first` : "You didn't answer a waiting customer first in this period"}</p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-sm text-muted-foreground">Your call-backs</p>
            <p className="text-3xl font-normal tracking-tight tabular-nums">{calls ? duration(calls.median_callback_seconds) : "—"}</p>
            <p className="text-xs text-muted-foreground">{calls ? `Median from the first ring, ${n(calls.callbacks, "caller")} rung back` : "No missed callers rung back by you in this period"}</p>
          </div>
        </div>
      )}
    </section>
  )
}

const compact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 })

/* ------------------------------------------------------------ page */

export default function TodayPage() {
  const { me } = useAuth()
  const [days, setDays] = useState(7)
  const [tracing, setTracing] = useState<string | null>(null)
  const today = useQuery({ queryKey: ["today"], queryFn: () => api<Today>("/today"), refetchInterval: 60_000 })
  const report = useQuery({ queryKey: ["analytics", days], queryFn: () => api<Report>(`/analytics?days=${days}`), placeholderData: keepPreviousData })
  const t = today.data
  const tz = t?.timezone ?? report.data?.timezone ?? "America/Chicago"
  const everyone = t ? t.needs.scope === "everyone" : me?.role === "admin" || me?.role === "manager"

  return (
    <>
      <SiteHeader title="Today" />
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-8 lg:px-8 lg:py-10">
        <Handover first={me?.name.split(" ")[0]} count={t ? needCount(t.needs) : null} everyone={everyone} t={t} tz={tz} />
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_18rem] xl:grid-cols-[minmax(0,1fr)_20rem] xl:gap-14">
          <Needs q={today} tz={tz} />
          <Agenda q={today} tz={tz} everyone={everyone} />
        </div>
        {everyone ? (
          <DealershipWeek r={report.data} report={report} days={days} setDays={setDays} team={t?.team ?? []} trace={setTracing} />
        ) : (
          <YourWeek r={report.data} report={report} days={days} setDays={setDays} meId={me?.id} />
        )}
      </div>
      <TraceSheet metric={tracing} days={days} tz={tz} onClose={() => setTracing(null)} />
    </>
  )
}

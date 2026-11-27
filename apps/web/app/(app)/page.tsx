"use client"

/**
 * Today. One job: the owner at 7am sees what needs them, then how last night went, then today's bookings, then how
 * the week is going. Every number comes from the dealership's own events, and each one opens the list behind it.
 * Blue is Ondra's work and nothing else; red is a VIP or something overdue.
 */

import { IconAlertTriangle, IconPhoneX } from "@tabler/icons-react"
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

const CHANNEL: Record<string, string> = { sms: "Text", whatsapp: "WhatsApp", email: "Email", phone: "Calls", owner: "Added by the owner", unknown: "Not recorded" }
const STAGE: Record<string, string> = { new: "New", qualified: "Qualified", appointment: "Appointment", negotiating: "Negotiating", won: "Won", lost: "Lost" }
const chartConfig = { responses_by_ai: { label: "Ondra", color: "var(--chart-1)" }, responses_by_team: { label: "Your team", color: "var(--chart-staff)" } } satisfies ChartConfig

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"
}

/** "41 s", "3 min 05 s", "1 h 12 min". A dash when there's nothing to measure. */
function duration(seconds: number | null | undefined) {
  if (seconds == null) return "—"
  const s = Math.round(seconds)
  if (s < 60) return `${s} s`
  if (s < 3600) return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`
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

function SplitBar({ ondra, team }: { ondra: number; team: number }) {
  const sum = ondra + team
  return (
    <div className="mt-3 flex flex-col gap-2">
      <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full" role="img" aria-label={`${ondra} by Ondra, ${team} by your team`}>
        {sum === 0 ? <div className="w-full bg-muted" /> : (
          <>
            {ondra > 0 && <div className="bg-ai" style={{ width: `${(ondra / sum) * 100}%` }} />}
            {team > 0 && <div className="bg-chart-staff" style={{ width: `${(team / sum) * 100}%` }} />}
          </>
        )}
      </div>
      <div className="flex gap-4 text-xs tabular-nums">
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-[2px] bg-ai" aria-hidden="true" /><span className="text-muted-foreground">Ondra</span> {ondra}</span>
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-[2px] bg-chart-staff" aria-hidden="true" /><span className="text-muted-foreground">Your team</span> {team}</span>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ what's behind a number */

function describe(e: Trace["events"][number]) {
  const d = e.detail
  if (e.type === "callback.first_try") {
    const rang = typeof d.rings === "number" && d.rings > 1 ? `Rang ${d.rings} times. ` : ""
    const did = d.result === "reached" ? "Spoke to them" : d.result === "no_answer" ? "Called, no answer," : d.result === "short" ? "A short call, likely voicemail," : "Left a message"
    return { by: typeof d.by === "string" ? d.by : null, text: `${rang}${did} ${duration(Number(d.seconds))} after the first ring, counting open hours` }
  }
  const by = d.by === "ai" || d.source === "ai" || d.handled_by === "ai" ? "Ondra" : d.by === "user" || d.source === "staff" || d.handled_by === "staff" ? "your team"
    : d.by === "owner" || d.handled_by === "owner" ? "the owner" : d.handled_by === "missed" ? "nobody (missed)" : null
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
    <div className="relative flex flex-col gap-1 bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-semibold tabular-nums">{value}</p>
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

/* ------------------------------------------------------------ calling back missed callers */

/** How fast missed callers get a call back: from the first ring to the first try (a voicemail counts; reaching them
 * is up to them), counted only while the dealership is open. Per person for owners and managers. */
function CallBacks({ r, everyone, onOpen }: { r: Report; everyone: boolean; onOpen: () => void }) {
  const t = r.totals
  if (t.calls_missed === 0 && t.callbacks === 0) {
    return (
      <div className="rounded-xl border p-5">
        <h3 className="font-medium">Calling back missed calls</h3>
        <p className="mt-1 text-sm text-muted-foreground">No missed calls in the last {r.days} days.</p>
      </div>
    )
  }
  return (
    <div className="grid overflow-hidden rounded-xl border md:grid-cols-[18rem_minmax(0,1fr)]">
      <div className="border-b md:border-r md:border-b-0">
        <Tile label="Time to call back" value={duration(t.median_callback_seconds)} onOpen={onOpen}
          context={<span className="text-muted-foreground">Median, from the first ring to the first try, counted while you&apos;re open</span>}
          delta={<Delta now={t.median_callback_seconds} before={r.previous.median_callback_seconds} days={r.days} lowerIsBetter />} />
      </div>
      <div className="p-5">
        <h3 className="font-medium">Calling back missed calls</h3>
        <p className="mb-4 text-sm text-muted-foreground">
          {n(t.calls_missed, "missed call")} in the last {r.days} days. {n(t.callbacks, "caller")} rung back; someone who rang three times counts once.
        </p>
        {everyone && r.callback_people.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr><th className="pb-2 font-normal">Who</th><th className="pb-2 text-right font-normal">Rung back</th><th className="pb-2 text-right font-normal">Median wait</th></tr>
            </thead>
            <tbody className="divide-y">
              {r.callback_people.map((p) => (
                <tr key={p.user_id}>
                  <td className="py-2">{p.name}</td>
                  <td className="py-2 text-right tabular-nums">{p.callbacks}</td>
                  <td className="py-2 text-right tabular-nums">{duration(p.median_callback_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ page */

export default function TodayPage() {
  const { me } = useAuth()
  const first = me?.name.split(" ")[0]
  const [days, setDays] = useState(7)
  const [tracing, setTracing] = useState<string | null>(null)
  const today = useQuery({ queryKey: ["today"], queryFn: () => api<Today>("/today"), refetchInterval: 60_000 })
  const report = useQuery({ queryKey: ["analytics", days], queryFn: () => api<Report>(`/analytics?days=${days}`), placeholderData: keepPreviousData })
  const t = today.data
  const r = report.data
  const tz = t?.timezone ?? r?.timezone ?? "America/Chicago"
  const needs = t?.needs
  const needCount = needs ? needs.vips.length + (needs.drafts > 0 ? 1 : 0) + (needs.overdue_count > 0 ? 1 : 0) + needs.hot.length + (needs.callbacks.count > 0 ? 1 : 0) : 0

  return (
    <>
      <SiteHeader title="Today" />
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-6 lg:px-6 lg:py-8">
        <p className="text-2xl font-medium tracking-tight">{greeting()}{first ? `, ${first}` : ""}.</p>

        {/* 1. What needs you */}
        <section aria-labelledby="needs">
          <h2 id="needs" className="text-sm font-medium text-muted-foreground">
            {needs?.scope === "mine" ? "Needs you" : "Needs someone"} {needs && <span className="tabular-nums">{needCount}</span>}
          </h2>
          {today.isPending ? <Skeleton className="mt-3 h-36 w-full rounded-xl" /> : today.isError ? (
            <div className="mt-3"><LoadError message={today.error.message} onRetry={() => today.refetch()} /></div>
          ) : needCount === 0 ? (
            <p className="mt-3 rounded-xl border p-5 text-sm text-muted-foreground">Nothing is waiting. VIPs, drafts to approve, missed callers and overdue tasks show here the moment there are any.</p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border">
              {needs!.vips.map((v) => (
                <li key={v.task_id} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 sm:flex-nowrap" data-vip>
                  <ClientAvatar name={v.client ?? ""} vip />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{v.client} is waiting</p>
                    <p className="text-sm text-muted-foreground">{v.title.replace(`${v.client}: `, "")}, since {v.since ? clock(v.since, tz) : "earlier"}.</p>
                  </div>
                  <Button asChild size="sm" className="ml-auto"><Link href={v.conversation_id ? `/inbox?c=${v.conversation_id}` : "/tasks"}>Reply yourself</Link></Button>
                </li>
              ))}
              {needs!.drafts > 0 && (
                <li className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 sm:flex-nowrap">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ai-subtle text-ai" aria-hidden="true"><OndraMark className="size-4" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{n(needs!.drafts, "reply", "replies")} to approve</p>
                    <p className="text-sm text-muted-foreground">Ondra wrote {needs!.drafts === 1 ? "it" : "them"} and is waiting for a person to send {needs!.drafts === 1 ? "it" : "them"}.</p>
                  </div>
                  <Button asChild variant="outline" size="sm" className="ml-auto"><Link href="/inbox">Review</Link></Button>
                </li>
              )}
              {needs!.callbacks.count > 0 && (
                <li className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 sm:flex-nowrap">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground" aria-hidden="true"><IconPhoneX className="size-4" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {n(needs!.callbacks.count, "caller")} waiting for a call back
                      {needs!.callbacks.overdue > 0 && <span className="text-overdue">, {needs!.callbacks.overdue} overdue</span>}
                    </p>
                    {needs!.callbacks.oldest && (
                      <p className="truncate text-sm text-muted-foreground">
                        {needs!.callbacks.count > 1 ? "Longest: " : ""}{needs!.callbacks.oldest.client}, since {since(needs!.callbacks.oldest.since, tz)}.
                      </p>
                    )}
                  </div>
                  <Button asChild variant="outline" size="sm" className="ml-auto"><Link href="/calls?show=missed">Call back</Link></Button>
                </li>
              )}
              {needs!.overdue_count > 0 && (
                <li className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 sm:flex-nowrap">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground" aria-hidden="true"><IconAlertTriangle className="size-4" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-overdue">{n(needs!.overdue_count, "task")} overdue</p>
                    <p className="truncate text-sm text-muted-foreground">{needs!.overdue.slice(0, 2).map((o) => o.title).join(". ")}{needs!.overdue_count > 2 ? ", and more" : ""}.</p>
                  </div>
                  <Button asChild variant="outline" size="sm" className="ml-auto"><Link href="/tasks">Open tasks</Link></Button>
                </li>
              )}
              {needs!.hot.map((h) => (
                <li key={h.task_id} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 sm:flex-nowrap">
                  <span className="size-9 shrink-0" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{h.title}</p>
                    <p className="text-sm text-muted-foreground">Marked urgent{h.due_at ? `, due ${clock(h.due_at, tz)}` : ""}.</p>
                  </div>
                  <Button asChild variant="outline" size="sm" className="ml-auto"><Link href={h.conversation_id ? `/inbox?c=${h.conversation_id}` : "/tasks"}>Open</Link></Button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 2. Last night */}
        {t?.overnight && (
          <section aria-labelledby="overnight">
            <h2 id="overnight" className="text-sm font-medium text-muted-foreground">While you were closed, {clock(t.overnight.from, tz)} to {clock(t.overnight.to, tz)}</h2>
            <div className="mt-3 grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-3">
              <div className="bg-card p-5">
                <p className="text-sm text-muted-foreground">Customers answered</p>
                <p className="mt-1 text-3xl font-semibold tabular-nums">{t.overnight.responses_by_ai + t.overnight.responses_by_team}</p>
                <SplitBar ondra={t.overnight.responses_by_ai} team={t.overnight.responses_by_team} />
              </div>
              <div className="bg-card p-5">
                <p className="text-sm text-muted-foreground">Test drives and service booked</p>
                <p className="mt-1 text-3xl font-semibold tabular-nums">{t.overnight.appointments_booked}</p>
                {t.overnight.appointments_booked_by_ai > 0 && (
                  <p data-slot="ai-note" className="mt-3 flex items-center gap-1.5 text-xs text-ai"><OndraMark className="size-3.5" /> {t.overnight.appointments_booked_by_ai} booked by Ondra</p>
                )}
              </div>
              <div className="bg-card p-5">
                <p className="text-sm text-muted-foreground">Median first reply</p>
                <p className="mt-1 text-3xl font-semibold tabular-nums">{duration(t.overnight.median_first_response_seconds)}</p>
                <p className="mt-3 text-xs text-muted-foreground">{n(t.overnight.leads, "new lead")}{t.overnight.calls_missed ? `, ${n(t.overnight.calls_missed, "missed call")}` : ""}</p>
              </div>
            </div>
          </section>
        )}

        {/* 3. Today's bookings */}
        <section aria-labelledby="coming-up">
          <h2 id="coming-up" className="text-sm font-medium text-muted-foreground">Booked today {t && <span className="tabular-nums">{t.appointments.length}</span>}</h2>
          {today.isPending ? <Skeleton className="mt-3 h-24 w-full rounded-xl" /> : !t || t.appointments.length === 0 ? (
            <p className="mt-3 rounded-xl border p-5 text-sm text-muted-foreground">No appointments today. Test drives and service bookings for today show here.</p>
          ) : (
            <ul className="mt-3 divide-y rounded-xl border">
              {t.appointments.map((a) => (
                <li key={a.id} data-vip={a.vip || undefined} className="relative grid grid-cols-[4.5rem_minmax(0,1fr)] items-baseline gap-x-4 gap-y-0.5 px-4 py-3 sm:grid-cols-[5rem_minmax(0,1fr)_auto]">
                  <span className="text-sm font-medium tabular-nums">{clock(a.starts_at, tz)}</span>
                  <span className="min-w-0">
                    <span className="block truncate">{a.kind}</span>
                    <span className="block truncate text-sm text-muted-foreground">{a.client}{a.with ? `, with ${a.with}` : ""}</span>
                  </span>
                  {a.by_ondra && !a.vip && (
                    <span data-slot="ai-note" className="col-start-2 flex items-center gap-1.5 text-sm text-ai sm:col-start-3"><OndraMark className="size-3.5" /> Booked by Ondra</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 4. How it's going */}
        <section aria-labelledby="period" className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="period" className="text-sm font-medium text-muted-foreground">The last {days} days</h2>
            <ToggleGroup type="single" variant="outline" size="sm" value={String(days)} onValueChange={(v) => v && setDays(Number(v))} aria-label="Period">
              <ToggleGroupItem value="7" className="px-3">7 days</ToggleGroupItem>
              <ToggleGroupItem value="30" className="px-3">30 days</ToggleGroupItem>
            </ToggleGroup>
          </div>
          {report.isPending ? <Skeleton className="h-72 w-full rounded-xl" /> : report.isError ? (
            <LoadError message={report.error.message} onRetry={() => report.refetch()} />
          ) : r && (
            <div className={cn("flex flex-col gap-4", report.isFetching && "opacity-60")} aria-busy={report.isFetching || undefined}>
              <div className="grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-2 lg:grid-cols-4">
                <Tile label="Leads captured" value={String(r.totals.leads)} onOpen={() => setTracing("leads")}
                  delta={<Delta now={r.totals.leads} before={r.previous.leads} days={r.days} />}
                  context={<span><span data-slot="ai-note" className="text-ai">{r.totals.leads_by_ai} by Ondra</span><span className="text-muted-foreground">, {r.totals.leads_after_hours} after hours</span></span>} />
                <Tile label="Median first reply" value={duration(r.totals.median_first_response_seconds)} onOpen={() => setTracing("responses")}
                  delta={<Delta now={r.totals.median_first_response_seconds} before={r.previous.median_first_response_seconds} days={r.days} lowerIsBetter />}
                  context={r.totals.median_first_response_seconds_ai != null ? <span data-slot="ai-note" className="text-ai">Ondra&apos;s own: {duration(r.totals.median_first_response_seconds_ai)}</span> : undefined} />
                <Tile label="Appointments booked" value={String(r.totals.appointments_booked)} onOpen={() => setTracing("appointments_booked")}
                  delta={<Delta now={r.totals.appointments_booked} before={r.previous.appointments_booked} days={r.days} />}
                  context={<span><span data-slot="ai-note" className="text-ai">{r.totals.appointments_booked_by_ai} by Ondra</span><span className="text-muted-foreground">, {r.totals.appointments_showed} showed, {r.totals.appointments_no_show} didn&apos;t</span></span>} />
                <Tile label="Follow-ups sent" value={String(r.totals.follow_ups_sent)} onOpen={() => setTracing("follow_ups_sent")}
                  delta={<Delta now={r.totals.follow_ups_sent} before={r.previous.follow_ups_sent} days={r.days} />} />
              </div>

              <div className="rounded-xl border p-5">
                <h3 className="font-medium">Who answered first</h3>
                <p className="mb-4 text-sm text-muted-foreground">Each time a customer wrote in and was waiting, who gave the first reply.</p>
                <RepliesChart r={r} />
              </div>

              {r.people.length > 0 && (needs?.scope === "everyone") && (
                <div className="rounded-xl border p-5">
                  <h3 className="font-medium">Your team&apos;s first replies</h3>
                  <p className="mb-4 text-sm text-muted-foreground">When a person, not Ondra, answered a waiting customer first.</p>
                  <table className="w-full text-sm">
                    <thead className="text-left text-muted-foreground">
                      <tr><th className="pb-2 font-normal">Who</th><th className="pb-2 text-right font-normal">First replies</th><th className="pb-2 text-right font-normal">Median wait</th></tr>
                    </thead>
                    <tbody className="divide-y">
                      {r.people.map((p) => (
                        <tr key={p.user_id}>
                          <td className="py-2">{p.name}</td>
                          <td className="py-2 text-right tabular-nums">{p.first_replies}</td>
                          <td className="py-2 text-right tabular-nums">{duration(p.median_first_response_seconds)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <CallBacks r={r} everyone={needs?.scope === "everyone"} onOpen={() => setTracing("callbacks")} />

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border p-5">
                  <h3 className="font-medium">Leads by channel</h3>
                  <p className="mb-4 text-sm text-muted-foreground">Where the {n(r.totals.leads, "lead")} came in.</p>
                  <BarList empty="No leads in this period." rows={Object.entries(r.totals.leads_by_channel).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ key: k, label: CHANNEL[k] ?? k, value: v }))} />
                </div>
                <div className="rounded-xl border p-5">
                  <h3 className="font-medium">Deals in play now</h3>
                  <p className="mb-4 text-sm text-muted-foreground">
                    {n(r.pipeline.in_play, "open deal")}{r.pipeline.in_play > 0 && <>, <span data-slot="ai-note" className="text-ai">{r.pipeline.in_play_by_ai} that Ondra brought in</span></>}. Not limited to the last {r.days} days.
                  </p>
                  <BarList empty="No deals yet. A deal starts when Ondra or your team records what a buyer wants." rows={Object.entries(r.pipeline.by_stage).map(([k, v]) => ({ key: k, label: STAGE[k] ?? k, value: v }))} />
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
      <TraceSheet metric={tracing} days={days} tz={tz} onClose={() => setTracing(null)} />
    </>
  )
}

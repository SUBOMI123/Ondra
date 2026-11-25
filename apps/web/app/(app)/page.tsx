"use client"

/**
 * Today. One job: the owner at 7am sees what needs them, then how last night went, then today's bookings.
 * Trends sit last; nothing here duplicates the Inbox or Deals.
 */

import { IconAlertTriangle, IconCrownFilled } from "@tabler/icons-react"
import Link from "next/link"

import { ChartAreaInteractive } from "@/components/dashboard/chart-area-interactive"
import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { useAuth } from "@/components/providers"
import { Button } from "@/components/ui/button"
import { NEEDS_YOU, OVERNIGHT, TODAY_APPOINTMENTS } from "@/lib/examples"
import { cn } from "@/lib/utils"

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"
}

function SplitBar({ ondra, team }: { ondra: number; team: number }) {
  const pct = (ondra / (ondra + team)) * 100
  return (
    <div className="mt-3 flex flex-col gap-2">
      <div className="flex h-1.5 overflow-hidden rounded-full bg-muted" role="img" aria-label={`${ondra} by Ondra, ${team} by your team`}>
        <div className="bg-ai" style={{ width: `${pct}%` }} />
        <div className="bg-chart-2/60" style={{ width: `${100 - pct}%` }} />
      </div>
      <div className="flex gap-4 text-xs tabular-nums">
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-[2px] bg-ai" aria-hidden="true" />
          <span className="text-muted-foreground">Ondra</span> {ondra}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-[2px] bg-chart-2/60" aria-hidden="true" />
          <span className="text-muted-foreground">Your team</span> {team}
        </span>
      </div>
    </div>
  )
}

export default function TodayPage() {
  const { me } = useAuth()
  const first = me?.name.split(" ")[0]
  return (
    <>
      <SiteHeader title="Today" note="Example data until conversations are live" />
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-6 lg:px-6 lg:py-8">
        <p className="text-2xl font-medium tracking-tight">
          {greeting()}
          {first ? `, ${first}` : ""}.
        </p>

        {/* 1. What needs you */}
        <section aria-labelledby="needs">
          <h2 id="needs" className="text-sm font-medium text-muted-foreground">
            Needs you <span className="tabular-nums">{NEEDS_YOU.length}</span>
          </h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {NEEDS_YOU.map((n) => (
              <li key={n.title} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 sm:flex-nowrap" data-vip={n.kind === "vip" || undefined}>
                <span
                  className={cn(
                    "flex size-9 shrink-0 items-center justify-center rounded-full",
                    n.kind === "vip" ? "bg-vip-subtle text-vip" : n.kind === "drafts" ? "bg-ai-subtle text-ai" : "bg-muted text-muted-foreground",
                  )}
                  aria-hidden="true"
                >
                  {n.kind === "vip" ? <IconCrownFilled className="size-4" /> : n.kind === "drafts" ? <OndraMark className="size-4" /> : <IconAlertTriangle className="size-4" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={cn("font-medium", n.kind === "overdue" && "text-vip")}>{n.title}</p>
                  <p className="text-sm text-muted-foreground">{n.detail}</p>
                </div>
                <Button asChild variant={n.kind === "vip" ? "default" : "outline"} size="sm" className="ml-auto">
                  <Link href={n.href}>{n.action}</Link>
                </Button>
              </li>
            ))}
          </ul>
        </section>

        {/* 2. Last night */}
        <section aria-labelledby="overnight">
          <h2 id="overnight" className="text-sm font-medium text-muted-foreground">
            While you were away, {OVERNIGHT.from} to {OVERNIGHT.to}
          </h2>
          <div className="mt-3 grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-3">
            <div className="bg-card p-5">
              <p className="text-sm text-muted-foreground">Leads answered</p>
              <p className="mt-1 text-3xl font-semibold tabular-nums">{OVERNIGHT.answered.ondra + OVERNIGHT.answered.team}</p>
              <SplitBar {...OVERNIGHT.answered} />
            </div>
            <div className="bg-card p-5">
              <p className="text-sm text-muted-foreground">Test drives and service booked</p>
              <p className="mt-1 text-3xl font-semibold tabular-nums">{OVERNIGHT.booked}</p>
              <p className="mt-3 flex items-center gap-1.5 text-xs text-ai">
                <OndraMark className="size-3.5" /> All booked by Ondra
              </p>
            </div>
            <div className="bg-card p-5">
              <p className="text-sm text-muted-foreground">Median first reply</p>
              <p className="mt-1 text-3xl font-semibold tabular-nums">{OVERNIGHT.medianReply}</p>
              <p className="mt-3 text-xs text-muted-foreground">Calls, texts, email and WhatsApp</p>
            </div>
          </div>
        </section>

        {/* 3. Today's bookings */}
        <section aria-labelledby="coming-up">
          <h2 id="coming-up" className="text-sm font-medium text-muted-foreground">
            Booked today <span className="tabular-nums">{TODAY_APPOINTMENTS.length}</span>
          </h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {TODAY_APPOINTMENTS.map((a) => (
              <li key={a.time + a.client} className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-baseline gap-x-4 gap-y-0.5 px-4 py-3 sm:grid-cols-[5rem_minmax(0,1fr)_auto]">
                <span className="text-sm font-medium tabular-nums">{a.time}</span>
                <span className="min-w-0">
                  <span className="block truncate">{a.title}</span>
                  <span className="block truncate text-sm text-muted-foreground">
                    {a.client}, with {a.who}
                  </span>
                </span>
                <span className="col-start-2 flex items-center gap-2 text-sm text-muted-foreground sm:col-start-3">
                  {a.where}
                  {a.byOndra && <OndraMark className="size-3.5 text-ai" />}
                  {a.byOndra && <span className="sr-only">Booked by Ondra</span>}
                </span>
              </li>
            ))}
          </ul>
        </section>

        {/* 4. Trend, last */}
        <ChartAreaInteractive />
      </div>
    </>
  )
}

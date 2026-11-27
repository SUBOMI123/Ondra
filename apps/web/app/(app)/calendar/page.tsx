"use client"

/**
 * Calendar. One job: who is where, when, at a glance, and record what happened.
 * Desktop: a day grid with a lane per salesperson and per service bay, and a line at the current time.
 * Phone: the same day as a time-ordered agenda, because narrow lanes don't read on a phone.
 * Ondra's bookings carry its mark (not a blue fill, so the grid stays calm); VIPs carry the crown.
 * Data: GET /calendar?date=; status changes PATCH /appointments/{id}; live updates refresh it.
 */

import { IconChevronLeft, IconChevronRight, IconMessage } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { api, send } from "@/lib/api"
import { useLiveInbox } from "@/lib/live"
import { cn } from "@/lib/utils"
import { VipTag } from "@/components/vip"

const START = 7
const END = 20
const HOUR = 56 // px per hour

type Lane = { id: string; name: string; group: "Sales" | "Service"; kind: "person" | "bay" }
type Appt = {
  id: string
  starts_at: string
  ends_at: string
  status: "booked" | "confirmed" | "showed" | "no_show" | "cancelled"
  source: "ai" | "staff" | "customer_link"
  title: string
  category: string | null
  client: { id: string; name: string; is_vip: boolean } | null
  with: string | null
  bays: string[]
  lane_ids: string[]
  details: { loaner?: string | null; loaner_note?: string; transport?: string; service_type?: string; vehicle?: string; notes?: string }
  conversation_id: string | null
}
type Day = { date: string; timezone: string; lanes: Lane[]; appointments: Appt[] }

const STATUS: Record<Appt["status"], string> = {
  booked: "Booked", confirmed: "Confirmed", showed: "Showed up", no_show: "No-show", cancelled: "Cancelled",
}

function isoDay(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

/** Hours since midnight, in the dealer's time zone. */
function hourIn(iso: string, tz: string) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", minute: "numeric", hourCycle: "h23" }).formatToParts(new Date(iso))
  const h = Number(parts.find((p) => p.type === "hour")?.value ?? 0)
  const m = Number(parts.find((p) => p.type === "minute")?.value ?? 0)
  return h + m / 60
}

function clock(iso: string, tz: string) {
  return new Date(iso).toLocaleTimeString("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit" }).toLowerCase()
}

function fmtHour(h: number) {
  const ampm = h >= 12 ? "pm" : "am"
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12} ${ampm}`
}

function Block({ a, tz, onOpen }: { a: Appt; tz: string; onOpen: () => void }) {
  const start = hourIn(a.starts_at, tz)
  const end = hourIn(a.ends_at, tz)
  const short = end - start <= 0.5
  const vip = a.client?.is_vip
  const done = a.status === "showed" || a.status === "no_show"
  return (
    <button
      type="button"
      onClick={onOpen}
      data-vip={vip || undefined}
      className={cn(
        "absolute inset-x-1 overflow-hidden rounded-md border bg-card px-2 py-1 text-left text-xs shadow-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
        vip && "border-vip/40",
        done && "opacity-60",
      )}
      style={{ top: (start - START) * HOUR + 1, height: Math.max((end - start) * HOUR - 2, 22) }}
      aria-label={`${a.title}${a.client ? ` with ${a.client.name}` : ""}, ${clock(a.starts_at, tz)} to ${clock(a.ends_at, tz)}${a.source === "ai" ? ", booked by Ondra" : ""}, ${STATUS[a.status]}`}
    >
      <span className="flex items-center gap-1 font-medium">
        {vip && <VipTag />}
        <span className="truncate">{a.client?.name ?? a.title}</span>
        {a.source === "ai" && <OndraMark className="ml-auto size-3 shrink-0 text-ai" />}
      </span>
      {!short && (
        <span className="block truncate text-muted-foreground">
          {a.client ? a.title : ""}
          {a.status === "no_show" ? ", no-show" : ""}
        </span>
      )}
    </button>
  )
}

function Details({ a, tz, onClose }: { a: Appt; tz: string; onClose: () => void }) {
  const qc = useQueryClient()
  const set = useMutation({
    mutationFn: (status: Appt["status"]) => send("PATCH", `/appointments/${a.id}`, { status }),
    onSuccess: (_, status) => {
      qc.invalidateQueries({ queryKey: ["calendar"] })
      toast(status === "cancelled" ? "Appointment cancelled" : `Marked ${STATUS[status].toLowerCase()}`)
      if (status === "cancelled") onClose()
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't update it."),
  })
  const started = new Date(a.starts_at) <= new Date()
  const live = a.status === "booked" || a.status === "confirmed"
  const transport = a.details.transport === "loaner"
    ? a.details.loaner ? `Loaner: ${a.details.loaner}` : a.details.loaner_note ?? "Loaner requested"
    : a.details.transport ? { wait: "Waiting at the dealership", shuttle: "Needs the shuttle", drop_off: "Dropping the car off" }[a.details.transport] : null
  return (
    <>
      <SheetHeader>
        <SheetTitle className="flex items-center gap-1.5">
          {a.client?.is_vip && <VipTag />}
          {a.client?.name ?? "Busy"}
        </SheetTitle>
        <SheetDescription>
          {a.title}, {clock(a.starts_at, tz)} to {clock(a.ends_at, tz)}
          {a.with ? `, with ${a.with}` : ""}
          {a.bays.length ? `, ${a.bays.join(", ")}` : ""}
        </SheetDescription>
      </SheetHeader>
      <div className="flex flex-col gap-4 px-4 text-sm">
        <p className={cn("flex items-center gap-1.5", a.source === "ai" ? "text-ai" : "text-muted-foreground")}>
          {a.source === "ai" ? (
            <>
              <OndraMark className="size-4" /> Booked by Ondra
            </>
          ) : (
            "Booked by your team"
          )}
        </p>
        <dl className="grid gap-1.5">
          <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2"><dt className="text-muted-foreground">Status</dt><dd>{STATUS[a.status]}</dd></div>
          {a.details.vehicle && <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2"><dt className="text-muted-foreground">Vehicle</dt><dd>{a.details.vehicle}</dd></div>}
          {a.details.service_type && <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2"><dt className="text-muted-foreground">For</dt><dd>{a.details.service_type}</dd></div>}
          {transport && <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2"><dt className="text-muted-foreground">Transport</dt><dd>{transport}</dd></div>}
          {a.details.notes && <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2"><dt className="text-muted-foreground">Notes</dt><dd>{a.details.notes}</dd></div>}
        </dl>
        {a.client && (
          <div className="flex flex-wrap gap-2">
            {live && started && (
              <>
                <Button size="sm" disabled={set.isPending} onClick={() => set.mutate("showed")}>Showed up</Button>
                <Button size="sm" variant="outline" disabled={set.isPending} onClick={() => set.mutate("no_show")}>No-show</Button>
              </>
            )}
            {a.conversation_id && (
              <Button size="sm" variant="outline" asChild>
                <Link href={`/inbox?c=${a.conversation_id}`}><IconMessage /> Conversation</Link>
              </Button>
            )}
            {live && (
              <Button size="sm" variant="ghost" disabled={set.isPending} onClick={() => set.mutate("cancelled")}>Cancel appointment</Button>
            )}
          </div>
        )}
      </div>
    </>
  )
}

export default function CalendarPage() {
  useLiveInbox()
  const [offset, setOffset] = useState(0) // days from today
  const [openId, setOpenId] = useState<string | null>(null)
  const [now, setNow] = useState<number | null>(null)

  const date = useMemo(() => {
    const d = new Date()
    d.setDate(d.getDate() + offset)
    return d
  }, [offset])
  const q = useQuery({ queryKey: ["calendar", isoDay(date)], queryFn: () => api<Day>(`/calendar?date=${isoDay(date)}`) })
  const tz = q.data?.timezone ?? "America/Chicago"
  useEffect(() => {
    setNow(hourIn(new Date().toISOString(), tz))
  }, [tz])

  const label = date.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
  const appts = q.data?.appointments ?? []
  const lanes = q.data?.lanes ?? []
  const groups = (["Sales", "Service"] as const).map((g) => ({ g, lanes: lanes.filter((l) => l.group === g) })).filter((x) => x.lanes.length)
  const open = appts.find((a) => a.id === openId) ?? null
  const laneName = (a: Appt) => lanes.find((l) => a.lane_ids.includes(l.id))?.name ?? a.with ?? ""

  return (
    <>
      <SiteHeader title="Calendar" />
      <div className="flex flex-col gap-4 px-4 py-6 lg:px-6">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => setOffset((o) => o - 1)} aria-label="Previous day">
            <IconChevronLeft />
          </Button>
          <Button variant="outline" size="icon" onClick={() => setOffset((o) => o + 1)} aria-label="Next day">
            <IconChevronRight />
          </Button>
          {offset !== 0 && (
            <Button variant="ghost" size="sm" onClick={() => setOffset(0)}>
              Today
            </Button>
          )}
          <h2 className="ml-1 text-lg font-medium">
            {offset === 0 ? "Today, " : ""}
            {label}
          </h2>
          <span className="ml-auto text-sm text-muted-foreground tabular-nums">
            {q.data ? `${appts.filter((a) => a.status !== "cancelled").length} booked` : ""}
          </span>
        </div>

        {q.isPending ? (
          <Skeleton className="h-96 w-full rounded-xl" />
        ) : q.isError ? (
          <div className="space-y-3 rounded-xl border p-6 text-sm" role="alert">
            <p>The calendar didn&apos;t load. {q.error instanceof Error ? q.error.message : ""}</p>
            <Button variant="outline" onClick={() => q.refetch()}>Try again</Button>
          </div>
        ) : appts.length === 0 ? (
          <p className="rounded-xl border p-6 text-sm text-muted-foreground">
            Nothing booked. Ondra books test drives and service here as customers ask for them.
          </p>
        ) : (
          <>
            {/* Phone: agenda */}
            <ul className="divide-y rounded-xl border md:hidden">
              {appts.map((a) => (
                <li key={a.id}>
                  <button type="button" onClick={() => setOpenId(a.id)} className="grid w-full grid-cols-[4.5rem_minmax(0,1fr)] gap-3 px-4 py-3 text-left" data-vip={a.client?.is_vip || undefined}>
                    <span className="text-sm font-medium tabular-nums">{clock(a.starts_at, tz)}</span>
                    <span className="min-w-0">
                      <span className="flex items-center gap-1.5">
                        {a.client?.is_vip && <VipTag />}
                        <span className="truncate font-medium">{a.client?.name ?? a.title}</span>
                        {a.source === "ai" && <OndraMark className="size-3.5 shrink-0 text-ai" />}
                      </span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {a.client ? `${a.title}, ` : ""}
                        {laneName(a)}
                        {a.status === "no_show" ? ", no-show" : a.status === "showed" ? ", showed up" : ""}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>

            {/* Desktop: day grid */}
            <div className="hidden overflow-x-auto rounded-xl border md:block">
              <div className="grid min-w-[44rem]" style={{ gridTemplateColumns: `3.5rem repeat(${lanes.length}, minmax(0, 1fr))` }}>
                <div className="border-b" />
                {groups.map(({ g, lanes: ls }) => (
                  <div key={g} className="border-b border-l px-2 pt-2 text-xs text-muted-foreground" style={{ gridColumn: `span ${ls.length}` }}>
                    {g}
                    <div className="mt-1 grid" style={{ gridTemplateColumns: `repeat(${ls.length}, minmax(0, 1fr))` }}>
                      {ls.map((l) => (
                        <span key={l.id} className="truncate pb-2 text-sm font-medium text-foreground">
                          {l.name}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}

                {/* time gutter */}
                <div className="relative" style={{ height: (END - START) * HOUR }}>
                  {Array.from({ length: END - START }, (_, i) => (
                    <span key={i} className="absolute right-2 -translate-y-1/2 text-xs text-muted-foreground tabular-nums" style={{ top: i * HOUR }}>
                      {i === 0 ? "" : fmtHour(START + i)}
                    </span>
                  ))}
                </div>
                {groups.flatMap(({ lanes: ls }) => ls).map((l) => (
                  <div
                    key={l.id}
                    className="relative border-l bg-[repeating-linear-gradient(to_bottom,transparent_0,transparent_55px,var(--border)_55px,var(--border)_56px)]"
                    style={{ height: (END - START) * HOUR }}
                  >
                    {appts.filter((a) => a.lane_ids.includes(l.id)).map((a) => (
                      <Block key={a.id} a={a} tz={tz} onOpen={() => setOpenId(a.id)} />
                    ))}
                    {offset === 0 && now !== null && now > START && now < END && (
                      <span className="pointer-events-none absolute inset-x-0 h-px bg-foreground/60" style={{ top: (now - START) * HOUR }} aria-hidden="true" />
                    )}
                  </div>
                ))}
              </div>
            </div>
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <OndraMark className="size-3.5 text-ai" /> Booked by Ondra
            </p>
          </>
        )}
      </div>

      <Sheet open={!!open} onOpenChange={(o) => !o && setOpenId(null)}>
        <SheetContent data-vip={open?.client?.is_vip || undefined}>
          {open && <Details a={open} tz={tz} onClose={() => setOpenId(null)} />}
        </SheetContent>
      </Sheet>
    </>
  )
}

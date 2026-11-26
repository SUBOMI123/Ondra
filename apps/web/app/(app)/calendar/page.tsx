"use client"

/**
 * Calendar. One job: who is where, when, today, at a glance.
 * Desktop: a day grid with a column per salesperson and per service bay, and a line at the current time.
 * Phone: the same day as a time-ordered agenda, because five narrow columns don't read on a phone.
 * Ondra's bookings carry its mark (not a blue fill, so the grid stays calm); VIPs carry the crown.
 */

import { IconChevronLeft, IconChevronRight, IconCrownFilled } from "@tabler/icons-react"
import { useEffect, useMemo, useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { BOOKINGS, LANES, type Booking } from "@/lib/examples"
import { cn } from "@/lib/utils"

const START = 7
const END = 20
const HOUR = 56 // px per hour

function fmt(h: number) {
  const hr = Math.floor(h)
  const min = Math.round((h - hr) * 60)
  const ampm = hr >= 12 ? "pm" : "am"
  const h12 = hr % 12 === 0 ? 12 : hr % 12
  return `${h12}:${String(min).padStart(2, "0")} ${ampm}`
}

function laneName(id: string) {
  return LANES.find((l) => l.id === id)?.name ?? id
}

function BookingBlock({ b, onOpen }: { b: Booking; onOpen: () => void }) {
  const short = b.end - b.start <= 0.5
  return (
    <button
      type="button"
      onClick={onOpen}
      data-vip={b.vip || undefined}
      className={cn(
        "absolute inset-x-1 overflow-hidden rounded-md border bg-card px-2 py-1 text-left text-xs shadow-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
        b.vip && "border-vip/40",
      )}
      style={{ top: (b.start - START) * HOUR + 1, height: (b.end - b.start) * HOUR - 2 }}
      aria-label={`${b.title} with ${b.client}, ${fmt(b.start)} to ${fmt(b.end)}${b.byOndra ? ", booked by Ondra" : ""}`}
    >
      <span className="flex items-center gap-1 font-medium">
        {b.vip && <IconCrownFilled className="size-3 shrink-0 text-vip" aria-hidden="true" />}
        <span className="truncate">{b.client}</span>
        {b.byOndra && <OndraMark className="ml-auto size-3 shrink-0 text-ai" />}
      </span>
      {!short && <span className="block truncate text-muted-foreground">{b.title}</span>}
    </button>
  )
}

export default function CalendarPage() {
  const [offset, setOffset] = useState(0) // days from today
  const [open, setOpen] = useState<Booking | null>(null)
  const [now, setNow] = useState<number | null>(null)
  useEffect(() => {
    const d = new Date()
    setNow(d.getHours() + d.getMinutes() / 60)
  }, [])

  const date = new Date()
  date.setDate(date.getDate() + offset)
  const label = date.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
  const bookings = useMemo(() => (offset === 0 ? BOOKINGS : []), [offset]) // example data covers today only
  const agenda = [...bookings].sort((a, b) => a.start - b.start)
  const groups = ["Sales", "Service"] as const

  return (
    <>
      <SiteHeader title="Calendar" note="Example data until booking goes live in Step 4" />
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
          <span className="ml-auto text-sm text-muted-foreground tabular-nums">{bookings.length} booked</span>
        </div>

        {bookings.length === 0 ? (
          <p className="rounded-xl border p-6 text-sm text-muted-foreground">
            Nothing booked. Ondra books test drives and service here as customers ask for them.
          </p>
        ) : (
          <>
            {/* Phone: agenda */}
            <ul className="divide-y rounded-xl border md:hidden">
              {agenda.map((b) => (
                <li key={b.lane + b.start}>
                  <button type="button" onClick={() => setOpen(b)} className="grid w-full grid-cols-[4.5rem_minmax(0,1fr)] gap-3 px-4 py-3 text-left" data-vip={b.vip || undefined}>
                    <span className="text-sm font-medium tabular-nums">{fmt(b.start)}</span>
                    <span className="min-w-0">
                      <span className="flex items-center gap-1.5">
                        {b.vip && <IconCrownFilled className="size-3.5 shrink-0 text-vip" aria-label="VIP" />}
                        <span className="truncate font-medium">{b.client}</span>
                        {b.byOndra && <OndraMark className="size-3.5 shrink-0 text-ai" />}
                      </span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {b.title}, {laneName(b.lane)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>

            {/* Desktop: day grid */}
            <div className="hidden overflow-x-auto rounded-xl border md:block">
              <div className="grid min-w-[44rem]" style={{ gridTemplateColumns: `3.5rem repeat(${LANES.length}, minmax(0, 1fr))` }}>
                <div className="border-b" />
                {groups.map((g) => {
                  const lanes = LANES.filter((l) => l.group === g)
                  return (
                    <div key={g} className="border-b border-l px-2 pt-2 text-xs text-muted-foreground" style={{ gridColumn: `span ${lanes.length}` }}>
                      {g}
                      <div className="mt-1 grid" style={{ gridTemplateColumns: `repeat(${lanes.length}, minmax(0, 1fr))` }}>
                        {lanes.map((l) => (
                          <span key={l.id} className="pb-2 text-sm font-medium text-foreground">
                            {l.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )
                })}

                {/* time gutter */}
                <div className="relative" style={{ height: (END - START) * HOUR }}>
                  {Array.from({ length: END - START }, (_, i) => (
                    <span key={i} className="absolute right-2 -translate-y-1/2 text-xs text-muted-foreground tabular-nums" style={{ top: i * HOUR }}>
                      {i === 0 ? "" : fmt(START + i).replace(":00", "")}
                    </span>
                  ))}
                </div>
                {LANES.map((l) => (
                  <div
                    key={l.id}
                    className="relative border-l bg-[repeating-linear-gradient(to_bottom,transparent_0,transparent_55px,var(--border)_55px,var(--border)_56px)]"
                    style={{ height: (END - START) * HOUR }}
                  >
                    {bookings
                      .filter((b) => b.lane === l.id)
                      .map((b) => (
                        <BookingBlock key={b.start} b={b} onOpen={() => setOpen(b)} />
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

      <Sheet open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <SheetContent data-vip={open?.vip || undefined}>
          {open && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-1.5">
                  {open.vip && <IconCrownFilled className="size-4 text-vip" aria-label="VIP" />}
                  {open.client}
                </SheetTitle>
                <SheetDescription>
                  {open.title}, {fmt(open.start)} to {fmt(open.end)}, {laneName(open.lane)}
                </SheetDescription>
              </SheetHeader>
              <div className="flex flex-col gap-4 px-4 text-sm">
                {open.detail && <p>{open.detail}</p>}
                <p className={cn("flex items-center gap-1.5", open.byOndra ? "text-ai" : "text-muted-foreground")}>
                  {open.byOndra ? (
                    <>
                      <OndraMark className="size-4" /> Booked by Ondra
                    </>
                  ) : (
                    "Booked by your team"
                  )}
                </p>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}

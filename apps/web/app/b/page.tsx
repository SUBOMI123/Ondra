"use client"

/**
 * A customer's own booking, from the link in their confirmation (/b?t=<token>). No sign-in: the signed link opens this
 * one booking only. One job: see when it is, put it in your calendar, or change it.
 * The dealership is the name here, not Ondra: it's the dealer's customer, booking with the dealer.
 * Data: /public/bookings/{token} (services/confirmations.py, routers/public_booking.py).
 */

import { IconBrandGoogle, IconBrandWindows, IconCalendarPlus, IconMapPin } from "@tabler/icons-react"
import { useSearchParams } from "next/navigation"
import { Suspense, useCallback, useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { API_URL } from "@/lib/api"
import { cn } from "@/lib/utils"

type Booking = {
  dealer: string; address: string | null; phone: string | null; what: string; starts_at: string; ends_at: string; timezone: string
  with: string | null; status: "booked" | "cancelled" | "past"; can_change: boolean
  calendar: { google: string; outlook: string; ics: string }
}
type Time = { slot_id: string; starts_at: string; with: string | null }

const day = (iso: string, tz: string) => new Date(iso).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: tz })
const clock = (iso: string, tz: string) => new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: tz }).toLowerCase()
const zone = (iso: string, tz: string) => new Date(iso).toLocaleTimeString("en-US", { timeZoneName: "short", timeZone: tz }).split(" ").pop()

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } })
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : "That didn't work. Try again, or reply to the message the link came in.")
  return body as T
}

function Times({ token, tz, onMoved }: { token: string; tz: string; onMoved: (b: Booking) => void }) {
  const [times, setTimes] = useState<Time[] | null>(null)
  const [picked, setPicked] = useState<Time | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    call<{ items: Time[] }>(`/public/bookings/${token}/times`).then((r) => setTimes(r.items), (e) => setError(e.message))
  }, [token])
  const days = useMemo(() => {
    const out = new Map<string, Time[]>()
    for (const t of times ?? []) out.set(day(t.starts_at, tz), [...(out.get(day(t.starts_at, tz)) ?? []), t])
    return [...out.entries()]
  }, [times, tz])
  const [chosenDay, setChosenDay] = useState<string | null>(null)
  const shownDay = chosenDay ?? days[0]?.[0] ?? null
  const move = async () => {
    if (!picked) return
    setBusy(true)
    setError(null)
    try {
      onMoved(await call<Booking>(`/public/bookings/${token}/move`, { method: "POST", body: JSON.stringify({ slot_id: picked.slot_id }) }))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }
  if (times === null && !error) return <Skeleton className="h-40 w-full rounded-xl" />
  return (
    <div className="flex flex-col gap-5">
      {days.length === 0 && !error && <p className="text-sm text-muted-foreground">No other times are free in the next two weeks. Reply to the message this link came in and we&apos;ll find one.</p>}
      {days.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium" id="pick-day">Day</p>
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1" role="radiogroup" aria-labelledby="pick-day">
            {days.map(([d]) => {
              const [weekday, date] = d.split(", ")
              return (
                <button key={d} type="button" role="radio" aria-checked={shownDay === d} onClick={() => { setChosenDay(d); setPicked(null) }}
                  className={cn("flex shrink-0 flex-col items-start rounded-xl border px-3 py-2 text-left text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    shownDay === d ? "border-foreground bg-foreground text-background" : "hover:bg-muted")}>
                  <span className="font-medium">{weekday.slice(0, 3)}</span><span className="tabular-nums opacity-80">{date}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}
      {days.filter(([d]) => d === shownDay).map(([d, ts]) => (
        <div key={d} className="flex flex-col gap-2">
          <p className="text-sm font-medium" id="pick-time">Time on {d.split(",")[0]}</p>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-labelledby="pick-time">
            {ts.map((t) => (
              <button key={t.slot_id} type="button" role="radio" aria-checked={picked?.slot_id === t.slot_id} onClick={() => setPicked(t)}
                className={cn("rounded-full border px-3.5 py-1.5 text-sm tabular-nums outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  picked?.slot_id === t.slot_id ? "border-foreground bg-foreground text-background" : "hover:bg-muted")}>
                {clock(t.starts_at, tz)}
              </button>
            ))}
          </div>
        </div>
      ))}
      {error && <p role="alert" className="text-sm">{error}</p>}
      {picked && (
        <Button onClick={move} disabled={busy} className="self-start">
          Move it to {day(picked.starts_at, tz).split(",")[0]} at {clock(picked.starts_at, tz)}
        </Button>
      )}
    </div>
  )
}

function Manage() {
  // Encoded: the token goes into an API path, so a crafted link mustn't be able to point the page at another path.
  const token = encodeURIComponent(useSearchParams().get("t") ?? "")
  const [b, setB] = useState<Booking | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<"view" | "move" | "cancel">("view")
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const load = useCallback(() => {
    if (!token) {
      setError("This link is missing its booking. Open it again from your message.")
      return
    }
    call<Booking>(`/public/bookings/${token}`).then(setB, (e) => setError(e.message))
  }, [token])
  useEffect(() => {
    load()
  }, [load])

  const cancel = async () => {
    setBusy(true)
    try {
      setB(await call<Booking>(`/public/bookings/${token}/cancel`, { method: "POST" }))
      setMode("view")
      setNote("Cancelled. We've sent you a note to say so.")
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
    setBusy(false)
  }

  if (error && !b) {
    return (
      <>
        <h1 className="text-3xl font-normal tracking-[-0.035em] text-balance">We couldn&apos;t find that booking</h1>
        <p className="text-pretty text-muted-foreground">{error}</p>
      </>
    )
  }
  if (!b) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading your booking">
        <h1 className="sr-only">Your booking</h1>
        <Skeleton className="h-5 w-40" /><Skeleton className="h-10 w-72 max-w-full" /><Skeleton className="h-24 w-full rounded-xl" />
      </div>
    )
  }
  const tz = b.timezone
  const cancelled = b.status === "cancelled"
  return (
    <>
      <div className="flex flex-col gap-2">
        <p className="text-sm text-muted-foreground">{b.dealer}</p>
        <h1 className={cn("text-3xl font-normal tracking-[-0.035em] text-balance sm:text-4xl", cancelled && "text-muted-foreground line-through decoration-1")}>
          {b.what}, {day(b.starts_at, tz)}
        </h1>
        <p className="text-xl tabular-nums">
          {clock(b.starts_at, tz)} to {clock(b.ends_at, tz)} <span className="text-sm text-muted-foreground">{zone(b.starts_at, tz)}</span>
          {b.with && <span className="text-muted-foreground">, with {b.with}</span>}
        </p>
        {b.address && <p className="flex items-start gap-1.5 text-sm text-muted-foreground"><IconMapPin className="mt-0.5 size-4 shrink-0" aria-hidden="true" />{b.address}</p>}
      </div>

      {note && <p role="status" className="rounded-lg border px-4 py-3 text-sm">{note}</p>}
      {cancelled ? (
        <p className="text-pretty text-muted-foreground">This booking is cancelled. To book another time, reply to the message this link came in{b.phone ? ` or call ${b.phone}` : ""}.</p>
      ) : b.status === "past" ? (
        <p className="text-muted-foreground">This booking has passed.</p>
      ) : (
        <>
          <section aria-labelledby="add" className="flex flex-col gap-3">
            <h2 id="add" className="text-sm font-medium">Add it to your calendar</h2>
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline"><a href={`${API_URL}${b.calendar.ics}`}><IconCalendarPlus /> Apple Calendar</a></Button>
              <Button asChild variant="outline"><a href={b.calendar.google} target="_blank" rel="noreferrer"><IconBrandGoogle /> Google</a></Button>
              <Button asChild variant="outline"><a href={b.calendar.outlook} target="_blank" rel="noreferrer"><IconBrandWindows /> Outlook</a></Button>
            </div>
          </section>

          {b.can_change && (
            <section aria-labelledby="change" className="flex flex-col gap-4 border-t pt-6">
              <h2 id="change" className="text-sm font-medium">Need to change it?</h2>
              {mode === "view" && (
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => { setNote(null); setMode("move") }}>Choose another time</Button>
                  <Button variant="ghost" onClick={() => { setNote(null); setMode("cancel") }}>Cancel the booking</Button>
                </div>
              )}
              {mode === "move" && (
                <>
                  <Times token={token} tz={tz} onMoved={(nb) => { setB(nb); setMode("view"); setNote("Moved. We've sent you the new time, and your calendar invite is updated.") }} />
                  <Button variant="ghost" className="self-start" onClick={() => setMode("view")}>Keep {clock(b.starts_at, tz)}</Button>
                </>
              )}
              {mode === "cancel" && (
                <div className="flex flex-col gap-3 rounded-xl border p-4">
                  <p>Cancel your {b.what.toLowerCase()} on {day(b.starts_at, tz)} at {clock(b.starts_at, tz)}?</p>
                  {error && <p role="alert" className="text-sm">{error}</p>}
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={cancel} disabled={busy}>Yes, cancel it</Button>
                    <Button variant="ghost" onClick={() => setMode("view")}>Keep the booking</Button>
                  </div>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </>
  )
}

export default function BookingPage() {
  return (
    <div className="min-h-svh bg-background">
      <main className="mx-auto flex w-full max-w-lg flex-col gap-8 px-4 pt-6 pb-16">
        <Suspense fallback={<Skeleton className="h-40 w-full rounded-xl" />}>
          <Manage />
        </Suspense>
      </main>
    </div>
  )
}

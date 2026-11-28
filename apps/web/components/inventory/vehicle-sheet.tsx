"use client"

/**
 * One car, opened from Inventory. One job: who wants this car, and what to do about it, before you walk the lot.
 * The buyers asking for it come first (a stock-number match before a "any 2021 Highlander"), each with their deal,
 * salesperson and the last thing they said, and a one-tap "Hold for them". Then the car's facts and its status.
 */

import credits from "@/lib/demo-photo-credits.json"
import { IconCar, IconExternalLink } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { toast } from "sonner"

import { LoadError } from "@/components/list-states"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { VipTag } from "@/components/vip"
import { api, send } from "@/lib/api"
import { clock, daysAgo, fmt } from "@/lib/time"

export type Hold = { by: string | null; at: string; for: { id: string; name: string } | null } | null
type Detail = {
  id: string; stock_number: string; vin: string | null; year: number; make: string; model: string; trim: string | null
  price: string | null; mileage: number | null; status: "available" | "hold" | "sold"; photos: string[]; created_at: string | null
  days_on_lot: number; color: string | null; body: string | null; seats: number | null; from_feed: boolean; hold: Hold
  buyers: {
    deal_id: string; client: { id: string; name: string; vip: boolean }; stage: string; wants: string | null; by_stock: boolean
    budget_max: number | null; salesperson: string | null; said: { body: string | null; at: string; channel: string } | null
  }[]
  can_hold: boolean; can_sell: boolean
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const STAGE: Record<string, string> = { new: "New", qualified: "Qualified", appointment: "Appointment booked", negotiating: "Negotiating" }

function when(iso: string) {
  const d = daysAgo(iso)
  return d === 0 ? clock(iso) : d === 1 ? "yesterday" : fmt(iso, { month: "short", day: "numeric" })
}

export function holdText(h: Hold) {
  if (!h) return "On hold"
  return `On hold${h.for ? ` for ${h.for.name}` : ""}${h.by ? `, by ${h.by.split(" ")[0]}` : ""}`
}

export function useSetStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { id: string; status: "available" | "hold" | "sold"; for_contact_id?: string; label: string }) =>
      send<{ status: string }>("PATCH", `/vehicles/${v.id}`, { status: v.status, for_contact_id: v.for_contact_id }),
    onSuccess: (_r, v) => {
      qc.invalidateQueries({ queryKey: ["vehicles"] })
      qc.invalidateQueries({ queryKey: ["vehicle", v.id] })
      toast(v.label)
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't change it. Try again."),
  })
}

type Credit = { model: string; artist: string; license: string; license_url: string; source: string }

/** The demo dealership's cars carry a stock photo of their model (docs/PLAN.md item 8), so it says so, with the
 * photographer's credit the licence asks for. A real dealer's photos come from their feed and need no line. */
function DemoCredit({ url }: { url: string }) {
  const c = (credits as Record<string, Credit>)[url]
  if (!c) return null
  return (
    <figcaption className="text-xs text-muted-foreground">
      Demo photo of a {c.model}, not this car. <a href={c.source} target="_blank" rel="noreferrer" className="underline underline-offset-2">{c.artist}</a>, {c.license}.
    </figcaption>
  )
}

export function CarThumb({ photos, className }: { photos: string[]; className?: string }) {
  // Photos come from the dealer's inventory feed. Without one, a plain mark: we never show a stock photo as theirs.
  return photos[0] ? (
    // eslint-disable-next-line @next/next/no-img-element -- dealer photo hosts vary; no image optimiser in between
    <img src={photos[0]} alt="" loading="lazy" className={`rounded-md bg-muted object-cover ${className ?? ""}`} />
  ) : (
    <span className={`flex items-center justify-center rounded-md bg-muted text-muted-foreground ${className ?? ""}`} aria-hidden="true">
      <IconCar className="size-1/2 max-h-6 max-w-6" stroke={1.5} />
    </span>
  )
}

function Body({ v }: { v: Detail }) {
  const set = useSetStatus()
  const name = `${v.year} ${v.make} ${v.model}`
  const facts: [string, React.ReactNode][] = [
    ["Price", v.price ? <span className="tabular-nums">{usd.format(Number(v.price))}</span> : "No price yet"],
    ["Miles", <span key="m" className="tabular-nums">{v.mileage ? v.mileage.toLocaleString("en-US") : "New"}</span>],
    ...(v.body ? [["Body", `${v.body.charAt(0).toUpperCase()}${v.body.slice(1)}${v.seats ? `, ${v.seats} seats` : ""}`] as [string, React.ReactNode]] : []),
    ...(v.color ? [["Color", v.color] as [string, React.ReactNode]] : []),
    ["Stock", <span key="s" className="font-mono text-xs">{v.stock_number}</span>],
    ...(v.vin ? [["VIN", <span key="v" className="font-mono text-xs break-all">{v.vin}</span>] as [string, React.ReactNode]] : []),
    ["On the lot", v.created_at ? `${v.days_on_lot} ${v.days_on_lot === 1 ? "day" : "days"}, since ${fmt(v.created_at, { month: "short", day: "numeric" })}` : "Unknown"],
  ]
  return (
    <div className="flex flex-col gap-6 px-4 pb-6 sm:px-6">
      {v.photos.length > 0 && (
        <figure className="flex flex-col gap-1">
          <CarThumb photos={v.photos} className="aspect-[16/10] w-full" />
          <DemoCredit url={v.photos[0]} />
        </figure>
      )}

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">{v.status === "sold" ? "Sold" : v.status === "hold" ? holdText(v.hold) : "In stock"}</h3>
        <div className="flex flex-wrap gap-2">
          {v.status !== "available" && (v.status !== "sold" || v.can_sell) && v.can_hold && (
            <Button size="sm" variant="outline" onClick={() => set.mutate({ id: v.id, status: "available", label: `${name} is back in stock.` })}>
              {v.status === "sold" ? "Back in stock" : "Release the hold"}
            </Button>
          )}
          {v.status === "available" && v.can_hold && (
            <Button size="sm" variant="outline" onClick={() => set.mutate({ id: v.id, status: "hold", label: `${name} is on hold.` })}>Put on hold</Button>
          )}
          {v.status !== "sold" && v.can_sell && (
            <Button size="sm" variant="outline" onClick={() => set.mutate({ id: v.id, status: "sold", label: `${name} marked sold. Ondra stops offering it.` })}>Mark sold</Button>
          )}
        </div>
        {v.from_feed && <p className="text-xs text-muted-foreground">From your inventory file. A hold set here stays until it&apos;s released, even when the next file comes in.</p>}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">
          {v.buyers.length === 0 ? "Nobody's asking about it yet" : `${v.buyers.length} ${v.buyers.length === 1 ? "buyer is" : "buyers are"} asking about it`}
        </h3>
        {v.buyers.length === 0 ? (
          <p className="text-sm text-muted-foreground">No open deal names this car, or a {v.year} {v.model}. When a buyer asks, they show here.</p>
        ) : (
          <ul className="divide-y border-y">
            {v.buyers.map((b) => {
              const first = b.client.name.split(" ")[0]
              const heldForThem = v.status === "hold" && v.hold?.for?.id === b.client.id
              return (
                <li key={b.deal_id} className="flex flex-col gap-1.5 py-3 text-sm" data-vip={b.client.vip || undefined}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="flex items-center gap-1.5 font-medium">{b.client.vip && <VipTag />}{b.client.name}</p>
                      <p className="text-muted-foreground">
                        {STAGE[b.stage] ?? b.stage}
                        {b.budget_max ? <span className="tabular-nums">, up to {usd.format(b.budget_max)}</span> : null}
                        {b.salesperson ? `, with ${b.salesperson.split(" ")[0]}` : ", nobody has it yet"}
                        {!b.by_stock && b.wants ? `. Asked for "${b.wants}"` : ""}
                      </p>
                    </div>
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/deals?deal=${b.deal_id}`}><IconExternalLink /> Deal</Link>
                    </Button>
                  </div>
                  {b.said?.body && (
                    <p className="text-pretty text-muted-foreground">
                      <span className="text-foreground">&ldquo;{b.said.body}&rdquo;</span> <span className="tabular-nums">{when(b.said.at)}</span>
                    </p>
                  )}
                  {v.can_hold && v.status !== "sold" && !heldForThem && (
                    <Button size="sm" variant="outline" className="self-start" disabled={set.isPending}
                      onClick={() => set.mutate({ id: v.id, status: "hold", for_contact_id: b.client.id, label: `${name} is on hold for ${first}.` })}>
                      Hold for {first}
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">The car</h3>
        <dl className="divide-y border-y">
          {facts.map(([k, val]) => (
            <div key={k} className="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 py-2 text-sm">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="min-w-0">{val}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  )
}

export function VehicleSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const q = useQuery({ queryKey: ["vehicle", id], queryFn: () => api<Detail>(`/vehicles/${id}`), enabled: !!id })
  const v = q.data
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-lg">
        <SheetHeader className="px-4 pt-5 pb-4 sm:px-6">
          <SheetTitle className="pr-8 text-xl font-normal tracking-tight">{v ? `${v.year} ${v.make} ${v.model}` : "Vehicle"}</SheetTitle>
          <SheetDescription>{v ? [v.trim, v.price ? usd.format(Number(v.price)) : null].filter(Boolean).join(", ") : "Loading"}</SheetDescription>
        </SheetHeader>
        {q.isPending ? (
          <div className="flex flex-col gap-3 px-4 sm:px-6" aria-label="Loading"><Skeleton className="h-9 w-full" /><Skeleton className="h-40 w-full" /></div>
        ) : q.isError ? (
          <div className="px-4 sm:px-6"><LoadError message={q.error.message} onRetry={() => q.refetch()} /></div>
        ) : v ? <Body v={v} /> : null}
      </SheetContent>
    </Sheet>
  )
}

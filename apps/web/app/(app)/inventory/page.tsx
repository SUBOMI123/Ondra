"use client"

/**
 * Inventory. One job: know what's on the lot, what's sitting too long and which cars buyers are asking about, and
 * change a car's status the moment it changes. Search first; in stock by default; sort by what a manager asks of
 * the lot (longest here, most asked about, newest, price). Hold or sell from the row; open a car to see who wants it.
 * Days on the lot count from when the car first came in. "Asked about" counts open deals that name the car.
 */

import { IconChevronDown, IconSearch } from "@tabler/icons-react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useDeferredValue, useEffect, useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { Pager } from "@/components/pager"
import { CarThumb, type Hold, holdText, useSetStatus, VehicleSheet } from "@/components/inventory/vehicle-sheet"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

type Car = {
  id: string; stock_number: string; vin: string | null; year: number; make: string; model: string; trim: string | null
  price: string | null; mileage: number | null; status: "available" | "hold" | "sold"; photos: string[]
  days_on_lot: number; asked_about: number; hold: Hold
}
type Lot = { items: Car[]; total: number; makes: string[]; can_hold: boolean; can_sell: boolean }
type Sort = "oldest" | "asked" | "newest" | "price_low" | "price_high"

const PER_PAGE = 25
const AGING = 60 // days: past this a car costs more to keep than it's worth waiting for
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const SORTS: Record<Sort, string> = {
  oldest: "Longest on the lot", asked: "Most asked about", newest: "Newest arrivals", price_low: "Price, low to high", price_high: "Price, high to low",
}

function StatusMenu({ c, canHold, canSell }: { c: Car; canHold: boolean; canSell: boolean }) {
  const set = useSetStatus()
  const name = `${c.year} ${c.make} ${c.model}`
  const label = c.status === "available" ? "In stock" : c.status === "sold" ? "Sold" : holdText(c.hold)
  const options = [
    c.status !== "available" && (c.status !== "sold" || canSell) && { status: "available" as const, text: c.status === "sold" ? "Back in stock" : "Release the hold", done: `${name} is back in stock.` },
    c.status === "available" && { status: "hold" as const, text: "Put on hold", done: `${name} is on hold.` },
    c.status !== "sold" && canSell && { status: "sold" as const, text: "Mark sold", done: `${name} marked sold. Ondra stops offering it.` },
  ].filter(Boolean) as { status: Car["status"]; text: string; done: string }[]
  if (!canHold || options.length === 0) return <span className="text-sm text-muted-foreground">{label}</span>
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className={cn("relative z-10 -ml-2 max-w-full gap-1 font-normal", c.status === "available" && "text-muted-foreground")}
          aria-label={`${label}. Change status of ${name}`}>
          <span className="truncate">{label}</span>
          <IconChevronDown className="size-3.5 shrink-0" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {options.map((o) => (
          <DropdownMenuItem key={o.status} onSelect={() => set.mutate({ id: c.id, status: o.status, label: o.done })}>{o.text}</DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function Inventory() {
  const router = useRouter()
  const open = useSearchParams().get("car")
  const [status, setStatus] = useState("available")
  const [make, setMake] = useState("all")
  const [sort, setSort] = useState<Sort>("oldest")
  const [q, setQ] = useState("")
  const [page, setPage] = useState(0)
  const query = useDeferredValue(q.trim())
  useEffect(() => {
    setPage(0)
  }, [status, make, sort, query])

  const params = new URLSearchParams({ limit: String(PER_PAGE), offset: String(page * PER_PAGE), sort })
  if (status !== "all") params.set("status", status)
  if (make !== "all") params.set("make", make)
  if (query) params.set("q", query)
  const res = useQuery({ queryKey: ["vehicles", params.toString()], queryFn: () => api<Lot>(`/vehicles?${params}`), placeholderData: keepPreviousData })
  const setOpen = (id: string | null) => router.replace(id ? `/inventory?car=${id}` : "/inventory", { scroll: false })

  const items = res.data?.items ?? []
  const total = res.data?.total ?? 0
  const aging = items.filter((c) => c.status === "available" && c.days_on_lot > AGING).length
  const asked = items.filter((c) => c.asked_about > 0).length
  // Thumbnails only when the feed sends photos: a column of identical placeholders is clutter, not information.
  const hasPhotos = items.some((c) => c.photos.length > 0)

  return (
    <>
      <SiteHeader title="Inventory" />
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-6 lg:px-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <IconSearch className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Make, model, year, stock number or VIN" aria-label="Search inventory"
              className="pl-9 [&::-webkit-search-cancel-button]:appearance-none" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Tabs value={status} onValueChange={setStatus}>
              <TabsList aria-label="Show">
                <TabsTrigger value="available">In stock</TabsTrigger>
                <TabsTrigger value="hold">On hold</TabsTrigger>
                <TabsTrigger value="sold">Sold</TabsTrigger>
                <TabsTrigger value="all">All</TabsTrigger>
              </TabsList>
            </Tabs>
            <Select value={make} onValueChange={setMake}>
              <SelectTrigger className="w-36" aria-label="Make"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All makes</SelectItem>
                {(res.data?.makes ?? []).map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={sort} onValueChange={(v) => setSort(v as Sort)}>
              <SelectTrigger className="w-48" aria-label="Order"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(Object.keys(SORTS) as Sort[]).map((k) => <SelectItem key={k} value={k}>{SORTS[k]}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        {res.isPending ? (
          <TableSkeleton rows={8} />
        ) : res.isError ? (
          <LoadError message={res.error.message} onRetry={() => res.refetch()} />
        ) : items.length === 0 ? (
          <div className="rounded-xl border p-6 text-sm">
            {query || make !== "all" ? (
              <p className="text-muted-foreground">Nothing matches. Try a make, a model or the last digits of a stock number.</p>
            ) : (
              <>
                <p className="font-medium">No cars here yet</p>
                <p className="mt-1 text-muted-foreground">Import your inventory file and Ondra can answer &ldquo;do you have it?&rdquo; from it.</p>
                <Button asChild variant="outline" size="sm" className="mt-3"><Link href="/settings/integrations#inventory">Import a file</Link></Button>
              </>
            )}
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground tabular-nums">
              {total} {total === 1 ? "car" : "cars"}
              {total <= PER_PAGE && aging > 0 && `. ${aging} in stock over ${AGING} days`}
              {total <= PER_PAGE && asked > 0 && `. ${asked} ${asked === 1 ? "has" : "have"} buyers asking`}
            </p>
            <div className="overflow-hidden rounded-xl border">
              <Table className="table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-auto">Vehicle</TableHead>
                    <TableHead className="w-28 text-right">Price</TableHead>
                    <TableHead className="hidden w-24 text-right md:table-cell">Miles</TableHead>
                    <TableHead className="hidden w-28 text-right sm:table-cell">On the lot</TableHead>
                    <TableHead className="hidden w-32 lg:table-cell">Asked about</TableHead>
                    <TableHead className="hidden w-48 md:table-cell">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className={res.isPlaceholderData ? "opacity-60" : undefined}>
                  {items.map((c) => (
                    <TableRow key={c.id} className="relative">
                      <TableCell className="py-2.5">
                        <div className="flex min-w-0 items-center gap-3">
                          {hasPhotos && <CarThumb photos={c.photos} className="h-10 w-14 shrink-0" />}
                          <div className="min-w-0">
                            <button type="button" onClick={() => setOpen(c.id)}
                              className="block max-w-full truncate rounded-sm text-left font-medium outline-none after:absolute after:inset-0 hover:underline focus-visible:ring-2 focus-visible:ring-ring">
                              {c.year} {c.make} {c.model} <span className="font-normal text-muted-foreground">{c.trim}</span>
                            </button>
                            <p className="truncate text-xs text-muted-foreground">
                              <span className="font-mono">{c.stock_number}</span>
                              {/* Phones: what the hidden columns would say, in one line. */}
                              <span className="sm:hidden">{`, ${c.days_on_lot} days`}{c.asked_about > 0 ? `, ${c.asked_about} asking` : ""}{c.status !== "available" ? `, ${c.status === "hold" ? "on hold" : "sold"}` : ""}</span>
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right font-medium tabular-nums">{c.price ? usd.format(Number(c.price)) : "No price"}</TableCell>
                      <TableCell className="hidden text-right text-muted-foreground tabular-nums md:table-cell">{c.mileage ? c.mileage.toLocaleString("en-US") : "New"}</TableCell>
                      <TableCell className={cn("hidden text-right tabular-nums sm:table-cell", c.status === "available" && c.days_on_lot > AGING ? "font-medium" : "text-muted-foreground")}>
                        {c.days_on_lot} {c.days_on_lot === 1 ? "day" : "days"}
                      </TableCell>
                      <TableCell className={cn("hidden lg:table-cell", c.asked_about ? "" : "text-muted-foreground")}>
                        {c.asked_about ? `${c.asked_about} ${c.asked_about === 1 ? "buyer" : "buyers"}` : "Nobody yet"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell"><StatusMenu c={c} canHold={!!res.data?.can_hold} canSell={!!res.data?.can_sell} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <Pager page={page} perPage={PER_PAGE} total={total} noun={["car", "cars"]} onPage={setPage} />
          </>
        )}
      </div>
      <VehicleSheet id={open} onClose={() => setOpen(null)} />
    </>
  )
}

export default function InventoryPage() {
  return (
    <Suspense fallback={null}>
      <Inventory />
    </Suspense>
  )
}

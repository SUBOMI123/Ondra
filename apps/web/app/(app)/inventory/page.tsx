"use client"

/**
 * Inventory. One job: "do we have it, and at what price?" Search first; in-stock cars by default; status only
 * where it changes the answer (on hold, sold). VIN is on hover of the stock number, not a column nobody scans.
 */

import { IconSearch } from "@tabler/icons-react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { useDeferredValue, useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { api, type Page, type Vehicle } from "@/lib/api"

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const miles = new Intl.NumberFormat("en-US")

export default function InventoryPage() {
  const [status, setStatus] = useState("available")
  const [q, setQ] = useState("")
  const query = useDeferredValue(q)
  const res = useQuery({
    queryKey: ["vehicles", status, query],
    queryFn: () => {
      const p = new URLSearchParams({ limit: "200" })
      if (status !== "all") p.set("status", status)
      if (query.trim()) p.set("q", query.trim())
      return api<Page<Vehicle>>(`/vehicles?${p}`)
    },
    placeholderData: keepPreviousData,
  })
  return (
    <>
      <SiteHeader title="Inventory" />
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-6 lg:px-6">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-0 flex-1 basis-64">
            <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Make, model, year or stock number" aria-label="Search inventory" className="pl-8" />
          </div>
          <ToggleGroup type="single" variant="outline" size="sm" value={status} onValueChange={(v) => v && setStatus(v)} aria-label="Show">
            <ToggleGroupItem value="available" className="px-3">In stock</ToggleGroupItem>
            <ToggleGroupItem value="hold" className="px-3">On hold</ToggleGroupItem>
            <ToggleGroupItem value="sold" className="px-3">Sold</ToggleGroupItem>
            <ToggleGroupItem value="all" className="px-3">All</ToggleGroupItem>
          </ToggleGroup>
        </div>
        {res.isPending ? (
          <TableSkeleton />
        ) : res.isError ? (
          <LoadError message={res.error.message} onRetry={() => res.refetch()} />
        ) : res.data.items.length === 0 ? (
          <p className="rounded-xl border p-6 text-sm text-muted-foreground">
            {query ? `Nothing matches “${query}”. Try a make, a model or a stock number.` : "No vehicles here."}
          </p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground tabular-nums">{res.data.total} vehicles</p>
            <div className="overflow-x-auto rounded-xl border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Vehicle</TableHead>
                    <TableHead>Stock</TableHead>
                    <TableHead className="text-right">Miles</TableHead>
                    <TableHead className="text-right">Price</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {res.data.items.map((v) => (
                    <TableRow key={v.id}>
                      <TableCell>
                        <span className="font-medium">
                          {v.year} {v.make} {v.model}
                        </span>{" "}
                        <span className="text-muted-foreground">{v.trim}</span>
                        {v.status !== "available" && (
                          <span className="ml-2 text-xs text-muted-foreground">{v.status === "hold" ? "On hold" : "Sold"}</span>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground" title={v.vin ? `VIN ${v.vin}` : undefined}>
                        {v.stock_number}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground tabular-nums">{v.mileage ? miles.format(v.mileage) : "New"}</TableCell>
                      <TableCell className="text-right font-medium tabular-nums">{v.price ? usd.format(Number(v.price)) : "Call"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </div>
    </>
  )
}

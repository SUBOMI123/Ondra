"use client"

import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { api, type Page, type Vehicle } from "@/lib/api"

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const miles = new Intl.NumberFormat("en-US")
const STATUS_LABEL = { available: "Available", hold: "On hold", sold: "Sold" } as const

export default function InventoryPage() {
  const [status, setStatus] = useState("")
  const query = useQuery({
    queryKey: ["vehicles", status],
    queryFn: () => api<Page<Vehicle>>(`/vehicles?limit=200${status ? `&status=${status}` : ""}`),
  })
  return (
    <>
      <SiteHeader title="Inventory" />
      <div className="flex flex-col gap-4 p-4 lg:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ToggleGroup type="single" variant="outline" size="sm" value={status} onValueChange={(v) => setStatus(v)} aria-label="Filter by status">
            <ToggleGroupItem value="" className="px-3">All</ToggleGroupItem>
            <ToggleGroupItem value="available" className="px-3">Available</ToggleGroupItem>
            <ToggleGroupItem value="hold" className="px-3">On hold</ToggleGroupItem>
            <ToggleGroupItem value="sold" className="px-3">Sold</ToggleGroupItem>
          </ToggleGroup>
          {query.data && <span className="text-sm text-muted-foreground tabular-nums">{query.data.total} vehicles</span>}
        </div>
        {query.isPending ? (
          <TableSkeleton />
        ) : query.isError ? (
          <LoadError message={query.error.message} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <p className="rounded-lg border p-6 text-sm text-muted-foreground">No vehicles with this status.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader className="bg-muted">
                <TableRow>
                  <TableHead>Vehicle</TableHead>
                  <TableHead>Stock</TableHead>
                  <TableHead className="hidden md:table-cell">VIN</TableHead>
                  <TableHead className="text-right">Miles</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((v) => (
                  <TableRow key={v.id}>
                    <TableCell className="font-medium">
                      {v.year} {v.make} {v.model} <span className="text-muted-foreground">{v.trim}</span>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{v.stock_number}</TableCell>
                    <TableCell className="hidden font-mono text-xs text-muted-foreground md:table-cell">{v.vin}</TableCell>
                    <TableCell className="text-right tabular-nums">{v.mileage ? miles.format(v.mileage) : "New"}</TableCell>
                    <TableCell className="text-right tabular-nums">{v.price ? usd.format(Number(v.price)) : "–"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={v.status === "available" ? "" : "text-muted-foreground"}>
                        {STATUS_LABEL[v.status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  )
}

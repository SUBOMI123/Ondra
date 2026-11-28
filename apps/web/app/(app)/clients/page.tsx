"use client"

/**
 * Clients. One job: find a client by anything you know about them (name, phone, email), and see where they stand
 * before you open them. One row each: who they are and how to reach them, their latest deal, who looks after them,
 * and when you were last in touch. Most recent first, because the client you want is usually one you just spoke to.
 * Search, filters and paging are done by the API, so it holds up at thousands of clients.
 */

import { IconBrandWhatsapp, IconChevronLeft, IconChevronRight, IconMail, IconMessage, IconPhone, IconSearch, IconX } from "@tabler/icons-react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useEffect, useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { useAuth } from "@/components/providers"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { VipTag } from "@/components/vip"
import { api, type Contact, type Page } from "@/lib/api"
import { clock, dayKey, daysAgo, fmt } from "@/lib/time"

type Row = Contact & {
  last_contact_at: string | null
  deal: { type: "sales" | "service"; stage: string; vehicle: string | null; budget_max: number | null } | null
  looks_after: string | null
}

const PER_PAGE = 50
const CHANNEL = {
  phone: { icon: IconPhone, label: "Prefers calls" },
  sms: { icon: IconMessage, label: "Prefers texts" },
  email: { icon: IconMail, label: "Prefers email" },
  whatsapp: { icon: IconBrandWhatsapp, label: "Prefers WhatsApp" },
} as const
const STAGE: Record<string, string> = { new: "New", qualified: "Qualified", appointment: "Appointment booked", negotiating: "Negotiating", won: "Bought", lost: "Lost" }

function formatPhone(e164?: string) {
  const m = e164?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : (e164 ?? "")
}

/** "2:14 pm" today, "Yesterday", a weekday this week, then "Nov 3". */
function when(iso: string | null) {
  if (!iso) return null
  const days = daysAgo(iso)
  if (days === 0) return clock(iso)
  if (days === 1) return "Yesterday"
  if (days < 7) return fmt(iso, { weekday: "long" })
  return fmt(iso, { month: "short", day: "numeric", year: dayKey(iso).slice(0, 4) === dayKey(new Date()).slice(0, 4) ? undefined : "numeric" })
}

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

/** How to reach them: their preferred channel's number or address, once. */
function Reach({ c }: { c: Row }) {
  const pref = CHANNEL[c.preferred_channel as keyof typeof CHANNEL]
  const email = c.identities.find((i) => i.kind === "email")?.value
  const phone = c.identities.find((i) => i.kind === "phone")?.value
  const value = c.preferred_channel === "email" ? (email ?? formatPhone(phone)) : phone ? formatPhone(phone) : email
  if (!value) return null
  return (
    <span className="flex min-w-0 items-center gap-1.5 text-sm text-muted-foreground">
      {pref && <pref.icon className="size-3.5 shrink-0" aria-label={pref.label} />}
      <span className="truncate tabular-nums">{value}</span>
    </span>
  )
}

function Deal({ d }: { d: Row["deal"] }) {
  if (!d) return <span className="text-sm text-muted-foreground">No deal</span>
  const what = d.vehicle ?? (d.type === "service" ? "Service" : "Car not chosen yet")
  return (
    <span className="flex min-w-0 flex-col">
      <span className="truncate text-sm">{what}</span>
      <span className="text-sm text-muted-foreground">
        {d.type === "service" ? "Service, " : ""}{STAGE[d.stage] ?? d.stage}
        {d.budget_max ? <span className="tabular-nums">, up to ${d.budget_max.toLocaleString("en-US")}</span> : null}
      </span>
    </span>
  )
}

export default function ClientsPage() {
  const { me } = useAuth()
  const seesVips = me?.role === "admin" || me?.role === "manager"
  const [q, setQ] = useState("")
  const [show, setShow] = useState<"all" | "vip">("all")
  const [sort, setSort] = useState<"recent" | "name">("recent")
  const [page, setPage] = useState(0)
  const search = useDebounced(q.trim())
  useEffect(() => {
    setPage(0)
  }, [search, show, sort])

  const params = new URLSearchParams({ limit: String(PER_PAGE), offset: String(page * PER_PAGE), sort })
  if (search) params.set("q", search)
  if (show === "vip") params.set("vip", "true")
  const query = useQuery({
    queryKey: ["contacts", params.toString()],
    queryFn: () => api<Page<Row>>(`/contacts?${params}`),
    placeholderData: keepPreviousData,
  })
  const total = query.data?.total ?? 0
  const from = total === 0 ? 0 : page * PER_PAGE + 1
  const to = Math.min(total, (page + 1) * PER_PAGE)

  return (
    <>
      <SiteHeader title="Clients" />
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-6 lg:px-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="relative min-w-0 flex-1">
            <IconSearch className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              type="search"
              aria-label="Search clients"
              placeholder="Search by name, phone or email"
              className="pr-9 pl-9 [&::-webkit-search-cancel-button]:appearance-none"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && setQ("")}
            />
            {q && (
              <Button variant="ghost" size="icon" aria-label="Clear search" onClick={() => setQ("")}
                className="absolute top-1/2 right-1 size-7 -translate-y-1/2 text-muted-foreground">
                <IconX />
              </Button>
            )}
          </div>
          <div className="flex items-center gap-3">
            {seesVips && (
              <Tabs value={show} onValueChange={(v) => setShow(v as "all" | "vip")}>
                <TabsList aria-label="Show">
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="vip">VIPs</TabsTrigger>
                </TabsList>
              </Tabs>
            )}
            <Select value={sort} onValueChange={(v) => setSort(v as "recent" | "name")}>
              <SelectTrigger className="w-full md:w-48" aria-label="Order">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="recent">Last in touch first</SelectItem>
                <SelectItem value="name">By name, A to Z</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {query.isPending ? (
          <TableSkeleton rows={8} />
        ) : query.isError ? (
          <LoadError message={query.error.message} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <p className="rounded-xl border p-6 text-sm text-muted-foreground">
            {search ? `No client matches “${search}”. Try part of their name, or the last digits of their number.`
              : show === "vip" ? "No VIPs yet. Open a client and choose Make VIP: a person will always handle them, never Ondra."
              : "No clients yet. They appear here as soon as someone calls, texts or emails."}
          </p>
        ) : (
          <>
            <div className="overflow-hidden rounded-xl border">
              <Table className="table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-auto md:w-[34%]">Client</TableHead>
                    <TableHead className="hidden md:table-cell">Deal</TableHead>
                    <TableHead className="hidden w-40 lg:table-cell">Looks after</TableHead>
                    <TableHead className="w-28 text-right">Last in touch</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className={query.isPlaceholderData ? "opacity-60" : undefined}>
                  {query.data.items.map((c) => (
                    <TableRow key={c.id} data-vip={c.is_vip || undefined} className="relative">
                      <TableCell className="py-3 align-top">
                        <Link
                          href={`/clients/profile?id=${c.id}`}
                          className="flex items-center gap-1.5 rounded-sm font-medium outline-none after:absolute after:inset-0 hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {c.is_vip && <VipTag />}
                          <span className="truncate">{c.display_name}</span>
                        </Link>
                        <Reach c={c} />
                        {/* Phones: the deal sits under the name, since there's no room for its own column. */}
                        {c.deal && <span className="mt-1 block md:hidden"><Deal d={c.deal} /></span>}
                      </TableCell>
                      <TableCell className="hidden py-3 align-top md:table-cell"><Deal d={c.deal} /></TableCell>
                      <TableCell className="hidden truncate py-3 align-top text-sm lg:table-cell">
                        {c.looks_after ?? <span className="text-muted-foreground">Nobody yet</span>}
                      </TableCell>
                      <TableCell className="py-3 text-right align-top text-sm text-muted-foreground tabular-nums">
                        {when(c.last_contact_at) ?? "Not yet"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
              <span className="tabular-nums">
                {from}–{to} of {total.toLocaleString("en-US")} {show === "vip" ? (total === 1 ? "VIP" : "VIPs") : total === 1 ? "client" : "clients"}
              </span>
              {total > PER_PAGE && (
                <span className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                    <IconChevronLeft /> Previous
                  </Button>
                  <Button variant="outline" size="sm" disabled={to >= total} onClick={() => setPage((p) => p + 1)}>
                    Next <IconChevronRight />
                  </Button>
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}

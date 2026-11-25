"use client"

import { IconBrandWhatsapp, IconCrownFilled, IconMail, IconMessage, IconPhone } from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, type Contact, type Page } from "@/lib/api"

const CHANNEL = {
  phone: { icon: IconPhone, label: "Phone" },
  sms: { icon: IconMessage, label: "Text" },
  email: { icon: IconMail, label: "Email" },
  whatsapp: { icon: IconBrandWhatsapp, label: "WhatsApp" },
} as const

function formatPhone(e164?: string) {
  const m = e164?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : e164 ?? ""
}

export default function ClientsPage() {
  const [q, setQ] = useState("")
  const query = useQuery({
    queryKey: ["contacts", q],
    queryFn: () => api<Page<Contact>>(`/contacts?limit=200${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  })
  return (
    <>
      <SiteHeader title="Clients" />
      <div className="flex flex-col gap-4 p-4 lg:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Input
            aria-label="Search clients"
            placeholder="Search by name"
            className="max-w-xs"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {query.data && <span className="text-sm text-muted-foreground tabular-nums">{query.data.total} clients</span>}
        </div>
        {query.isPending ? (
          <TableSkeleton />
        ) : query.isError ? (
          <LoadError message={query.error.message} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <p className="rounded-lg border p-6 text-sm text-muted-foreground">
            {q ? `No clients match “${q}”.` : "No clients yet. They appear here as soon as someone calls, texts or emails."}
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader className="bg-muted">
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead className="hidden md:table-cell">Email</TableHead>
                  <TableHead>Prefers</TableHead>
                  <TableHead className="hidden lg:table-cell">Tags</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((c) => {
                  const ch = CHANNEL[c.preferred_channel as keyof typeof CHANNEL]
                  return (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">
                        <span className="flex items-center gap-1.5">
                          {c.is_vip && <IconCrownFilled className="size-4 text-vip" aria-label="VIP" />}
                          {c.display_name}
                        </span>
                      </TableCell>
                      <TableCell className="tabular-nums">{formatPhone(c.identities.find((i) => i.kind === "phone")?.value)}</TableCell>
                      <TableCell className="hidden text-muted-foreground md:table-cell">
                        {c.identities.find((i) => i.kind === "email")?.value}
                      </TableCell>
                      <TableCell>
                        {ch && (
                          <span className="flex items-center gap-1.5 text-muted-foreground">
                            <ch.icon className="size-4" aria-hidden="true" />
                            {ch.label}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        <div className="flex gap-1">
                          {c.tags.map((t) => (
                            <Badge key={t} variant="outline" className="text-muted-foreground">
                              {t}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  )
}

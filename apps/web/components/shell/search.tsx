"use client"

/**
 * The search box (sidebar Search, the header bar, ⌘K). One job: get to a client, a car, a conversation or a deal by
 * typing whatever you remember: a name, a phone number however it's written, a stock number, what someone said.
 * Results come from GET /search (VIPs hidden as on every list). Enter opens the highlighted one.
 */

import { IconCar, IconLayoutKanban, IconMessage, IconUser } from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { VipTag } from "@/components/vip"
import { api } from "@/lib/api"

type Results = {
  clients: { id: string; name: string; is_vip: boolean; detail: string | null }[]
  cars: { id: string; title: string; trim: string | null; stock_number: string; status: string; price: string | null }[]
  conversations: { id: string; client: string; is_vip: boolean; channel: string; snippet: string }[]
  deals: { id: string; client: string; is_vip: boolean; stage: string; wants: string | null }[]
}

const CHANNEL: Record<string, string> = { sms: "Text", whatsapp: "WhatsApp", email: "Email", phone: "Call" }
const STAGE: Record<string, string> = { new: "New", qualified: "Qualified", appointment: "Appointment", negotiating: "Negotiating", won: "Won", lost: "Lost" }
const STATUS: Record<string, string> = { available: "In stock", hold: "On hold", sold: "Sold" }
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })

function phone(v: string | null) {
  const m = v?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : v
}

function useDebounced(value: string, ms = 200) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export function SearchPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter()
  const [text, setText] = useState("")
  const q = useDebounced(text.trim())
  const results = useQuery({ queryKey: ["search", q], queryFn: () => api<Results>(`/search?q=${encodeURIComponent(q)}`), enabled: open && q.length > 0 })
  const r = results.data
  const none = r && !r.clients.length && !r.cars.length && !r.conversations.length && !r.deals.length

  const go = (href: string) => {
    onOpenChange(false)
    setText("")
    router.push(href)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setText("") }}>
      <DialogContent className="top-[12vh] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-xl" showCloseButton={false}>
        <DialogTitle className="sr-only">Search</DialogTitle>
        <DialogDescription className="sr-only">Search clients, cars, conversations and deals</DialogDescription>
        <Command shouldFilter={false} className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground">
          <CommandInput value={text} onValueChange={setText} placeholder="Name, phone, stock number, or what someone said" className="h-12" />
          <CommandList className="max-h-[min(60vh,28rem)]">
            {!q ? (
              <p className="px-4 py-6 text-sm text-muted-foreground">
                Try a client&apos;s name or number, a car (&ldquo;Highlander&rdquo;, a stock number), or something a customer said (&ldquo;tow package&rdquo;).
              </p>
            ) : results.isPending ? (
              <div className="flex flex-col gap-2 p-3" aria-label="Searching"><Skeleton className="h-9 w-full" /><Skeleton className="h-9 w-full" /><Skeleton className="h-9 w-2/3" /></div>
            ) : results.isError ? (
              <p className="px-4 py-6 text-sm text-muted-foreground">Search didn&apos;t load. Check your connection and try again.</p>
            ) : none ? (
              <CommandEmpty className="px-4 py-6 text-left text-sm text-muted-foreground">Nothing matches &ldquo;{q}&rdquo;. Try part of a name, the last digits of a number, or a model.</CommandEmpty>
            ) : r ? (
              <>
                {r.clients.length > 0 && (
                  <CommandGroup heading="Clients">
                    {r.clients.map((c) => (
                      <CommandItem key={c.id} value={`client-${c.id}`} onSelect={() => go(`/clients/profile?id=${c.id}`)} data-vip={c.is_vip || undefined}>
                        <IconUser className="text-muted-foreground" />
                        <span className="flex min-w-0 items-center gap-1.5">{c.is_vip && <VipTag />}<span className="truncate">{c.name}</span></span>
                        {c.detail && <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">{phone(c.detail)}</span>}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {r.cars.length > 0 && (
                  <CommandGroup heading="Cars">
                    {r.cars.map((v) => (
                      <CommandItem key={v.id} value={`car-${v.id}`} onSelect={() => go(`/inventory?car=${v.id}`)}>
                        <IconCar className="text-muted-foreground" />
                        <span className="min-w-0 truncate">{v.title}{v.trim ? ` ${v.trim}` : ""}</span>
                        <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">
                          {STATUS[v.status] ?? v.status}{v.price ? `, ${usd.format(Number(v.price))}` : ""}
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {r.conversations.length > 0 && (
                  <CommandGroup heading="Conversations">
                    {r.conversations.map((c) => (
                      <CommandItem key={c.id} value={`conv-${c.id}`} onSelect={() => go(`/inbox?c=${c.id}`)} data-vip={c.is_vip || undefined}>
                        <IconMessage className="text-muted-foreground" />
                        <span className="flex min-w-0 flex-col">
                          <span className="flex items-center gap-1.5">{c.is_vip && <VipTag />}{c.client}<span className="text-xs text-muted-foreground">{CHANNEL[c.channel] ?? c.channel}</span></span>
                          <span className="truncate text-xs text-muted-foreground">{c.snippet}</span>
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {r.deals.length > 0 && (
                  <CommandGroup heading="Deals">
                    {r.deals.map((d) => (
                      <CommandItem key={d.id} value={`deal-${d.id}`} onSelect={() => go(`/deals?deal=${d.id}`)} data-vip={d.is_vip || undefined}>
                        <IconLayoutKanban className="text-muted-foreground" />
                        <span className="flex min-w-0 items-center gap-1.5">{d.is_vip && <VipTag />}<span className="truncate">{d.client}{d.wants ? `: ${d.wants}` : ""}</span></span>
                        <span className="ml-auto shrink-0 text-xs text-muted-foreground">{STAGE[d.stage] ?? d.stage}</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
              </>
            ) : null}
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  )
}

"use client"

import { IconBrandWhatsapp, IconCrownFilled, IconMail, IconMessage, IconPhone } from "@tabler/icons-react"
import { useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { SALES_STAGES, SERVICE_STAGES, type Channel, type DealCard } from "@/lib/examples"

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })
const compact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 })
const CHANNEL_ICON: Record<Channel, typeof IconPhone> = { phone: IconPhone, sms: IconMessage, email: IconMail, whatsapp: IconBrandWhatsapp }

function Deal({ d }: { d: DealCard }) {
  const Ch = CHANNEL_ICON[d.channel]
  return (
    <article className="flex flex-col gap-1.5 rounded-xl border bg-card p-3 text-sm shadow-xs">
      <div className="flex items-center gap-1.5 font-medium">
        {d.vip && <IconCrownFilled className="size-3.5 shrink-0 text-vip" aria-label="VIP" />}
        <span className="truncate">{d.client}</span>
      </div>
      <p className="truncate text-muted-foreground">{d.vehicle}</p>
      {d.note && <p className="text-xs text-muted-foreground">{d.note}</p>}
      <div className="mt-1 flex items-center justify-between gap-2 text-xs">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Ch className="size-3.5" aria-hidden="true" />
          {d.owner}
          {d.byOndra && (
            <span className="flex items-center gap-1 text-ai" title="Ondra brought this lead in">
              <OndraMark className="size-3.5" /> Ondra
            </span>
          )}
        </span>
        <span className="font-medium tabular-nums">{d.value ? usd.format(d.value) : "Warranty"}</span>
      </div>
    </article>
  )
}

export default function DealsPage() {
  const [pipeline, setPipeline] = useState("sales")
  const stages = pipeline === "sales" ? SALES_STAGES : SERVICE_STAGES
  const all = stages.flatMap((s) => s.deals)
  const fromOndra = all.filter((d) => d.byOndra).length
  return (
    <>
      <SiteHeader title="Deals" note="Example data until deals are live in Step 3" />
      <div className="flex min-w-0 flex-col gap-4 p-4 lg:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ToggleGroup type="single" variant="outline" size="sm" value={pipeline} onValueChange={(v) => v && setPipeline(v)} aria-label="Pipeline">
            <ToggleGroupItem value="sales" className="px-3">Sales</ToggleGroupItem>
            <ToggleGroupItem value="service" className="px-3">Service</ToggleGroupItem>
          </ToggleGroup>
          <p className="flex items-center gap-3 text-sm text-muted-foreground tabular-nums">
            <span>
              {all.length} open, {compact.format(all.reduce((s, d) => s + d.value, 0))}
            </span>
            <span className="flex items-center gap-1 text-ai">
              <OndraMark className="size-3.5" /> {fromOndra} brought in by Ondra
            </span>
          </p>
        </div>
        <div className="-mx-4 overflow-x-auto px-4 pb-2 lg:-mx-6 lg:px-6">
          <div className="grid auto-cols-[16rem] grid-flow-col gap-3">
            {stages.map((s) => (
              <section key={s.stage} className="flex flex-col gap-2.5 rounded-xl bg-muted/40 p-2.5" aria-label={s.stage}>
                <h2 className="flex items-baseline justify-between px-1 pt-0.5 text-sm font-medium">
                  {s.stage}
                  <span className="text-xs font-normal text-muted-foreground tabular-nums">
                    {s.deals.length}
                    {s.deals.some((d) => d.value) && `, ${compact.format(s.deals.reduce((a, d) => a + d.value, 0))}`}
                  </span>
                </h2>
                {s.deals.map((d) => (
                  <Deal key={d.client + d.vehicle} d={d} />
                ))}
              </section>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}

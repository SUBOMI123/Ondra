"use client"

/**
 * Settings. One job: set how Ondra behaves and who does what.
 * Five sections in the order an owner sets up: the business, the team, how Ondra replies, VIPs, channels.
 * Team and VIPs are real (API); the other sections are working controls that aren't saved until Step 6,
 * which the header says plainly.
 */

import { IconCheck, IconCrownFilled } from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { SiteHeader } from "@/components/dashboard/site-header"
import { TableSkeleton } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { useAuth } from "@/components/providers"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Switch } from "@/components/ui/switch"
import { api, type Contact, type Page } from "@/lib/api"
import { cn } from "@/lib/utils"

type User = { id: string; email: string; name: string; role: string; active: boolean }

const SECTIONS = [
  { id: "business", title: "Business" },
  { id: "team", title: "Team" },
  { id: "ondra", title: "How Ondra replies" },
  { id: "vips", title: "VIPs" },
  { id: "channels", title: "Channels" },
]

const ROLE_LABEL: Record<string, string> = {
  owner: "Owner", admin: "Admin", manager: "Manager", sales: "Sales", service: "Service", ops: "Operations", viewer: "View only",
}

const HOURS = [
  ["Monday", "9:00 am", "7:00 pm"], ["Tuesday", "9:00 am", "7:00 pm"], ["Wednesday", "9:00 am", "7:00 pm"],
  ["Thursday", "9:00 am", "7:00 pm"], ["Friday", "9:00 am", "7:00 pm"], ["Saturday", "9:00 am", "6:00 pm"], ["Sunday", "", ""],
]

const HANDOFFS = ["A discount or final price", "What their trade-in is worth", "A delivery date", "A complaint", "Financing terms"]

const CHANNELS = [
  { name: "Phone", status: "Connected", ok: true, detail: "(214) 555-0100 forwards to Ondra when nobody picks up." },
  { name: "Email", status: "Connected", ok: true, detail: "sales@ and service@ forward to Ondra." },
  { name: "Text", status: "Registration pending", ok: false, detail: "US carriers are reviewing your business texting registration. This usually takes 2 to 3 weeks." },
  { name: "WhatsApp", status: "Not connected", ok: false, detail: "Needs Meta to verify your business first. We'll walk you through it." },
]

function Section({ id, title, description, children }: { id: string; title: string; description: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-20 border-b pb-10 last:border-b-0">
      <h2 id={`${id}-h`} className="text-lg font-medium">{title}</h2>
      <p className="mt-1 max-w-prose text-sm text-muted-foreground">{description}</p>
      <div className="mt-6">{children}</div>
    </section>
  )
}

export default function SettingsPage() {
  const { me } = useAuth()
  const [draftMode, setDraftMode] = useState(true)
  const [prices, setPrices] = useState("listed")
  const [handoffs, setHandoffs] = useState<string[]>(HANDOFFS.slice(0, 4))
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<Page<User>>("/users"), retry: false })
  const vips = useQuery({
    queryKey: ["contacts", "vips"],
    queryFn: async () => (await api<Page<Contact>>("/contacts?limit=200")).items.filter((c) => c.is_vip),
  })

  return (
    <>
      <SiteHeader title="Settings" note="Changes here aren't saved until Step 6" />
      <div className="mx-auto grid w-full max-w-5xl gap-10 px-4 py-6 lg:grid-cols-[11rem_minmax(0,1fr)] lg:px-6">
        <nav aria-label="Settings sections" className="hidden lg:block">
          <ul className="sticky top-6 flex flex-col gap-1 text-sm">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`} className="block rounded-md px-2 py-1.5 text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
                  {s.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex min-w-0 flex-col gap-10">
          <Section id="business" title="Business" description="Ondra answers outside these hours and books into the next opening.">
            <div className="grid max-w-md gap-2">
              <Label htmlFor="biz-name">Dealership name</Label>
              <Input id="biz-name" defaultValue={me?.tenant_name ?? ""} />
            </div>
            <div className="mt-6 max-w-md">
              <p className="mb-2 text-sm font-medium">Opening hours</p>
              <dl className="divide-y rounded-xl border text-sm">
                {HOURS.map(([day, open, close]) => (
                  <div key={day} className="grid grid-cols-[7rem_minmax(0,1fr)] px-4 py-2.5">
                    <dt>{day}</dt>
                    <dd className="text-muted-foreground tabular-nums">{open ? `${open} to ${close}` : "Closed"}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </Section>

          <Section id="team" title="Team" description="Who works here, and what each role can see and do. VIPs are visible to the owner and managers only.">
            {users.isPending ? (
              <TableSkeleton rows={5} />
            ) : users.isError ? (
              <p className="text-sm text-muted-foreground">Only owners, admins and managers can see the team.</p>
            ) : (
              <ul className="divide-y rounded-xl border">
                {users.data.items.map((u) => (
                  <li key={u.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{u.name}</p>
                      <p className="truncate text-sm text-muted-foreground">{u.email}</p>
                    </div>
                    <span className="text-sm text-muted-foreground">{ROLE_LABEL[u.role] ?? u.role}</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section id="ondra" title="How Ondra replies" description="The rules Ondra checks before every message. It never promises what you haven't allowed.">
            <div className="flex flex-col gap-8">
              <div className="flex items-start justify-between gap-6 rounded-xl border p-4">
                <div>
                  <Label htmlFor="draft-mode" className="flex items-center gap-1.5">
                    <OndraMark className="size-4 text-ai" /> Draft mode
                  </Label>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Ondra writes every reply and waits for your approval. On for your first week; turn it off when you trust the drafts.
                  </p>
                </div>
                <Switch id="draft-mode" checked={draftMode} onCheckedChange={setDraftMode} />
              </div>

              <fieldset>
                <legend className="text-sm font-medium">Prices</legend>
                <RadioGroup value={prices} onValueChange={setPrices} className="mt-3 gap-3">
                  {[
                    ["none", "Don't share prices", "Ondra passes every price question to your team."],
                    ["listed", "Share listed prices", "Ondra can quote the price on your website. Never a final price or a discount."],
                    ["range", "Share a price range", "Ondra can give a range you set per vehicle."],
                  ].map(([v, t, d]) => (
                    <Label key={v} htmlFor={`price-${v}`} className="flex cursor-pointer items-start gap-3 rounded-xl border p-4 font-normal has-data-[state=checked]:border-foreground/40">
                      <RadioGroupItem value={v} id={`price-${v}`} className="mt-0.5" />
                      <span>
                        <span className="block font-medium">{t}</span>
                        <span className="block text-sm text-muted-foreground">{d}</span>
                      </span>
                    </Label>
                  ))}
                </RadioGroup>
              </fieldset>

              <fieldset>
                <legend className="text-sm font-medium">Always hand these to a person</legend>
                <p className="mt-1 text-sm text-muted-foreground">Ondra tells the customer someone will follow up, then passes the conversation on with a brief.</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {HANDOFFS.map((h) => {
                    const on = handoffs.includes(h)
                    return (
                      <button
                        key={h}
                        type="button"
                        aria-pressed={on}
                        onClick={() => setHandoffs((xs) => (on ? xs.filter((x) => x !== h) : [...xs, h]))}
                        className={cn(
                          "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          on ? "border-foreground/40 bg-muted" : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {on && <IconCheck className="size-3.5" aria-hidden="true" />}
                        {h}
                      </button>
                    )
                  })}
                </div>
              </fieldset>
            </div>
          </Section>

          <Section id="vips" title="VIPs" description="VIPs never talk to Ondra. Their calls ring the owner's mobile, and their messages wait for a personal reply.">
            {vips.isPending ? (
              <TableSkeleton rows={2} />
            ) : (vips.data ?? []).length === 0 ? (
              <p className="rounded-xl border p-4 text-sm text-muted-foreground">No VIPs yet. Mark a client as VIP from their profile.</p>
            ) : (
              <ul className="divide-y rounded-xl border" data-vip>
                {(vips.data ?? []).map((c) => (
                  <li key={c.id} className="flex items-center gap-3 px-4 py-3">
                    <IconCrownFilled className="size-4 shrink-0 text-vip" aria-hidden="true" />
                    <span className="flex-1 font-medium">{c.display_name}</span>
                    <span className="text-sm text-muted-foreground">Rings you directly</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section id="channels" title="Channels" description="Customers keep using your existing number, email and WhatsApp. Ondra sits behind them.">
            <ul className="divide-y rounded-xl border">
              {CHANNELS.map((ch) => (
                <li key={ch.name} className="flex flex-wrap items-start gap-x-4 gap-y-1 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{ch.name}</p>
                    <p className="text-sm text-muted-foreground">{ch.detail}</p>
                  </div>
                  <Badge variant="outline" className={cn(ch.ok ? "" : "text-muted-foreground")}>
                    {ch.ok && <IconCheck aria-hidden="true" />}
                    {ch.status}
                  </Badge>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </>
  )
}

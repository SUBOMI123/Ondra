"use client"

/**
 * Settings. One job: set up the dealership, how Ondra behaves and who works here, and have it stick.
 * Every section reads from and saves to the API (GET/PUT /settings, /users). Each section saves on its own with
 * its own Save button, enabled only when something changed. People who can't change settings see them read-only.
 * The section list (desktop) and sticky bar (phones) show which section you're in.
 */

import {
  IconCheck,
  IconCopy,
  IconCrownFilled,
  IconDotsVertical,
  IconMail,
  IconMessage,
  IconBrandWhatsapp,
  IconPlus,
} from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { TableSkeleton } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { useAuth } from "@/components/providers"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { api, send, type Contact, type Page } from "@/lib/api"
import { cn } from "@/lib/utils"

// --- types from the API ----------------------------------------------------------------------------------------

type Day = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"
type Business = { name: string; timezone: string; hours: Record<Day, [string, string] | null> }
type Replies = {
  draft_mode: boolean
  price_disclosure: "none" | "listed" | "range"
  handoff_triggers: string[]
  never_say: string[]
  ai_disclosure: "when_asked" | "upfront"
}
type Channel = { id: string; channel: "sms" | "whatsapp" | "email"; address: string; provider: string; active: boolean; live: boolean }
type SettingsData = { business: Business; replies: Replies; channels: Channel[]; can_edit: boolean; timezones: string[] }
type User = { id: string; email: string; name: string; role: string; active: boolean; invited: boolean }

const SECTIONS = [
  { id: "business", title: "Business" },
  { id: "team", title: "Team" },
  { id: "ondra", title: "How Ondra replies" },
  { id: "vips", title: "VIPs" },
  { id: "channels", title: "Channels" },
]
const SECTION_IDS = SECTIONS.map((s) => s.id)

const DAYS: [Day, string][] = [
  ["mon", "Monday"], ["tue", "Tuesday"], ["wed", "Wednesday"], ["thu", "Thursday"],
  ["fri", "Friday"], ["sat", "Saturday"], ["sun", "Sunday"],
]

const ROLE_LABEL: Record<string, string> = {
  owner: "Owner", admin: "Admin", manager: "Manager", sales: "Sales", service: "Service", ops: "Operations", viewer: "View only",
}

const HANDOFF_PRESETS = ["A discount or final price", "What their trade-in is worth", "A delivery date", "A complaint", "Financing terms"]

const CHANNEL_META = {
  sms: { label: "Text", icon: IconMessage, placeholder: "(214) 555-0100" },
  whatsapp: { label: "WhatsApp", icon: IconBrandWhatsapp, placeholder: "(214) 555-0100" },
  email: { label: "Email", icon: IconMail, placeholder: "sales@yourdealership.com" },
} as const

function formatAddress(c: Pick<Channel, "channel" | "address">) {
  const m = c.address.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return c.channel !== "email" && m ? `(${m[1]}) ${m[2]}-${m[3]}` : c.address
}

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

// --- current section tracking ----------------------------------------------------------------------------------

/** The section the reader is in: the last one whose heading has scrolled past the top third of the screen. */
function useCurrentSection(ids: string[]) {
  const [current, setCurrent] = useState(ids[0])
  // A click on a section link wins until the scroll it started has settled; otherwise a short section near the
  // bottom (VIPs) could never be shown as current, because its heading can't scroll up to the line.
  const clickedAt = useRef(0)
  useEffect(() => {
    const update = () => {
      if (Date.now() - clickedAt.current < 1000) return
      const line = window.innerHeight * 0.33
      let active = ids[0]
      for (const id of ids) {
        const el = document.getElementById(id)
        if (el && el.getBoundingClientRect().top <= line) active = id
      }
      const scroller = document.scrollingElement
      if (scroller && scroller.scrollTop + window.innerHeight >= scroller.scrollHeight - 4) active = ids[ids.length - 1]
      setCurrent(active)
    }
    update()
    window.addEventListener("scroll", update, { passive: true, capture: true })
    window.addEventListener("resize", update)
    // Re-check when the page's height changes (content loading in), not only on scroll.
    const grows = new ResizeObserver(update)
    grows.observe(document.body)
    return () => {
      window.removeEventListener("scroll", update, { capture: true })
      window.removeEventListener("resize", update)
      grows.disconnect()
    }
  }, [ids])
  const choose = useCallback((id: string) => {
    clickedAt.current = Date.now()
    setCurrent(id)
  }, [])
  return [current, choose] as const
}

// --- building blocks -------------------------------------------------------------------------------------------

function Section({ id, title, description, children }: { id: string; title: string; description: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-20 border-b pb-10 last:border-b-0 lg:scroll-mt-6">
      <h2 id={`${id}-h`} className="text-lg font-medium">{title}</h2>
      <p className="mt-1 max-w-prose text-sm text-muted-foreground">{description}</p>
      <div className="mt-6">{children}</div>
    </section>
  )
}

/** Save row for a form section: the button is enabled only when something changed. */
function SaveBar({ dirty, saving, error, onSave, onReset }: {
  dirty: boolean; saving: boolean; error: string | null; onSave: () => void; onReset: () => void
}) {
  return (
    <div className="mt-6 flex flex-wrap items-center gap-3">
      <Button onClick={onSave} disabled={!dirty || saving}>{saving ? "Saving…" : "Save changes"}</Button>
      {dirty && !saving && (
        <Button variant="ghost" onClick={onReset}>Discard</Button>
      )}
      {error && <p role="alert" className="text-sm">{error}</p>}
    </div>
  )
}

// --- Business --------------------------------------------------------------------------------------------------

function BusinessSection({ data, canEdit }: { data: SettingsData; canEdit: boolean }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<Business>(data.business)
  useEffect(() => setForm(data.business), [data.business])
  const dirty = JSON.stringify(form) !== JSON.stringify(data.business)
  const save = useMutation({
    mutationFn: () => send("PUT", "/settings/business", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] })
      toast("Business details saved. Ondra uses the new hours from its next reply.")
    },
  })
  const setDay = (d: Day, span: [string, string] | null) => setForm((f) => ({ ...f, hours: { ...f.hours, [d]: span } }))

  return (
    <Section id="business" title="Business" description="Ondra answers outside these hours, and tells customers when you'll be back.">
      <fieldset disabled={!canEdit} className="grid max-w-xl gap-6">
        <div className="grid gap-2">
          <Label htmlFor="biz-name">Dealership name</Label>
          <Input id="biz-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="biz-tz">Time zone</Label>
          <Select value={form.timezone} onValueChange={(v) => setForm({ ...form, timezone: v })} disabled={!canEdit}>
            <SelectTrigger id="biz-tz" className="w-full sm:w-72"><SelectValue /></SelectTrigger>
            <SelectContent className="max-h-72">
              {data.timezones.map((z) => <SelectItem key={z} value={z}>{z.replace(/_/g, " ")}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <p className="mb-2 text-sm font-medium" id="hours-label">Opening hours</p>
          <ul aria-labelledby="hours-label" className="divide-y rounded-xl border">
            {DAYS.map(([d, label]) => {
              const span = form.hours[d]
              return (
                <li key={d} className="grid grid-cols-[6.5rem_auto_minmax(0,1fr)] items-center gap-3 px-4 py-2.5 text-sm">
                  <span>{label}</span>
                  <Switch
                    checked={!!span}
                    onCheckedChange={(on) => setDay(d, on ? ["09:00", "18:00"] : null)}
                    aria-label={`Open on ${label}`}
                  />
                  {span ? (
                    <span className="flex flex-wrap items-center gap-2">
                      <Input type="time" value={span[0]} aria-label={`${label} opens`} className="w-32"
                        onChange={(e) => setDay(d, [e.target.value, span[1]])} />
                      <span className="text-muted-foreground">to</span>
                      <Input type="time" value={span[1]} aria-label={`${label} closes`} className="w-32"
                        onChange={(e) => setDay(d, [span[0], e.target.value])} />
                    </span>
                  ) : (
                    <span className="text-muted-foreground">Closed</span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      </fieldset>
      {canEdit && (
        <SaveBar dirty={dirty} saving={save.isPending} error={save.isError ? errorText(save.error) : null}
          onSave={() => save.mutate()} onReset={() => { setForm(data.business); save.reset() }} />
      )}
    </Section>
  )
}

// --- Team ------------------------------------------------------------------------------------------------------

function InviteForm({ assignable, onDone }: { assignable: string[]; onDone: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [role, setRole] = useState("sales")
  const [link, setLink] = useState<string | null>(null)
  const invite = useMutation({
    mutationFn: () => send<{ invite_link: string }>("POST", "/users/invite", { name, email, role }),
    onSuccess: (r) => {
      setLink(r.invite_link)
      qc.invalidateQueries({ queryKey: ["users"] })
    },
  })
  if (link) {
    return (
      <div className="rounded-xl border p-4">
        <p className="font-medium">Invite ready for {name}</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Send them this link. It works once and expires in 7 days. Ondra doesn&apos;t email invites yet.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <Input readOnly value={link} aria-label="Invite link" className="font-mono text-xs" onFocus={(e) => e.target.select()} />
          <Button variant="outline" onClick={() => navigator.clipboard.writeText(link).then(() => toast("Link copied"))}>
            <IconCopy /> Copy link
          </Button>
          <Button variant="ghost" onClick={onDone}>Done</Button>
        </div>
      </div>
    )
  }
  return (
    <form
      className="grid gap-4 rounded-xl border p-4 sm:grid-cols-[1fr_1fr_10rem_auto] sm:items-end"
      onSubmit={(e) => { e.preventDefault(); invite.mutate() }}
    >
      <div className="grid gap-2">
        <Label htmlFor="inv-name">Name</Label>
        <Input id="inv-name" required value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="inv-email">Work email</Label>
        <Input id="inv-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="inv-role">Role</Label>
        <Select value={role} onValueChange={setRole}>
          <SelectTrigger id="inv-role" className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>{assignable.map((r) => <SelectItem key={r} value={r}>{ROLE_LABEL[r]}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={invite.isPending}>{invite.isPending ? "Creating…" : "Create invite"}</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
      {invite.isError && <p role="alert" className="text-sm sm:col-span-4">{errorText(invite.error)}</p>}
    </form>
  )
}

function TeamSection() {
  const { me } = useAuth()
  const qc = useQueryClient()
  const [inviting, setInviting] = useState(false)
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<Page<User>>("/users"), retry: false })
  const canManage = me?.role === "owner" || me?.role === "admin"
  const assignable = Object.keys(ROLE_LABEL).filter((r) => r !== "owner" || me?.role === "owner")
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<Pick<User, "role" | "active">> }) => send("PATCH", `/users/${id}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
    onError: (e) => toast(errorText(e)),
  })
  const reinvite = useMutation({
    mutationFn: (id: string) => send<{ invite_link: string }>("POST", `/users/${id}/invite`),
    onSuccess: (r) => navigator.clipboard.writeText(r.invite_link).then(
      () => toast("New invite link copied. The old one no longer works."),
      () => toast(`New invite link: ${r.invite_link}`),
    ),
    onError: (e) => toast(errorText(e)),
  })

  return (
    <Section id="team" title="Team" description="Who works here and what each role can do. VIPs are visible to owners and managers only.">
      {users.isPending ? (
        <TableSkeleton rows={5} />
      ) : users.isError ? (
        <p className="text-sm text-muted-foreground">Only owners, admins and managers can see the team.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {canManage && (inviting ? (
            <InviteForm assignable={assignable} onDone={() => setInviting(false)} />
          ) : (
            <Button variant="outline" className="self-start" onClick={() => setInviting(true)}>
              <IconPlus /> Invite teammate
            </Button>
          ))}
          <ul className="divide-y rounded-xl border">
            {users.data.items.map((u) => {
              const self = u.id === me?.id
              const ownerLocked = u.role === "owner" && me?.role !== "owner"
              const editable = canManage && !self && !ownerLocked && u.active
              return (
                <li key={u.id} className={cn("flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3", !u.active && "text-muted-foreground")}>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {u.name}
                      {self && <span className="font-normal text-muted-foreground"> (you)</span>}
                    </p>
                    <p className="truncate text-sm text-muted-foreground">{u.email}</p>
                  </div>
                  {u.invited && u.active && <Badge variant="outline">Invite sent</Badge>}
                  {!u.active && <Badge variant="outline" className="text-muted-foreground">Deactivated</Badge>}
                  {editable ? (
                    <Select value={u.role} onValueChange={(role) => update.mutate({ id: u.id, patch: { role } })}>
                      <SelectTrigger className="w-36" aria-label={`Role for ${u.name}`}><SelectValue /></SelectTrigger>
                      <SelectContent>{assignable.map((r) => <SelectItem key={r} value={r}>{ROLE_LABEL[r]}</SelectItem>)}</SelectContent>
                    </Select>
                  ) : (
                    <span className="w-36 text-sm text-muted-foreground sm:text-right">{ROLE_LABEL[u.role] ?? u.role}</span>
                  )}
                  {canManage && !self && !ownerLocked ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label={`More for ${u.name}`}><IconDotsVertical /></Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {u.invited && u.active && (
                          <DropdownMenuItem onSelect={() => reinvite.mutate(u.id)}>Copy a new invite link</DropdownMenuItem>
                        )}
                        {u.active ? (
                          <DropdownMenuItem onSelect={() => update.mutate({ id: u.id, patch: { active: false } })}>
                            Deactivate and sign out
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem onSelect={() => update.mutate({ id: u.id, patch: { active: true } })}>Reactivate</DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : canManage ? (
                    <span className="size-9" aria-hidden="true" />
                  ) : null}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </Section>
  )
}

// --- How Ondra replies -----------------------------------------------------------------------------------------

function RepliesSection({ data, canEdit }: { data: SettingsData; canEdit: boolean }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<Replies>(data.replies)
  useEffect(() => setForm(data.replies), [data.replies])
  const dirty = JSON.stringify(form) !== JSON.stringify(data.replies)
  const save = useMutation({
    mutationFn: () => send("PUT", "/settings/replies", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] })
      toast("Saved. Ondra follows these rules from its next reply.")
    },
  })
  const triggers = [...HANDOFF_PRESETS, ...form.handoff_triggers.filter((t) => !HANDOFF_PRESETS.includes(t))]

  return (
    <Section id="ondra" title="How Ondra replies" description="The rules Ondra checks before every message. It never promises what you haven't allowed.">
      <fieldset disabled={!canEdit} className="flex flex-col gap-8">
        <div className="flex items-start justify-between gap-6 rounded-xl border p-4">
          <div>
            <Label htmlFor="draft-mode" className="flex items-center gap-1.5">
              <OndraMark className="size-4 text-ai" /> Draft mode
            </Label>
            <p className="mt-1 text-sm text-muted-foreground">
              Ondra writes every reply and waits for your approval. On for your first week; turn it off when you trust the drafts.
            </p>
          </div>
          <Switch id="draft-mode" checked={form.draft_mode} onCheckedChange={(v) => setForm({ ...form, draft_mode: v })} />
        </div>

        <fieldset>
          <legend className="text-sm font-medium">Prices</legend>
          <RadioGroup value={form.price_disclosure} onValueChange={(v) => setForm({ ...form, price_disclosure: v as Replies["price_disclosure"] })} className="mt-3 gap-3">
            {([
              ["none", "Don't share prices", "Ondra passes every price question to your team."],
              ["listed", "Share listed prices", "Ondra can quote the price on your website. Never a final price or a discount."],
              ["range", "Share a price range", "Ondra gives a rounded range around the listed price."],
            ] as const).map(([v, t, d]) => (
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
            {triggers.map((h) => {
              const on = form.handoff_triggers.includes(h)
              return (
                <button
                  key={h}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setForm({ ...form, handoff_triggers: on ? form.handoff_triggers.filter((x) => x !== h) : [...form.handoff_triggers, h] })}
                  className={cn(
                    "flex min-h-9 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed",
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

        <fieldset>
          <legend className="text-sm font-medium">Telling customers it&apos;s AI</legend>
          <RadioGroup value={form.ai_disclosure} onValueChange={(v) => setForm({ ...form, ai_disclosure: v as Replies["ai_disclosure"] })} className="mt-3 gap-3">
            {([
              ["when_asked", "When they ask", "Ondra never claims to be a person, and says it's your AI assistant whenever asked."],
              ["upfront", "In its first reply", "For states that require it. Ondra says it's your AI assistant when a conversation starts."],
            ] as const).map(([v, t, d]) => (
              <Label key={v} htmlFor={`disc-${v}`} className="flex cursor-pointer items-start gap-3 rounded-xl border p-4 font-normal has-data-[state=checked]:border-foreground/40">
                <RadioGroupItem value={v} id={`disc-${v}`} className="mt-0.5" />
                <span>
                  <span className="block font-medium">{t}</span>
                  <span className="block text-sm text-muted-foreground">{d}</span>
                </span>
              </Label>
            ))}
          </RadioGroup>
        </fieldset>
      </fieldset>
      {canEdit && (
        <SaveBar dirty={dirty} saving={save.isPending} error={save.isError ? errorText(save.error) : null}
          onSave={() => save.mutate()} onReset={() => { setForm(data.replies); save.reset() }} />
      )}
    </Section>
  )
}

// --- VIPs ------------------------------------------------------------------------------------------------------

function VipsSection() {
  const vips = useQuery({
    queryKey: ["contacts", "vips"],
    queryFn: async () => (await api<Page<Contact>>("/contacts?limit=200")).items.filter((c) => c.is_vip),
  })
  return (
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
  )
}

// --- Channels --------------------------------------------------------------------------------------------------

function AddChannelForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [channel, setChannel] = useState<Channel["channel"]>("sms")
  const [address, setAddress] = useState("")
  const add = useMutation({
    mutationFn: () => send<Channel>("POST", "/settings/channels", { channel, address }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] })
      toast("Connected. Messages to it now reach Ondra.")
      onDone()
    },
  })
  return (
    <form className="grid gap-4 rounded-xl border p-4 sm:grid-cols-[10rem_1fr_auto] sm:items-end"
      onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
      <div className="grid gap-2">
        <Label htmlFor="ch-kind">Channel</Label>
        <Select value={channel} onValueChange={(v) => setChannel(v as Channel["channel"])}>
          <SelectTrigger id="ch-kind" className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {(Object.keys(CHANNEL_META) as Channel["channel"][]).map((k) => <SelectItem key={k} value={k}>{CHANNEL_META[k].label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="ch-address">{channel === "email" ? "Your email address" : "Your number"}</Label>
        <Input id="ch-address" required value={address} onChange={(e) => setAddress(e.target.value)}
          placeholder={CHANNEL_META[channel].placeholder} type={channel === "email" ? "email" : "tel"} />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={add.isPending}>{add.isPending ? "Connecting…" : "Connect"}</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
      {add.isError && <p role="alert" className="text-sm sm:col-span-3">{errorText(add.error)}</p>}
    </form>
  )
}

function ChannelsSection({ data, canEdit }: { data: SettingsData; canEdit: boolean }) {
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const patch = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => send("PATCH", `/settings/channels/${id}`, { active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
    onError: (e) => toast(errorText(e)),
  })
  const remove = useMutation({
    mutationFn: (id: string) => send("DELETE", `/settings/channels/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
    onError: (e) => toast(errorText(e)),
  })

  return (
    <Section id="channels" title="Channels"
      description="Your existing number, WhatsApp and email. Customers keep using them; messages to them reach Ondra while they're on.">
      <div className="flex flex-col gap-4">
        {data.channels.length === 0 ? (
          <p className="rounded-xl border p-4 text-sm text-muted-foreground">Nothing connected yet. Connect your number or sales email to start.</p>
        ) : (
          <ul className="divide-y rounded-xl border">
            {data.channels.map((c) => {
              const meta = CHANNEL_META[c.channel]
              return (
                <li key={c.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
                  <meta.icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{meta.label}</p>
                    <p className="truncate text-sm text-muted-foreground tabular-nums">{formatAddress(c)}</p>
                  </div>
                  <Badge variant="outline" className="text-muted-foreground">
                    {c.live ? "Live" : "Test mode"}
                  </Badge>
                  <Switch checked={c.active} disabled={!canEdit || patch.isPending}
                    onCheckedChange={(active) => patch.mutate({ id: c.id, active })}
                    aria-label={`${meta.label} ${formatAddress(c)} reaches Ondra`} />
                  {canEdit && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label={`More for ${meta.label} ${formatAddress(c)}`}><IconDotsVertical /></Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => remove.mutate(c.id)}>Disconnect</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </li>
              )
            })}
          </ul>
        )}
        {data.channels.some((c) => !c.live) && (
          <p className="max-w-prose text-sm text-muted-foreground">
            Test mode: messages are simulated, nothing reaches real customers. Each channel goes live once its provider
            account is set up: Meta for WhatsApp, Twilio for texts, Postmark for email.
          </p>
        )}
        {canEdit && (adding ? (
          <AddChannelForm onDone={() => setAdding(false)} />
        ) : (
          <Button variant="outline" className="self-start" onClick={() => setAdding(true)}><IconPlus /> Connect a channel</Button>
        ))}
        <p className="max-w-prose text-sm text-muted-foreground">Phone calls connect with voice, in a later update.</p>
      </div>
    </Section>
  )
}

// --- page ------------------------------------------------------------------------------------------------------

function NavLinks({ current, choose, variant }: { current: string; choose: (id: string) => void; variant: "list" | "bar" }) {
  return SECTIONS.map((s) => (
    <li key={s.id} className={variant === "bar" ? "shrink-0" : undefined}>
      <a
        href={`#${s.id}`}
        onClick={() => choose(s.id)}
        aria-current={current === s.id ? "location" : undefined}
        className={cn(
          "text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring aria-[current=location]:bg-muted aria-[current=location]:font-medium aria-[current=location]:text-foreground",
          variant === "list" ? "block rounded-md px-2 py-1.5 hover:bg-muted" : "flex min-h-11 items-center rounded-full px-3",
        )}
      >
        {s.title}
      </a>
    </li>
  ))
}

export default function SettingsPage() {
  const [current, choose] = useCurrentSection(SECTION_IDS)
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api<SettingsData>("/settings") })
  const phoneBar = useRef<HTMLUListElement>(null)
  useEffect(() => {
    // Keep the current section's chip visible in the phone bar (it scrolls sideways at narrow widths).
    const chip = phoneBar.current?.querySelector<HTMLElement>("[aria-current=location]")
    const bar = phoneBar.current
    if (chip && bar) bar.scrollTo({ left: chip.offsetLeft - bar.clientWidth / 2 + chip.clientWidth / 2, behavior: "smooth" })
  }, [current])
  const canEdit = settings.data?.can_edit ?? false

  return (
    <>
      <SiteHeader title="Settings" note={settings.data && !canEdit ? "View only. Owners and admins can change these." : undefined} />
      {/* Phones and tablets: the sections as a sticky bar, so you always know where you are. */}
      <nav aria-label="Settings sections" className="sticky top-0 z-10 border-b bg-background px-4 lg:hidden">
        <ul ref={phoneBar} className="relative flex gap-1 overflow-x-auto py-2 text-sm [scrollbar-width:none]">
          <NavLinks current={current} choose={choose} variant="bar" />
        </ul>
      </nav>
      <div className="mx-auto grid w-full max-w-5xl gap-10 px-4 py-6 lg:grid-cols-[11rem_minmax(0,1fr)] lg:px-6">
        <nav aria-label="Settings sections" className="hidden lg:block">
          <ul className="sticky top-6 flex flex-col gap-1 text-sm">
            <NavLinks current={current} choose={choose} variant="list" />
          </ul>
        </nav>

        <div className="flex min-w-0 flex-col gap-10">
          {settings.isPending ? (
            <div className="flex flex-col gap-4" aria-label="Loading settings">
              <Skeleton className="h-7 w-40" />
              <Skeleton className="h-10 w-full max-w-xl" />
              <Skeleton className="h-80 w-full max-w-xl" />
            </div>
          ) : settings.isError ? (
            <div role="alert" className="rounded-xl border p-4 text-sm">
              <p>Settings didn&apos;t load. {errorText(settings.error)}</p>
              <Button variant="outline" className="mt-3" onClick={() => settings.refetch()}>Try again</Button>
            </div>
          ) : (
            <>
              <BusinessSection data={settings.data} canEdit={canEdit} />
              <TeamSection />
              <RepliesSection data={settings.data} canEdit={canEdit} />
              <VipsSection />
              <ChannelsSection data={settings.data} canEdit={canEdit} />
            </>
          )}
        </div>
      </div>
    </>
  )
}

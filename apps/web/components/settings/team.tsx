"use client"

/**
 * The team: invite, roles, mobiles, deactivation. Shared by the Settings summary and the Team page
 * (/settings/team). Roles are Ondra's (admin, manager, sales, service); with Clerk they're mirrored onto
 * the Clerk Organization, but Ondra's are what's enforced.
 */

import { IconCopy, IconDotsVertical } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import type { Me } from "@/lib/api"
import { api, CLERK, send } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"

type Day = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"
type Hours = Partial<Record<Day, [string, string] | null>>
export type User = {
  id: string; email: string; name: string; role: string; active: boolean; invited: boolean; phone: string | null
  /** Their own working hours and time zone (null: the dealership's), and a limit on open tasks (null: none). */
  work_hours: Hours | null; timezone: string | null; max_open_tasks: number | null
}
export type TeamData = { items: User[]; total: number; counts: { role: Record<string, number>; status: Record<"active" | "invited" | "deactivated", number> } }

export const ROLE_LABEL: Record<string, string> = {
  admin: "Admin", manager: "Manager", sales: "Sales", service: "Service", ops: "Operations", viewer: "View only",
}

export function canManageTeam(me: Me | null) {
  return me?.role === "admin"
}

export function assignableRoles(me: Me | null) {
  return me?.role === "admin" ? Object.keys(ROLE_LABEL) : []
}

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

export function InviteForm({ assignable, onDone }: { assignable: string[]; onDone: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [role, setRole] = useState("sales")
  const [link, setLink] = useState<string | null>(null)
  const invite = useMutation({
    mutationFn: () => send<{ invite_link?: string; emailed?: boolean }>("POST", "/users/invite", { name, email, role }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["users"] })
      if (r.invite_link) {
        setLink(r.invite_link)
      } else {
        // Clerk emails the invitation; nothing to copy.
        toast(`Invitation emailed to ${email}.`)
        onDone()
      }
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

function formatPhone(e164: string | null) {
  const m = e164?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : (e164 ?? "")
}

/** A person's mobile: where Ondra rings them to put a call through. Edited inline. */
function Mobile({ u, self, canEdit }: { u: User; self: boolean; canEdit: boolean }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(u.phone ?? "")
  const save = useMutation({
    mutationFn: () => (self ? send("PATCH", "/me", { phone: value }) : send("PATCH", `/users/${u.id}`, { phone: value })),
    onSuccess: () => {
      setEditing(false)
      qc.invalidateQueries({ queryKey: ["users"] })
      toast(value.trim() ? "Mobile saved." : "Mobile removed.")
    },
  })
  if (editing)
    return (
      <form className="mt-1.5 flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
        <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="(214) 555-0100" inputMode="tel" aria-label={`Mobile for ${u.name}`} className="h-8 w-44" autoFocus />
        <Button size="sm" type="submit" disabled={save.isPending}>Save</Button>
        <Button size="sm" variant="ghost" type="button" onClick={() => { setEditing(false); setValue(u.phone ?? "") }}>Cancel</Button>
        {save.isError && <p role="alert" className="w-full text-sm">{errorText(save.error)}</p>}
      </form>
    )
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <span className="whitespace-nowrap tabular-nums">{u.phone ? formatPhone(u.phone) : "No mobile"}</span>
      {canEdit && (
        <button type="button" className="underline-offset-4 hover:text-foreground hover:underline" onClick={() => setEditing(true)} aria-label={`${u.phone ? "Change" : "Add"} mobile for ${u.name}`}>
          {u.phone ? "Change" : "Add mobile"}
        </button>
      )}
    </p>
  )
}

const DAYS: [Day, string][] = [
  ["mon", "Monday"], ["tue", "Tuesday"], ["wed", "Wednesday"], ["thu", "Thursday"], ["fri", "Friday"], ["sat", "Saturday"], ["sun", "Sunday"],
]
const WEEKDAYS: Hours = { mon: ["09:00", "18:00"], tue: ["09:00", "18:00"], wed: ["09:00", "18:00"], thu: ["09:00", "18:00"], fri: ["09:00", "18:00"] }

/** When a person works and how much they can hold. Decides who new work goes to (Settings > Who gets what). */
function HoursForm({ u, onDone }: { u: User; onDone: () => void }) {
  const qc = useQueryClient()
  const zones = useQuery({ queryKey: ["settings"], queryFn: () => api<{ timezones: string[]; business: { timezone: string } }>("/settings") })
  const [own, setOwn] = useState(u.work_hours != null)
  const [hours, setHours] = useState<Hours>(u.work_hours ?? WEEKDAYS)
  const [tz, setTz] = useState(u.timezone ?? "")
  const [limit, setLimit] = useState(u.max_open_tasks ? String(u.max_open_tasks) : "")
  const zone = tz || zones.data?.business.timezone || ""
  const save = useMutation({
    mutationFn: () => send("PATCH", `/users/${u.id}`, {
      work_hours: own ? hours : null, ...(own ? { timezone: zone || null } : {}), max_open_tasks: limit.trim() ? Number(limit) : null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["users"] }); toast(`Saved. New work for ${u.name.split(" ")[0]} follows this from now.`); onDone() },
  })
  return (
    <form className="grid gap-6 px-4 pb-6" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
      <div className="flex items-start gap-3">
        <Switch id="own-hours" checked={own} onCheckedChange={setOwn} className="mt-0.5" />
        <div className="grid gap-1">
          <Label htmlFor="own-hours">Works their own hours</Label>
          <p className="text-sm text-muted-foreground">Off: they follow the dealership&apos;s opening hours.</p>
        </div>
      </div>
      {own && (
        <>
          <div className="grid gap-2">
            <Label htmlFor="own-tz">Their time zone</Label>
            <Select value={zone} onValueChange={setTz}>
              <SelectTrigger id="own-tz" className="w-full"><SelectValue placeholder="Choose a time zone" /></SelectTrigger>
              <SelectContent>{(zones.data?.timezones ?? (zone ? [zone] : [])).map((z) => <SelectItem key={z} value={z}>{z.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">Hours below are in this time zone, so someone in Lagos can cover a Dallas night.</p>
          </div>
          <ul className="divide-y rounded-xl border" aria-label="Working days">
            {DAYS.map(([d, label]) => {
              const span = hours[d]
              return (
                <li key={d} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
                  <Switch checked={!!span} onCheckedChange={(on) => setHours({ ...hours, [d]: on ? ["09:00", "18:00"] : null })} aria-label={`Works ${label}`} />
                  <span className="w-24 text-sm">{label}</span>
                  {span ? (
                    <span className="flex items-center gap-2">
                      <Input type="time" value={span[0]} aria-label={`${label} starts`} className="w-32" onChange={(e) => setHours({ ...hours, [d]: [e.target.value, span[1]] })} />
                      <span className="text-sm text-muted-foreground">to</span>
                      <Input type="time" value={span[1]} aria-label={`${label} finishes`} className="w-32" onChange={(e) => setHours({ ...hours, [d]: [span[0], e.target.value] })} />
                    </span>
                  ) : (
                    <span className="text-sm text-muted-foreground">Off</span>
                  )}
                </li>
              )
            })}
          </ul>
        </>
      )}
      <div className="grid gap-2">
        <Label htmlFor="own-limit">Most open tasks at once</Label>
        <Input id="own-limit" inputMode="numeric" pattern="[0-9]*" value={limit} onChange={(e) => setLimit(e.target.value.replace(/\D/g, ""))} placeholder="No limit" className="w-32" />
        <p className="text-sm text-muted-foreground">At the limit, new work goes to a teammate. Leave empty for no limit.</p>
      </div>
      {save.isError && <p role="alert" className="text-sm">{errorText(save.error)}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save hours and limit"}</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  )
}

/** The people in `users`, each with their role and actions. */
export function TeamRows({ users, me }: { users: User[]; me: Me | null }) {
  const [hoursFor, setHoursFor] = useState<string | null>(null)
  const qc = useQueryClient()
  const canManage = canManageTeam(me)
  const assignable = assignableRoles(me)
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<Pick<User, "role" | "active">> }) => send("PATCH", `/users/${id}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
    onError: (e) => toast(errorText(e)),
  })
  const reinvite = useMutation({
    mutationFn: (id: string) => send<{ invite_link?: string; emailed?: boolean }>("POST", `/users/${id}/invite`),
    onSuccess: (r) => !r.invite_link ? toast("Invitation emailed again.") : navigator.clipboard.writeText(r.invite_link).then(
      () => toast("New invite link copied. The old one no longer works."),
      () => toast(`New invite link: ${r.invite_link}`),
    ),
    onError: (e) => toast(errorText(e)),
  })

  const hoursUser = users.find((u) => u.id === hoursFor)
  return (
    <>
    <Sheet open={!!hoursUser} onOpenChange={(o) => !o && setHoursFor(null)}>
      <SheetContent className="overflow-y-auto">
        {hoursUser && (
          <>
            <SheetHeader>
              <SheetTitle>{hoursUser.name}&apos;s hours and workload</SheetTitle>
              <SheetDescription>New messages, calls and handoffs go to people who are in and under their limit.</SheetDescription>
            </SheetHeader>
            <HoursForm key={hoursUser.id} u={hoursUser} onDone={() => setHoursFor(null)} />
          </>
        )}
      </SheetContent>
    </Sheet>
    <ul className="divide-y rounded-xl border">
{users.map((u) => {
        const self = u.id === me?.id
        const editable = canManage && !self && u.active
        return (
          <li key={u.id} className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5", !u.active && "text-muted-foreground")}>
            {/* Name and email, then the mobile: its own column on wider screens so each person is two lines. */}
            <div className="min-w-0 basis-full sm:basis-0 sm:flex-1 md:grid md:grid-cols-[minmax(0,1fr)_12rem] md:items-center md:gap-4">
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {u.name}
                  {self && <span className="font-normal text-muted-foreground"> (you)</span>}
                </p>
                <p className="truncate text-sm text-muted-foreground" title={u.email}>{u.email}</p>
              </div>
              <Mobile u={u} self={self} canEdit={self || (canManage && u.active)} />
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
            {canManage && (u.active || !self) ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label={`More for ${u.name}`}><IconDotsVertical /></Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {u.active && <DropdownMenuItem onSelect={() => setHoursFor(u.id)}>Hours and workload</DropdownMenuItem>}
                  {u.invited && u.active && (
                    <DropdownMenuItem onSelect={() => reinvite.mutate(u.id)}>{CLERK ? "Email the invitation again" : "Copy a new invite link"}</DropdownMenuItem>
                  )}
                  {self ? null : u.active ? (
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
    </>
  )
}

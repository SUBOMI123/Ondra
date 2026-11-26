"use client"

/**
 * The team: invite, roles, mobiles, deactivation. Shared by the Settings summary and the Team page
 * (/settings/team). Roles are Ondra's (owner, admin, manager, sales, service); with Clerk they're mirrored onto
 * the Clerk Organization, but Ondra's are what's enforced.
 */

import { IconCopy, IconDotsVertical } from "@tabler/icons-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import type { Me } from "@/lib/api"
import { CLERK, send } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"

export type User = { id: string; email: string; name: string; role: string; active: boolean; invited: boolean; phone: string | null }
export type TeamData = { items: User[]; total: number; counts: { role: Record<string, number>; status: Record<"active" | "invited" | "deactivated", number> } }

export const ROLE_LABEL: Record<string, string> = {
  owner: "Owner", admin: "Admin", manager: "Manager", sales: "Sales", service: "Service", ops: "Operations", viewer: "View only",
}

export function canManageTeam(me: Me | null) {
  return me?.role === "owner" || me?.role === "admin"
}

export function assignableRoles(me: Me | null) {
  return Object.keys(ROLE_LABEL).filter((r) => r !== "owner" || me?.role === "owner")
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

/** The people in `users`, each with their role and actions. */
export function TeamRows({ users, me }: { users: User[]; me: Me | null }) {
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

  return (
    <ul className="divide-y rounded-xl border">
{users.map((u) => {
        const self = u.id === me?.id
        const ownerLocked = u.role === "owner" && me?.role !== "owner"
        const editable = canManage && !self && !ownerLocked && u.active
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
              <Mobile u={u} self={self} canEdit={self || (canManage && !ownerLocked && u.active)} />
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
                    <DropdownMenuItem onSelect={() => reinvite.mutate(u.id)}>{CLERK ? "Email the invitation again" : "Copy a new invite link"}</DropdownMenuItem>
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
  )
}

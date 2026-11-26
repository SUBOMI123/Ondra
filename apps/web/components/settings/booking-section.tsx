"use client"

/**
 * Settings > Booking. One job: decide what customers can book, how long it takes, and who or what it needs.
 * Appointment types (from a template or from scratch) and the bays and loaners they use. Ondra offers only these.
 */

import { IconPlus } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { TableSkeleton } from "@/components/list-states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { api, send } from "@/lib/api"
import { cn } from "@/lib/utils"

type ApptType = {
  id: string
  name: string
  description: string | null
  category: string
  duration_min: number
  buffer_min: number
  eligible_roles: string[]
  required_resource_kinds: string[]
  min_notice_min: number
  max_days_ahead: number
  reminder_schedule: number[]
  active: boolean
}
type Template = Omit<ApptType, "id" | "active"> & { key: string }
type Res = { id: string; kind: "service_bay" | "loaner" | "demo_vehicle" | "room"; name: string; active: boolean }

const ROLE_LABEL: Record<string, string> = { sales: "Sales", service: "Service", manager: "Managers", ops: "Operations", owner: "Owner" }
const KIND_LABEL: Record<Res["kind"], string> = { service_bay: "Service bay", loaner: "Loaner", demo_vehicle: "Demo car", room: "Room" }
const REMINDERS: [number, string][] = [[1440, "The day before"], [120, "2 hours before"]]

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

function summary(t: Pick<ApptType, "duration_min" | "eligible_roles" | "required_resource_kinds">) {
  const who = t.eligible_roles.map((r) => ROLE_LABEL[r] ?? r).join(" or ")
  const bay = t.required_resource_kinds.includes("service_bay") ? ", needs a bay" : ""
  return `${t.duration_min} min, ${who || "anyone"}${bay}`
}

/* ------------------------------------------------------------ type form (add or edit) */

type Draft = {
  name: string
  description: string
  duration_min: number
  buffer_min: number
  eligible_roles: string[]
  needs_bay: boolean
  min_notice_min: number
  reminder_schedule: number[]
}

function toDraft(t?: Partial<ApptType>): Draft {
  return {
    name: t?.name ?? "",
    description: t?.description ?? "",
    duration_min: t?.duration_min ?? 30,
    buffer_min: t?.buffer_min ?? 0,
    eligible_roles: t?.eligible_roles ?? ["sales"],
    needs_bay: (t?.required_resource_kinds ?? []).includes("service_bay"),
    min_notice_min: t?.min_notice_min ?? 60,
    reminder_schedule: t?.reminder_schedule ?? [1440, 120],
  }
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        "min-h-9 rounded-full border px-3 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
        on ? "border-foreground/40 bg-muted" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}

function TypeForm({ initial, templates, onSave, onCancel, saving, error, isNew }: {
  initial: Draft
  templates?: Template[]
  onSave: (d: Draft, template: string | null) => void
  onCancel: () => void
  saving: boolean
  error: string | null
  isNew: boolean
}) {
  const [d, setD] = useState<Draft>(initial)
  const [template, setTemplate] = useState<string>("custom")
  const toggle = (xs: number[] | string[], x: never) => ((xs as never[]).includes(x) ? (xs as never[]).filter((y) => y !== x) : [...xs, x])
  return (
    <form
      className="grid gap-5 rounded-xl border p-4"
      onSubmit={(e) => {
        e.preventDefault()
        onSave(d, template === "custom" ? null : template)
      }}
    >
      {isNew && templates && (
        <div className="grid gap-2 sm:max-w-xs">
          <Label htmlFor="type-template">Start from</Label>
          <Select
            value={template}
            onValueChange={(v) => {
              setTemplate(v)
              const tpl = templates.find((x) => x.key === v)
              if (tpl) setD(toDraft(tpl))
            }}
          >
            <SelectTrigger id="type-template" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="custom">Blank, my own</SelectItem>
              {templates.map((t) => <SelectItem key={t.key} value={t.key}>{t.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-[1fr_8rem_8rem]">
        <div className="grid gap-2">
          <Label htmlFor="type-name">Name customers see</Label>
          <Input id="type-name" required value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} placeholder="EV charging walkthrough" />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="type-duration">Minutes</Label>
          <Input id="type-duration" type="number" min={10} max={480} step={5} value={d.duration_min}
            onChange={(e) => setD({ ...d, duration_min: Number(e.target.value) })} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="type-buffer">Gap after</Label>
          <Input id="type-buffer" type="number" min={0} max={240} step={5} value={d.buffer_min}
            onChange={(e) => setD({ ...d, buffer_min: Number(e.target.value) })} />
        </div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="type-desc">What it is</Label>
        <Input id="type-desc" value={d.description} onChange={(e) => setD({ ...d, description: e.target.value })}
          placeholder="Ondra uses this to decide when to offer it" />
      </div>
      <fieldset>
        <legend className="text-sm font-medium">Who takes it</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {["sales", "service", "manager"].map((r) => (
            <Chip key={r} on={d.eligible_roles.includes(r)} onClick={() => setD({ ...d, eligible_roles: toggle(d.eligible_roles, r as never) as string[] })}>
              {ROLE_LABEL[r]}
            </Chip>
          ))}
        </div>
      </fieldset>
      <div className="flex items-start justify-between gap-6">
        <div>
          <Label htmlFor="type-bay">Needs a service bay</Label>
          <p className="mt-1 text-sm text-muted-foreground">Ondra only offers times when a bay is free too.</p>
        </div>
        <Switch id="type-bay" checked={d.needs_bay} onCheckedChange={(v) => setD({ ...d, needs_bay: v })} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="type-notice">Earliest booking</Label>
          <Select value={String(d.min_notice_min)} onValueChange={(v) => setD({ ...d, min_notice_min: Number(v) })}>
            <SelectTrigger id="type-notice" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="0">Any time</SelectItem>
              <SelectItem value="60">An hour from now</SelectItem>
              <SelectItem value="120">Two hours from now</SelectItem>
              <SelectItem value="1440">Tomorrow onwards</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <fieldset>
          <legend className="text-sm font-medium">Reminders</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {REMINDERS.map(([m, label]) => (
              <Chip key={m} on={d.reminder_schedule.includes(m)} onClick={() => setD({ ...d, reminder_schedule: toggle(d.reminder_schedule, m as never) as number[] })}>
                {label}
              </Chip>
            ))}
          </div>
        </fieldset>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={saving || !d.name.trim() || d.eligible_roles.length === 0}>
          {saving ? "Saving…" : isNew ? "Add appointment type" : "Save changes"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
        {d.eligible_roles.length === 0 && <p className="text-sm text-muted-foreground">Choose who takes it.</p>}
        {error && <p role="alert" className="text-sm">{error}</p>}
      </div>
    </form>
  )
}

function body(d: Draft) {
  return {
    name: d.name.trim(),
    description: d.description.trim() || null,
    duration_min: d.duration_min,
    buffer_min: d.buffer_min,
    eligible_roles: d.eligible_roles,
    required_resource_kinds: d.needs_bay ? ["service_bay"] : [],
    min_notice_min: d.min_notice_min,
    reminder_schedule: d.reminder_schedule,
  }
}

/* ------------------------------------------------------------ section */

export function BookingSection({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient()
  const types = useQuery({ queryKey: ["appointment-types"], queryFn: () => api<{ items: ApptType[] }>("/appointment-types") })
  const templates = useQuery({ queryKey: ["appointment-templates"], queryFn: () => api<{ items: Template[] }>("/appointment-types/templates"), enabled: canEdit })
  const resources = useQuery({ queryKey: ["resources"], queryFn: () => api<{ items: Res[] }>("/resources") })
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [newRes, setNewRes] = useState<{ kind: Res["kind"]; name: string } | null>(null)
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["appointment-types"] })
    qc.invalidateQueries({ queryKey: ["resources"] })
  }

  const create = useMutation({
    mutationFn: ({ d, template }: { d: Draft; template: string | null }) => send("POST", "/appointment-types", { ...body(d), ...(template ? { template } : {}) }),
    onSuccess: () => { refresh(); setAdding(false); toast("Added. Ondra can offer it from now on.") },
  })
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: object }) => send("PATCH", `/appointment-types/${id}`, patch),
    onSuccess: () => { refresh(); setEditing(null) },
    onError: (e) => toast(errorText(e)),
  })
  const addRes = useMutation({
    mutationFn: (r: { kind: Res["kind"]; name: string }) => send("POST", "/resources", r),
    onSuccess: () => { refresh(); setNewRes(null) },
    onError: (e) => toast(errorText(e)),
  })
  const patchRes = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => send("PATCH", `/resources/${id}`, { active }),
    onSuccess: refresh,
    onError: (e) => toast(errorText(e)),
  })

  return (
    <section id="booking" aria-labelledby="booking-h" className="scroll-mt-20 border-b pb-10 last:border-b-0 lg:scroll-mt-6">
      <h2 id="booking-h" className="text-lg font-medium">Booking</h2>
      <p className="mt-1 max-w-prose text-sm text-muted-foreground">
        What customers can book with Ondra, how long it takes, and who or what it needs. Ondra only offers times when the right person and bay are free.
      </p>

      <div className="mt-6 flex flex-col gap-4">
        <h3 className="text-sm font-medium">Appointment types</h3>
        {types.isPending ? (
          <TableSkeleton rows={4} />
        ) : types.isError ? (
          <p className="text-sm">Appointment types didn&apos;t load. {errorText(types.error)}</p>
        ) : (
          <ul className="divide-y rounded-xl border">
            {types.data.items.map((t) => (
              <li key={t.id} className="px-4 py-3">
                {editing === t.id ? (
                  <TypeForm
                    initial={toDraft(t)}
                    isNew={false}
                    saving={update.isPending}
                    error={update.isError ? errorText(update.error) : null}
                    onCancel={() => setEditing(null)}
                    onSave={(d) => update.mutate({ id: t.id, patch: body(d) })}
                  />
                ) : (
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                    <div className={cn("min-w-0 flex-1", !t.active && "text-muted-foreground")}>
                      <p className="font-medium">{t.name}</p>
                      <p className="truncate text-sm text-muted-foreground">{summary(t)}</p>
                    </div>
                    {canEdit && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => setEditing(t.id)} aria-label={`Edit ${t.name}`}>Edit</Button>
                        <Switch checked={t.active} onCheckedChange={(active) => update.mutate({ id: t.id, patch: { active } })}
                          aria-label={`Customers can book ${t.name}`} />
                      </>
                    )}
                    {!canEdit && !t.active && <span className="text-sm text-muted-foreground">Off</span>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        {canEdit && (adding ? (
          <TypeForm
            initial={toDraft()}
            templates={templates.data?.items}
            isNew
            saving={create.isPending}
            error={create.isError ? errorText(create.error) : null}
            onCancel={() => { setAdding(false); create.reset() }}
            onSave={(d, template) => create.mutate({ d, template })}
          />
        ) : (
          <Button variant="outline" className="self-start" onClick={() => setAdding(true)}><IconPlus /> Add appointment type</Button>
        ))}

        <h3 className="mt-4 text-sm font-medium">Bays and loaners</h3>
        {resources.isPending ? (
          <TableSkeleton rows={3} />
        ) : (
          <ul className="divide-y rounded-xl border">
            {(resources.data?.items ?? []).map((r) => (
              <li key={r.id} className="flex items-center gap-4 px-4 py-2.5">
                <span className={cn("flex-1 font-medium", !r.active && "text-muted-foreground")}>{r.name}</span>
                <span className="text-sm text-muted-foreground">{KIND_LABEL[r.kind]}</span>
                <Switch checked={r.active} disabled={!canEdit} onCheckedChange={(active) => patchRes.mutate({ id: r.id, active })}
                  aria-label={`${r.name} can be booked`} />
              </li>
            ))}
          </ul>
        )}
        {canEdit && (newRes ? (
          <form className="grid gap-3 rounded-xl border p-4 sm:grid-cols-[10rem_1fr_auto] sm:items-end"
            onSubmit={(e) => { e.preventDefault(); addRes.mutate(newRes) }}>
            <div className="grid gap-2">
              <Label htmlFor="res-kind">Kind</Label>
              <Select value={newRes.kind} onValueChange={(v) => setNewRes({ ...newRes, kind: v as Res["kind"] })}>
                <SelectTrigger id="res-kind" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="service_bay">Service bay</SelectItem>
                  <SelectItem value="loaner">Loaner</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="res-name">Name</Label>
              <Input id="res-name" required value={newRes.name} onChange={(e) => setNewRes({ ...newRes, name: e.target.value })} placeholder="Bay 4" />
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={addRes.isPending}>Add</Button>
              <Button type="button" variant="ghost" onClick={() => setNewRes(null)}>Cancel</Button>
            </div>
          </form>
        ) : (
          <Button variant="outline" className="self-start" onClick={() => setNewRes({ kind: "service_bay", name: "" })}><IconPlus /> Add a bay or loaner</Button>
        ))}
      </div>
    </section>
  )
}

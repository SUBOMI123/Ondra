"use client"

/**
 * Settings > Follow-ups. One job: decide when the dealership checks back with a customer who went quiet, what is
 * said, and whether a person approves it first. Plus the hours no follow-up is ever sent in.
 * What Ondra writes is marked in Ondra blue; nothing here can reach a VIP or someone who opted out.
 */

import { IconDotsVertical, IconPlus } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { api, send } from "@/lib/api"
import { cn } from "@/lib/utils"

type Topic = "sales" | "service" | "shipping" | "finance" | "complaint" | "other"
type Step = { after_hours: number; write: "ondra" | "text"; text: string; require_approval: boolean }
type Sequence = { id: string; name: string; active: boolean; topics: Topic[]; steps: Step[] }
type Data = {
  sequences: Sequence[]
  quiet_hours: { start: string; end: string }
  scheduled: number
  awaiting_approval: number
  draft_mode: boolean
  can_edit: boolean
}
type Draft = Omit<Sequence, "id">

const TOPICS: [Topic, string][] = [["sales", "Sales"], ["service", "Service"], ["shipping", "Shipping"], ["finance", "Finance"], ["other", "Anything else"]]
const STARTER: Draft = {
  name: "Quiet buyers",
  active: true,
  topics: ["sales"],
  steps: [
    { after_hours: 24, write: "ondra", text: "", require_approval: true },
    { after_hours: 72, write: "ondra", text: "", require_approval: true },
  ],
}

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

function wait(hours: number) {
  if (hours % 24 === 0) return hours === 24 ? "1 day" : `${hours / 24} days`
  return hours === 1 ? "1 hour" : `${hours} hours`
}

function clock(hhmm: string) {
  const [h, m] = hhmm.split(":").map(Number)
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, "0")}` : ""} ${h < 12 ? "am" : "pm"}`
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

/** One step as a line: "After 1 day, Ondra writes it. Someone approves it first." */
function StepLine({ s, n, draftMode }: { s: Step; n: number; draftMode: boolean }) {
  const approve = s.require_approval || draftMode
  return (
    <li className="text-sm">
      <span className="text-muted-foreground">{n === 0 ? "After" : "Then after"} {wait(s.after_hours)} of silence, </span>
      {s.write === "ondra" ? (
        <span data-slot="ai-note" className="inline-flex items-center gap-1 text-ai">
          <OndraMark className="size-3.5 shrink-0" />
          Ondra writes a check-in.
        </span>
      ) : (
        <span>your message is sent: &ldquo;{s.text}&rdquo;</span>
      )}{" "}
      <span className="text-muted-foreground">{approve ? "Someone approves it first." : "It sends without approval."}</span>
    </li>
  )
}

/* ------------------------------------------------------------ sequence form (add or edit) */

function SequenceForm({ initial, isNew, saving, error, onSave, onCancel }: {
  initial: Draft; isNew: boolean; saving: boolean; error: string | null; onSave: (d: Draft) => void; onCancel: () => void
}) {
  const [d, setD] = useState<Draft>(initial)
  const setStep = (i: number, patch: Partial<Step>) => setD({ ...d, steps: d.steps.map((s, j) => (j === i ? { ...s, ...patch } : s)) })
  const flip = (t: Topic) => setD({ ...d, topics: d.topics.includes(t) ? d.topics.filter((x) => x !== t) : [...d.topics, t] })
  return (
    <form className="grid gap-5 rounded-xl border p-4" onSubmit={(e) => { e.preventDefault(); onSave(d) }} aria-label={isNew ? "New follow-up sequence" : "Edit follow-up sequence"}>
      <div className="grid gap-2 sm:max-w-sm">
        <Label htmlFor="seq-name">Name</Label>
        <Input id="seq-name" required value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} placeholder="Quiet buyers" />
      </div>
      <fieldset className="grid gap-2">
        <legend className="text-sm font-medium">For conversations about</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {TOPICS.map(([t, label]) => <Chip key={t} on={d.topics.includes(t)} onClick={() => flip(t)}>{label}</Chip>)}
        </div>
        <p className="text-sm text-muted-foreground">Leave them all off for any conversation. Complaints never get an automatic follow-up.</p>
      </fieldset>
      <ol className="grid gap-4">
        {d.steps.map((s, i) => {
          const days = s.after_hours % 24 === 0
          return (
            <li key={i} className="grid gap-3 border-t pt-4">
              <div className="flex flex-wrap items-end gap-3">
                <div className="grid gap-2">
                  <Label htmlFor={`seq-wait-${i}`}>{i === 0 ? "After they've been quiet for" : "Then, after another"}</Label>
                  <div className="flex gap-2">
                    <Input id={`seq-wait-${i}`} inputMode="numeric" className="w-20" value={String(days ? s.after_hours / 24 : s.after_hours)}
                      onChange={(e) => { const n = Math.max(1, Number(e.target.value.replace(/\D/g, "")) || 1); setStep(i, { after_hours: days ? n * 24 : n }) }} />
                    <Select value={days ? "days" : "hours"} onValueChange={(u) => { const n = days ? s.after_hours / 24 : s.after_hours; setStep(i, { after_hours: u === "days" ? n * 24 : n }) }}>
                      <SelectTrigger className="w-28" aria-label="Hours or days"><SelectValue /></SelectTrigger>
                      <SelectContent><SelectItem value="hours">hours</SelectItem><SelectItem value="days">days</SelectItem></SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid min-w-48 flex-1 gap-2">
                  <Label htmlFor={`seq-write-${i}`}>What&apos;s sent</Label>
                  <Select value={s.write} onValueChange={(w) => setStep(i, { write: w as Step["write"] })}>
                    <SelectTrigger id={`seq-write-${i}`} className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ondra">Ondra writes it from the conversation</SelectItem>
                      <SelectItem value="text">A message I write once</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {d.steps.length > 1 && (
                  <Button type="button" variant="ghost" size="sm" onClick={() => setD({ ...d, steps: d.steps.filter((_, j) => j !== i) })}>Remove</Button>
                )}
              </div>
              {s.write === "text" ? (
                <div className="grid gap-2">
                  <Label htmlFor={`seq-text-${i}`}>Message</Label>
                  <Textarea id={`seq-text-${i}`} required maxLength={600} rows={2} value={s.text} onChange={(e) => setStep(i, { text: e.target.value })}
                    placeholder="Hi {first_name}, it's {dealership}. Still looking for the right car? Happy to help when you're ready." />
                  <p className="text-sm text-muted-foreground">{"{first_name}"} and {"{dealership}"} are filled in for you. No prices or offers: those need a person.</p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Ondra reads the conversation and writes one short check-in. It never mentions a price, an offer or a date, and it sends nothing if there&apos;s nothing useful to say.</p>
              )}
              <div className="flex items-center gap-3">
                <Switch id={`seq-approve-${i}`} checked={s.require_approval} onCheckedChange={(v) => setStep(i, { require_approval: v })} />
                <Label htmlFor={`seq-approve-${i}`} className="font-normal">Someone approves it in the Inbox before it goes</Label>
              </div>
            </li>
          )
        })}
      </ol>
      {d.steps.length < 6 && (
        <Button type="button" variant="outline" size="sm" className="justify-self-start"
          onClick={() => setD({ ...d, steps: [...d.steps, { after_hours: 72, write: "ondra", text: "", require_approval: true }] })}>
          <IconPlus /> Add another follow-up
        </Button>
      )}
      {error && <p role="alert" className="text-sm">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>{saving ? "Saving…" : isNew ? "Add sequence" : "Save sequence"}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  )
}

/* ------------------------------------------------------------ quiet hours */

function QuietHours({ value, canEdit }: { value: Data["quiet_hours"]; canEdit: boolean }) {
  const qc = useQueryClient()
  const [form, setForm] = useState(value)
  useEffect(() => {
    setForm(value)
  }, [value])
  const dirty = form.start !== value.start || form.end !== value.end
  const save = useMutation({
    mutationFn: () => send("PUT", "/follow-ups/quiet-hours", form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["follow-ups"] }); toast(`Quiet hours saved: nothing from ${clock(form.start)} to ${clock(form.end)}.`) },
  })
  return (
    <div className="grid gap-2">
      <p className="text-sm font-medium" id="quiet-label">Quiet hours</p>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-labelledby="quiet-label">
        <span className="text-sm text-muted-foreground">No follow-ups from</span>
        <Input type="time" className="w-32" aria-label="Quiet hours start" value={form.start} disabled={!canEdit} onChange={(e) => setForm({ ...form, start: e.target.value })} />
        <span className="text-sm text-muted-foreground">to</span>
        <Input type="time" className="w-32" aria-label="Quiet hours end" value={form.end} disabled={!canEdit} onChange={(e) => setForm({ ...form, end: e.target.value })} />
        {dirty && <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "Saving…" : "Save quiet hours"}</Button>}
      </div>
      <p className="text-sm text-muted-foreground">In the dealership&apos;s time. A follow-up that falls due inside them waits until they end. Replies to a customer who just wrote in aren&apos;t held back.</p>
      {save.isError && <p role="alert" className="text-sm">{errorText(save.error)}</p>}
    </div>
  )
}

/* ------------------------------------------------------------ section */

export function FollowUpsSection() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ["follow-ups"], queryFn: () => api<Data>("/follow-ups") })
  const [editing, setEditing] = useState<string | "new" | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ["follow-ups"] })
  const save = useMutation({
    mutationFn: ({ id, d }: { id: string | "new"; d: Draft }) => (id === "new" ? send("POST", "/follow-ups", d) : send("PUT", `/follow-ups/${id}`, d)),
    onSuccess: (_r, v) => { setEditing(null); refresh(); toast(v.id === "new" ? "Sequence added. It starts with the next reply that goes out." : "Sequence saved.") },
  })
  const change = useMutation({
    mutationFn: (job: { kind: "switch"; s: Sequence; active: boolean } | { kind: "delete"; s: Sequence }) =>
      job.kind === "switch" ? send("PUT", `/follow-ups/${job.s.id}`, { ...job.s, active: job.active }) : send("DELETE", `/follow-ups/${job.s.id}`),
    onSuccess: (_r, job) => { refresh(); if (job.kind === "delete") toast(`Deleted "${job.s.name}" and the follow-ups it had lined up.`) },
    onError: (e) => toast(errorText(e)),
  })

  if (q.isPending) return <Skeleton className="h-32 w-full" />
  if (q.isError)
    return (
      <div role="alert" className="rounded-xl border p-4 text-sm">
        <p className="font-medium">Couldn&apos;t load follow-ups</p>
        <p className="mt-1 text-muted-foreground">{q.error.message}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => q.refetch()}>Try again</Button>
      </div>
    )
  const data = q.data
  const canEdit = data.can_edit
  return (
    <div className="flex flex-col gap-6">
      {(data.scheduled > 0 || data.awaiting_approval > 0) && (
        <p className="text-sm">
          <span className="tabular-nums">{data.scheduled}</span> lined up
          {data.awaiting_approval > 0 && (
            <>, <Link href="/inbox" className="underline underline-offset-4"><span className="tabular-nums">{data.awaiting_approval}</span> waiting for approval in the Inbox</Link></>
          )}
          .
        </p>
      )}
      {data.draft_mode && data.sequences.length > 0 && (
        <p className="text-sm text-muted-foreground">Ondra is set to draft only (How Ondra replies), so every follow-up waits for approval whatever is set below.</p>
      )}

      {data.sequences.length === 0 && editing !== "new" ? (
        <div className="rounded-xl border p-4 text-sm">
          <p className="font-medium">No follow-ups yet</p>
          <p className="mt-1 max-w-prose text-muted-foreground">When a customer stops replying, nothing more is sent. A sequence checks back with them, once or a few times, and stops the moment they answer.</p>
          {canEdit && (
            <Button className="mt-3" onClick={() => { save.reset(); setEditing("new") }}>
              <IconPlus /> Set up a follow-up
            </Button>
          )}
        </div>
      ) : (
        <ul className="grid gap-3">
          {data.sequences.map((s) =>
            editing === s.id ? (
              <li key={s.id}>
                <SequenceForm initial={s} isNew={false} saving={save.isPending} error={save.isError ? errorText(save.error) : null}
                  onSave={(d) => save.mutate({ id: s.id, d })} onCancel={() => setEditing(null)} />
              </li>
            ) : (
              <li key={s.id} className="rounded-xl border p-4">
                <div className="flex items-start gap-3">
                  <div className={cn("min-w-0 flex-1", !s.active && "text-muted-foreground")}>
                    <p className="font-medium">{s.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {s.topics.length ? `For ${s.topics.map((t) => TOPICS.find((x) => x[0] === t)?.[1].toLowerCase() ?? t).join(", ")} conversations` : "For any conversation"}
                      {!s.active && ". Switched off: nothing new is lined up."}
                    </p>
                  </div>
                  {canEdit && (
                    <>
                      <Switch checked={s.active} onCheckedChange={(active) => change.mutate({ kind: "switch", s, active })} aria-label={`${s.name} is ${s.active ? "on" : "off"}`} className="mt-0.5" />
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="-my-1.5 -mr-2" aria-label={`More for ${s.name}`}><IconDotsVertical /></Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onSelect={() => { save.reset(); setEditing(s.id) }}>Edit</DropdownMenuItem>
                          <DropdownMenuItem onSelect={() => change.mutate({ kind: "delete", s })}>Delete &ldquo;{s.name}&rdquo;</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </>
                  )}
                </div>
                <ol className={cn("mt-3 grid gap-1.5", !s.active && "opacity-60")}>
                  {s.steps.map((st, i) => <StepLine key={i} s={st} n={i} draftMode={data.draft_mode} />)}
                </ol>
              </li>
            ),
          )}
          {editing === "new" && (
            <li>
              <SequenceForm initial={STARTER} isNew saving={save.isPending} error={save.isError ? errorText(save.error) : null}
                onSave={(d) => save.mutate({ id: "new", d })} onCancel={() => setEditing(null)} />
            </li>
          )}
        </ul>
      )}
      {canEdit && data.sequences.length > 0 && editing === null && (
        <Button variant="outline" className="self-start" onClick={() => { save.reset(); setEditing("new") }}>
          <IconPlus /> Add a sequence
        </Button>
      )}

      <QuietHours value={data.quiet_hours} canEdit={canEdit} />
      <p className="max-w-prose text-sm text-muted-foreground">
        Follow-ups never go to VIPs or to anyone who has opted out. By text or WhatsApp they go only to customers with consent on file; for anyone else, a person gets a task to follow up instead.
      </p>
    </div>
  )
}

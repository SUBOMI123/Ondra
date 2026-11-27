"use client"

/**
 * Settings > Your WhatsApp assistant. One job: decide when Ondra messages the owner on WhatsApp, and show whether
 * it can actually reach them. The owner's own setting: only an owner can change it.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { api, send } from "@/lib/api"

type Data = {
  briefing_on: boolean
  briefing_time: string
  alerts_on: boolean
  owners: { name: string; has_mobile: boolean }[]
  whatsapp: { address: string; live: boolean } | null
  templates: { name: string; text: string }[]
  can_edit: boolean
}
type Form = Pick<Data, "briefing_on" | "briefing_time" | "alerts_on">

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

function clock(hhmm: string) {
  const [h, m] = hhmm.split(":").map(Number)
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`
}

function list(names: string[]) {
  return names.length <= 1 ? (names[0] ?? "") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

export function OwnerAssistantSection() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ["owner-assistant"], queryFn: () => api<Data>("/settings/owner-assistant") })
  const [form, setForm] = useState<Form | null>(null)
  useEffect(() => {
    if (q.data) setForm({ briefing_on: q.data.briefing_on, briefing_time: q.data.briefing_time, alerts_on: q.data.alerts_on })
  }, [q.data])
  const save = useMutation({
    mutationFn: (f: Form) => send("PUT", "/settings/owner-assistant", f),
    onSuccess: (_r, f) => {
      qc.invalidateQueries({ queryKey: ["owner-assistant"] })
      toast(f.briefing_on ? `Saved. Your briefing arrives at ${clock(f.briefing_time)}, dealership time.` : "Saved. The morning briefing is off.")
    },
  })
  const now = useMutation({
    mutationFn: () => send<{ sent: number; owners: number }>("POST", "/settings/owner-assistant/briefing"),
    onSuccess: (r) => toast(r.owners === 1 ? "Sent. Check your WhatsApp." : `Sent to ${r.sent} of ${r.owners} owners.`),
    onError: (e) => toast(errorText(e)),
  })

  if (q.isPending || (q.data && !form)) return <Skeleton className="h-40 w-full" />
  if (q.isError || !form)
    return (
      <div role="alert" className="rounded-xl border p-4 text-sm">
        <p className="font-medium">Couldn&apos;t load this</p>
        <p className="mt-1 text-muted-foreground">{q.isError ? q.error.message : ""}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => q.refetch()}>Try again</Button>
      </div>
    )
  const d = q.data
  const canEdit = d.can_edit
  const reachable = d.owners.filter((o) => o.has_mobile).map((o) => o.name)
  const missing = d.owners.filter((o) => !o.has_mobile).map((o) => o.name)
  const dirty = form.briefing_on !== d.briefing_on || form.briefing_time !== d.briefing_time || form.alerts_on !== d.alerts_on
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-1.5 text-sm">
        <p>
          {reachable.length > 0 ? `Messages go to ${list(reachable)}, on the mobile set under Team.` : "No owner has a mobile on file yet, so there's nobody to message."}
          {missing.length > 0 && ` ${list(missing)} ${missing.length === 1 ? "has" : "have"} no mobile on file.`}{" "}
          <Link href="/settings/team" className="underline underline-offset-4">Set mobiles under Team</Link>
        </p>
        {d.whatsapp === null ? (
          <p>Your dealership has no WhatsApp number yet. <Link href="/settings#channels" className="underline underline-offset-4">Add one under Channels</Link>: the assistant sends from it, and it&apos;s the number you write to.</p>
        ) : !d.whatsapp.live ? (
          <p className="text-muted-foreground">Your WhatsApp number is in test mode, so nothing reaches a real phone yet.</p>
        ) : null}
        {!canEdit && <p className="text-muted-foreground">Only an owner can change this: it&apos;s their own phone.</p>}
      </div>

      <div className="grid gap-4">
        <div className="flex items-start gap-3">
          <Switch id="oa-briefing" checked={form.briefing_on} disabled={!canEdit} className="mt-0.5" onCheckedChange={(v) => setForm({ ...form, briefing_on: v })} />
          <div className="grid gap-1">
            <Label htmlFor="oa-briefing">Morning briefing</Label>
            <p className="text-sm text-muted-foreground">One message each morning: VIPs waiting, hot leads, drafts to approve, overdue tasks and today&apos;s appointments.</p>
          </div>
        </div>
        {form.briefing_on && (
          <div className="grid gap-2 pl-11">
            <Label htmlFor="oa-time">Send it at</Label>
            <Input id="oa-time" type="time" className="w-32" value={form.briefing_time} disabled={!canEdit} onChange={(e) => setForm({ ...form, briefing_time: e.target.value })} />
            <p className="text-sm text-muted-foreground">In the dealership&apos;s time zone, every day.</p>
          </div>
        )}
        <div className="flex items-start gap-3">
          <Switch id="oa-alerts" checked={form.alerts_on} disabled={!canEdit} className="mt-0.5" onCheckedChange={(v) => setForm({ ...form, alerts_on: v })} />
          <div className="grid gap-1">
            <Label htmlFor="oa-alerts">Tell me straight away when a VIP is waiting</Label>
            <p className="text-sm text-muted-foreground">A VIP writes or calls and nobody has answered: you get a message at once, and again if they&apos;re still waiting.</p>
          </div>
        </div>
      </div>
      {save.isError && <p role="alert" className="text-sm">{errorText(save.error)}</p>}
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => save.mutate(form)} disabled={!dirty || save.isPending || !form.briefing_time}>{save.isPending ? "Saving…" : "Save changes"}</Button>
          <Button variant="outline" onClick={() => now.mutate()} disabled={now.isPending || dirty}>{now.isPending ? "Sending…" : "Send me today's briefing now"}</Button>
        </div>
      )}

      <div className="grid gap-1.5 text-sm">
        <p className="font-medium">What you can send it</p>
        <p className="max-w-prose text-muted-foreground">
          Message your dealership&apos;s WhatsApp number from your own mobile, typed or as a voice note. &ldquo;Sarah King wants the white Highlander now, budget forty,
          have Daniel call her tomorrow.&rdquo; &ldquo;Who asked about a G63?&rdquo; &ldquo;What&apos;s waiting on me?&rdquo; It updates the client, creates the task and tells you
          what it did. It can send a reply Ondra already drafted when you say so, and it never messages a customer on its own.
        </p>
      </div>

      <details className="text-sm">
        <summary className="cursor-pointer font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">Before the first briefing: two WhatsApp templates to get approved</summary>
        <div className="mt-2 grid gap-2 text-muted-foreground">
          <p className="max-w-prose">WhatsApp only lets a business start a conversation with a message it has approved. If you haven&apos;t written to the assistant in the last 24 hours, the briefing and alerts use these. They need adding to your WhatsApp Business account, with these names:</p>
          <ul className="grid gap-2">
            {d.templates.map((t) => (
              <li key={t.name}><span className="font-mono text-foreground">{t.name}</span><br />{t.text}</li>
            ))}
          </ul>
        </div>
      </details>
    </div>
  )
}

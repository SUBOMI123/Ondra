"use client"

/**
 * Settings > Who gets what > When a VIP's call isn't answered. One job: decide what a VIP hears when their person
 * doesn't pick up, in the dealer's own words, and what they can press. Never the AI (docs/PLAN.md item 3).
 * The preview shows the message exactly as it will be said, with the options that will actually be offered.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { VipTag } from "@/components/vip"
import { api, send } from "@/lib/api"

type VipCalls = { message: string | null; backup_number: string | null; booking_link: string | null; default_message: string; live: boolean; can_edit: boolean }
type Form = { message: string; backup_number: string; booking_link: string }

function preview(f: Form, fallback: string) {
  let text = (f.message.trim() || fallback).replaceAll("{first}", "Robert").replaceAll("{person}", "Daniel").replaceAll("{dealer}", "Prestige Motors")
  if (f.backup_number.trim()) text += " If it's urgent, press 1."
  if (f.booking_link.trim()) text += " To book a time yourself, press 2 and we'll text you a link."
  return text
}

export function VipCallsSection() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ["vip-calls"], queryFn: () => api<VipCalls>("/settings/vip-calls") })
  const [f, setF] = useState<Form | null>(null)
  useEffect(() => {
    if (q.data) setF({ message: q.data.message ?? "", backup_number: q.data.backup_number ?? "", booking_link: q.data.booking_link ?? "" })
  }, [q.data])
  const save = useMutation({
    mutationFn: (v: Form) => send<VipCalls>("PUT", "/settings/vip-calls", v),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["vip-calls"] }); toast("Saved.") },
  })

  return (
    <section aria-labelledby="vip-calls" className="flex flex-col gap-4 border-t pt-8" data-vip>
      <div className="flex flex-col gap-1">
        <h2 id="vip-calls" className="flex items-center gap-2 text-base font-medium"><VipTag /> When a VIP&apos;s call isn&apos;t answered</h2>
        <p className="max-w-prose text-sm text-muted-foreground">
          Their person&apos;s phone rings for 20 seconds. If nobody picks up, they hear this, in your words, never Ondra. Their person is told straight away and gets a call-back task.
        </p>
      </div>
      {q.isPending || !f ? <Skeleton className="h-64 w-full rounded-xl" /> : q.isError ? (
        <p role="alert" className="text-sm">{q.error.message}</p>
      ) : (
        <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); save.mutate(f) }}>
          {!q.data.live && (
            <p className="rounded-lg border px-3 py-2.5 text-sm">
              Not playing yet: until your phone line is connected through Ondra&apos;s VIP desk, a VIP&apos;s call is put straight through to their person, with no message if they don&apos;t answer.
            </p>
          )}
          <div className="grid gap-2">
            <Label htmlFor="vip-message">What they hear</Label>
            <Textarea id="vip-message" rows={3} maxLength={400} disabled={!q.data.can_edit} value={f.message}
              placeholder={q.data.default_message} onChange={(e) => setF({ ...f, message: e.target.value })} />
            <p className="text-xs text-muted-foreground">{"{first}"} is their first name, {"{person}"} the first name of whoever looks after them. Leave it empty to use the message shown.</p>
          </div>
          <div className="grid items-start gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="vip-backup">Press 1 rings</Label>
              <Input id="vip-backup" inputMode="tel" disabled={!q.data.can_edit} value={f.backup_number} placeholder="(214) 555-0199"
                onChange={(e) => setF({ ...f, backup_number: e.target.value })} />
              <p className="text-xs text-muted-foreground">One phone a person answers: the front desk&apos;s direct line or a manager&apos;s mobile. Not your main number, which Ondra answers. Empty: no press 1.</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="vip-link">Press 2 texts this booking link</Label>
              <Input id="vip-link" inputMode="url" disabled={!q.data.can_edit} value={f.booking_link} placeholder="https://yourdealership.com/book"
                onChange={(e) => setF({ ...f, booking_link: e.target.value })} />
              <p className="text-xs text-muted-foreground">Your website&apos;s online booking page. Only offered to VIPs who have agreed to texts. Empty: no press 2.</p>
            </div>
          </div>
          <div className="rounded-lg bg-muted/50 px-4 py-3 text-sm">
            <p className="mb-1 text-xs text-muted-foreground">Robert, looked after by Daniel, would hear:</p>
            <p className="text-pretty">&ldquo;{preview(f, q.data.default_message)}&rdquo;</p>
          </div>
          {save.isError && <p role="alert" className="text-sm">{save.error instanceof Error ? save.error.message : "Couldn't save."}</p>}
          {q.data.can_edit && <Button type="submit" className="self-start" disabled={save.isPending}>Save</Button>}
        </form>
      )}
    </section>
  )
}

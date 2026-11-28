"use client"

/**
 * New message. One job: write to a client first, on the channel they use, without hunting for their thread.
 * Pick the client, pick a channel (the ones that can't be used say why: no number, not connected, WhatsApp's 24-hour
 * rule), write, send. It goes through the same send path as every reply (opt-outs block it) into the client's thread
 * on that channel, which then belongs to whoever wrote. Data: GET /search (clients), GET /contacts/{id}/write-options,
 * POST /conversations/start.
 */

import { IconArrowLeft, IconBrandWhatsapp, IconMail, IconMessage, IconSend } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { VipTag } from "@/components/vip"
import { api, send } from "@/lib/api"
import { cn } from "@/lib/utils"

export type ComposeTo = { id: string; name: string; is_vip?: boolean }
type Option = { channel: "whatsapp" | "sms" | "email"; available: boolean; why: string | null }
type WriteOptions = { contact: ComposeTo; opted_out: boolean; channels: Option[] }

const CHANNEL = {
  whatsapp: { label: "WhatsApp", Icon: IconBrandWhatsapp, by: "on WhatsApp" },
  sms: { label: "Text", Icon: IconMessage, by: "by text" },
  email: { label: "Email", Icon: IconMail, by: "by email" },
} as const

function phone(v: string | null) {
  const m = v?.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : v
}

function PickClient({ onPick }: { onPick: (c: ComposeTo) => void }) {
  const [text, setText] = useState("")
  const [q, setQ] = useState("")
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 200)
    return () => clearTimeout(t)
  }, [text])
  const found = useQuery({
    queryKey: ["search", q], enabled: q.length > 0,
    queryFn: () => api<{ clients: { id: string; name: string; is_vip: boolean; detail: string | null }[] }>(`/search?q=${encodeURIComponent(q)}`),
  })
  return (
    <div className="flex flex-col gap-3">
      <Label htmlFor="compose-to">To</Label>
      <Input id="compose-to" autoFocus value={text} onChange={(e) => setText(e.target.value)} placeholder="Client's name or phone number" autoComplete="off" />
      {q && (found.isPending ? (
        <div className="flex flex-col gap-2" aria-label="Searching"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div>
      ) : found.data?.clients.length ? (
        <ul className="divide-y rounded-lg border">
          {found.data.clients.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => onPick(c)} data-vip={c.is_vip || undefined}
                className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm outline-none hover:bg-muted/60 focus-visible:bg-muted">
                {c.is_vip && <VipTag />}<span className="truncate font-medium">{c.name}</span>
                {c.detail && <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">{phone(c.detail)}</span>}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">No client matches &ldquo;{q}&rdquo;. New messages go to clients already in Ondra.</p>
      ))}
    </div>
  )
}

function Write({ to, onBack, onSent }: { to: ComposeTo; onBack: () => void; onSent: () => void }) {
  const qc = useQueryClient()
  const router = useRouter()
  const opts = useQuery({ queryKey: ["write-options", to.id], queryFn: () => api<WriteOptions>(`/contacts/${to.id}/write-options`) })
  const [channel, setChannel] = useState<Option["channel"] | null>(null)
  const [body, setBody] = useState("")
  const [error, setError] = useState<string | null>(null)
  const usable = opts.data?.channels.filter((o) => o.available) ?? []
  const chosen = channel ?? usable[0]?.channel ?? null
  const first = to.name.split(" ")[0]

  const sendIt = useMutation({
    mutationFn: () => send<{ conversation_id: string }>("POST", "/conversations/start", { contact_id: to.id, channel: chosen, body }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["conversations"] })
      toast(`Sent to ${first} ${CHANNEL[chosen!].by}.`, { action: { label: "Open", onClick: () => router.push(`/inbox?c=${r.conversation_id}`) } })
      onSent()
    },
    onError: (e) => setError(e instanceof Error ? e.message : "That didn't send. Try again."),
  })

  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (chosen && body.trim()) sendIt.mutate() }}>
      <div className="flex items-center gap-2 text-sm">
        <Button type="button" variant="ghost" size="icon" className="-ml-2 size-8" onClick={onBack} aria-label="Choose someone else"><IconArrowLeft /></Button>
        <span className="text-muted-foreground">To</span>
        <span className="flex items-center gap-1.5 font-medium">{to.is_vip && <VipTag />}{to.name}</span>
      </div>

      {opts.isPending ? (
        <Skeleton className="h-9 w-full" />
      ) : opts.isError ? (
        <p className="text-sm text-muted-foreground">Couldn&apos;t load {first}&apos;s details. Try again.</p>
      ) : opts.data!.opted_out ? (
        <p className="rounded-lg border px-3 py-2.5 text-sm">{first} opted out, so nothing can be sent to them on any channel.</p>
      ) : (
        <>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Send by</legend>
            <div className="flex flex-wrap gap-2" role="radiogroup">
              {opts.data!.channels.map((o) => {
                const { label, Icon } = CHANNEL[o.channel]
                return (
                  <button key={o.channel} type="button" role="radio" aria-checked={chosen === o.channel} disabled={!o.available}
                    onClick={() => setChannel(o.channel)}
                    className={cn("flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
                      chosen === o.channel ? "border-foreground bg-foreground text-background" : "hover:bg-muted")}>
                    <Icon className="size-4" aria-hidden="true" />{label}
                  </button>
                )
              })}
            </div>
            {opts.data!.channels.filter((o) => !o.available).map((o) => (
              <p key={o.channel} className="text-xs text-muted-foreground">{CHANNEL[o.channel].label}: {o.why}.</p>
            ))}
          </fieldset>
          {usable.length === 0 ? (
            <p className="text-sm text-muted-foreground">There&apos;s no way to write to {first} right now. Add a phone number or email on their profile.</p>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                <Label htmlFor="compose-body">Message</Label>
                <Textarea id="compose-body" value={body} onChange={(e) => { setBody(e.target.value); setError(null) }}
                  placeholder={`Hi ${first}, `} rows={5} maxLength={4000} autoFocus />
                {error && <p className="text-sm" role="alert">{error}</p>}
              </div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">Goes into {first}&apos;s conversation. You&apos;ll see their reply in the Inbox.</p>
                <Button type="submit" disabled={!body.trim() || !chosen || sendIt.isPending}><IconSend /> Send</Button>
              </div>
            </>
          )}
        </>
      )}
    </form>
  )
}

export function ComposeDialog({ open, onOpenChange, to }: { open: boolean; onOpenChange: (o: boolean) => void; to?: ComposeTo | null }) {
  const [picked, setPicked] = useState<ComposeTo | null>(null)
  useEffect(() => { if (open) setPicked(to ?? null) }, [open, to])
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New message</DialogTitle>
          <DialogDescription>Write to a client on WhatsApp, by text or by email.</DialogDescription>
        </DialogHeader>
        {picked ? (
          <Write key={picked.id} to={picked} onBack={() => setPicked(null)} onSent={() => onOpenChange(false)} />
        ) : (
          <PickClient onPick={setPicked} />
        )}
      </DialogContent>
    </Dialog>
  )
}

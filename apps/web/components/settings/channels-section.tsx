"use client"

/** Settings > Channels. One job: which of the dealership's own numbers and addresses reach Ondra, and whether each is live. */

import { IconBrandWhatsapp, IconDotsVertical, IconMail, IconMessage, IconPhone, IconPlus } from "@tabler/icons-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { type Channel, errorText, type SettingsData } from "@/components/settings/shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { send } from "@/lib/api"

export const CHANNEL_META = {
  sms: { label: "Text", icon: IconMessage, placeholder: "(214) 555-0100" },
  whatsapp: { label: "WhatsApp", icon: IconBrandWhatsapp, placeholder: "(214) 555-0100" },
  email: { label: "Email", icon: IconMail, placeholder: "sales@yourdealership.com" },
  phone: { label: "Calls", icon: IconPhone, placeholder: "(214) 555-0100" },
} as const

function formatAddress(c: Pick<Channel, "channel" | "address">) {
  const m = c.address.match(/^\+1(\d{3})(\d{3})(\d{4})$/)
  return c.channel !== "email" && m ? `(${m[1]}) ${m[2]}-${m[3]}` : c.address
}

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

export function ChannelsSection({ data, canEdit }: { data: SettingsData; canEdit: boolean }) {
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
    <>
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
        <p className="max-w-prose text-sm text-muted-foreground">
          For calls, forward your number to Ondra at your phone carrier, always or when nobody picks up. Ondra answers
          on it, and VIPs ring you directly.
        </p>
      </div>
    </>
  )
}

"use client"

/**
 * Making a client a VIP, from their profile. Admins and managers only (they're the people who can see VIPs).
 * Becoming a VIP changes what happens to them at once, so the confirm step says exactly that, in a sentence each.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { useAuth } from "@/components/providers"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { api, send, type Contact } from "@/lib/api"

type Person = { id: string; name: string; role: string }

export function useCanMakeVip() {
  const { me } = useAuth()
  return me?.role === "admin" || me?.role === "manager"
}

/** The button sits with the profile's actions; the panel opens on its own row below the header. */
export function VipButton({ c, onOpen }: { c: Contact; onOpen: () => void }) {
  if (!useCanMakeVip()) return null
  return (
    <Button variant="outline" onClick={onOpen}>
      {c.is_vip ? "VIP settings" : "Make VIP"}
    </Button>
  )
}

export function VipPanel({ c, onClose }: { c: Contact; onClose: () => void }) {
  const qc = useQueryClient()
  const canChoose = useCanMakeVip()
  const people = useQuery({
    queryKey: ["users", "active-list"],
    queryFn: () => api<{ items: (Person & { active: boolean; invited: boolean })[] }>("/users?status=active&limit=100"),
    enabled: canChoose,
  })
  const { me } = useAuth()
  // Every VIP has a person. It starts as whoever is making them a VIP.
  const [handler, setHandler] = useState<string>(c.vip_owner_user_id ?? me?.id ?? "")
  const save = useMutation({
    mutationFn: (vip: boolean) => send<Contact>("PUT", `/contacts/${c.id}/vip`, { vip, handler_user_id: vip && handler ? handler : null }),
    onSuccess: (_r, vip) => {
      onClose()
      qc.invalidateQueries({ queryKey: ["contact", c.id] })
      qc.invalidateQueries({ queryKey: ["contacts"] })
      qc.invalidateQueries({ queryKey: ["conversations"] })
      toast(vip ? `${c.display_name} is now a VIP. Ondra won't reply to them.` : `${c.display_name} is no longer a VIP.`)
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't save. Try again."),
  })
  if (!canChoose) return null
  const first = c.display_name.split(" ")[0]

  return (
    <div className="grid w-full gap-4 rounded-xl border p-4 sm:max-w-md" role="group" aria-label={c.is_vip ? "VIP settings" : "Make VIP"}>
      {!c.is_vip && (
        <ul className="grid gap-1 text-sm">
          <li>Ondra stops replying to {first}, and any draft or follow-up waiting for them is dropped.</li>
          <li>Their calls ring a person directly.</li>
          <li>Only admins, managers and the person below can see them.</li>
        </ul>
      )}
      <div className="grid gap-2">
        <Label htmlFor="vip-handler">Who looks after {first}</Label>
        <Select value={handler} onValueChange={setHandler}>
          <SelectTrigger id="vip-handler" className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {(people.data?.items ?? []).map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => save.mutate(true)} disabled={save.isPending}>{c.is_vip ? "Save" : `Make ${first} a VIP`}</Button>
        {c.is_vip && <Button variant="outline" onClick={() => save.mutate(false)} disabled={save.isPending}>No longer a VIP</Button>}
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
      </div>
    </div>
  )
}

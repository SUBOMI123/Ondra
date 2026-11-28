"use client"

/**
 * A client's name on their profile, editable. One job: get the name right. A name Ondra heard on a phone call is
 * flagged ("as Ondra heard it on a call") because speech recognition misspells names; a person fixes it or confirms
 * it, and Ondra never overwrites a name a person saved. The flag is grey, not Ondra-blue: it's a prompt to check,
 * and it can sit on a VIP's profile, where nothing blue may appear.
 */

import { IconPencil } from "@tabler/icons-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { VipTag } from "@/components/vip"
import { send, type Contact } from "@/lib/api"

export function ContactName({ c }: { c: Contact }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(c.display_name)
  const save = useMutation({
    mutationFn: (display_name: string) => send<Contact>("PATCH", `/contacts/${c.id}`, { display_name }),
    onSuccess: (r, sent) => {
      qc.setQueryData(["contact", c.id], (old: Contact | undefined) => (old ? { ...old, ...r } : r))
      qc.invalidateQueries({ queryKey: ["contacts"] })
      qc.invalidateQueries({ queryKey: ["conversations"] })
      setEditing(false)
      toast(sent === c.display_name ? "Name confirmed." : `Saved as ${r.display_name}.`)
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't save the name."),
  })
  const placeholder = c.display_name.startsWith("+") || c.display_name.includes("@")

  if (editing) {
    return (
      <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim()) save.mutate(name) }}>
        <label htmlFor="client-name" className="sr-only">Client&apos;s name</label>
        <Input id="client-name" autoFocus value={name} maxLength={200} onChange={(e) => setName(e.target.value)} className="h-10 w-72 max-w-full text-lg" />
        <Button type="submit" disabled={!name.trim() || save.isPending}>Save</Button>
        <Button type="button" variant="ghost" onClick={() => { setName(c.display_name); setEditing(false) }}>Cancel</Button>
      </form>
    )
  }
  return (
    <div className="flex flex-col gap-1">
      <h2 className="flex items-center gap-2 text-2xl font-medium tracking-tight">
        {c.is_vip && <VipTag size="lg" />}
        <span className="min-w-0 break-words">{c.display_name}</span>
        <Button variant="ghost" size="icon" className="size-8 text-muted-foreground" aria-label={placeholder ? "Add their name" : "Edit name"}
          onClick={() => { setName(placeholder ? "" : c.display_name); setEditing(true) }}>
          <IconPencil className="size-4" />
        </Button>
      </h2>
      {c.name_source === "call" && (
        <p className="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
          Spelled as Ondra heard it on a call.
          <button type="button" className="underline underline-offset-4 hover:text-foreground" onClick={() => { setName(c.display_name); setEditing(true) }}>Fix it</button>
          <button type="button" className="underline underline-offset-4 hover:text-foreground" disabled={save.isPending} onClick={() => save.mutate(c.display_name)}>It&apos;s right</button>
        </p>
      )}
    </div>
  )
}

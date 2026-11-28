"use client"

/**
 * A client's own data request, answered from their profile (security audit, 2026-11-28). Admins only.
 * One job: hand a customer everything we hold about them, or erase it when they ask.
 * Erasing can't be undone, so it opens inline, says exactly what goes and what stays, and needs their name typed.
 * Data: GET /contacts/{id}/export, POST /contacts/{id}/erase (services/privacy.py).
 */

import { IconDownload } from "@tabler/icons-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import { useAuth } from "@/components/providers"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, send, type Contact } from "@/lib/api"

export function ClientData({ c, optedOut }: { c: Contact; optedOut: boolean }) {
  const { me } = useAuth()
  const qc = useQueryClient()
  const [erasing, setErasing] = useState(false)
  const [typed, setTyped] = useState("")
  const first = c.display_name.split(" ")[0]

  const download = useMutation({
    mutationFn: () => api<unknown>(`/contacts/${c.id}/export`),
    onSuccess: (data) => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }))
      const a = document.createElement("a")
      a.href = url
      a.download = `${c.display_name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-data.json`
      a.click()
      URL.revokeObjectURL(url)
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't download. Try again."),
  })
  const erase = useMutation({
    mutationFn: () => send("POST", `/contacts/${c.id}/erase`, { confirm: typed }),
    onSuccess: () => {
      setErasing(false)
      qc.invalidateQueries({ queryKey: ["contact", c.id] })
      qc.invalidateQueries({ queryKey: ["timeline", c.id] })
      qc.invalidateQueries({ queryKey: ["contacts"] })
      qc.invalidateQueries({ queryKey: ["conversations"] })
      toast(`Erased. Nothing left here says who ${first} was.`)
    },
  })

  if (me?.role !== "admin" || c.display_name === "Erased client") return null
  const matches = typed.trim().replace(/\s+/g, " ").toLowerCase() === c.display_name.trim().replace(/\s+/g, " ").toLowerCase()

  return (
    <section aria-labelledby="their-data">
      <h3 id="their-data" className="text-xs font-medium text-muted-foreground">Their data</h3>
      <p className="mt-1.5 text-sm text-pretty text-muted-foreground">For when {first} asks what you hold, or to be forgotten.</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => download.mutate()} disabled={download.isPending}>
          <IconDownload /> Download it all
        </Button>
        {!erasing && (
          <Button variant="ghost" size="sm" onClick={() => setErasing(true)}>Erase {first}</Button>
        )}
      </div>
      {erasing && (
        <form className="mt-3 grid gap-3 rounded-xl border p-4" aria-label={`Erase ${first}`}
          onSubmit={(e) => { e.preventDefault(); if (matches) erase.mutate() }}>
          <ul className="grid gap-1 text-sm text-pretty">
            <li>Their name, numbers, messages, call notes and deal details are erased. This can&apos;t be undone.</li>
            <li>Bookings and deals stay in your counts, with no name on them.</li>
            {optedOut && <li>They opted out, so their number is kept only to keep that opt-out working.</li>}
          </ul>
          <div className="grid gap-2">
            <Label htmlFor="erase-confirm">Type {c.display_name} to confirm</Label>
            <Input id="erase-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
          </div>
          {erase.isError && <p role="alert" className="text-sm">{erase.error instanceof Error ? erase.error.message : "Couldn't erase. Try again."}</p>}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="outline" disabled={!matches || erase.isPending}>Erase {first} for good</Button>
            <Button type="button" variant="ghost" onClick={() => { setErasing(false); setTyped("") }}>Cancel</Button>
          </div>
        </form>
      )}
    </section>
  )
}

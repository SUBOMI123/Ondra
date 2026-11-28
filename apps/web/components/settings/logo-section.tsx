"use client"

/**
 * Settings > Business and hours > Logo. One job: put the dealership's own logo in the sidebar, where staff see it
 * all day. A second, optional version for dark mode, because a logo drawn for white paper often vanishes on a dark
 * screen; without one, the logo sits on a light tile in dark mode so it still reads.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useRef } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { send } from "@/lib/api"
import { useBranding, type Branding } from "@/lib/branding"

const MAX = 300_000

function read(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (file.size > MAX) return reject(new Error(`That logo is ${Math.round(file.size / 1000)} KB. Use one under 300 KB (an SVG or a PNG about 400 px wide is plenty).`))
    const r = new FileReader()
    r.onload = () => resolve(String(r.result))
    r.onerror = () => reject(new Error("That file couldn't be read. Try another."))
    r.readAsDataURL(file)
  })
}

function Slot({ label, help, value, tile, onPick, onRemove, disabled }: {
  label: string; help: string; value: string | null; tile: "light" | "dark"; onPick: (f: File) => void; onRemove: () => void; disabled: boolean
}) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className={`flex h-16 w-44 shrink-0 items-center justify-center rounded-lg border px-3 ${tile === "dark" ? "bg-night" : "bg-paper"}`}>
        {value ? (
          // eslint-disable-next-line @next/next/no-img-element -- a data URL from the dealer's own upload
          <img src={value} alt={`${label} preview`} className="max-h-10 max-w-full object-contain" />
        ) : (
          <span className={`text-xs ${tile === "dark" ? "text-night-muted" : "text-paper-muted"}`}>No logo yet</span>
        )}
      </div>
      <div className="flex min-w-0 flex-col gap-1.5">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-sm text-muted-foreground">{help}</p>
        <div className="flex flex-wrap gap-2">
          <input ref={input} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="sr-only" aria-label={`Choose ${label.toLowerCase()}`}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onPick(f); e.target.value = "" }} />
          <Button type="button" variant="outline" size="sm" disabled={disabled} onClick={() => input.current?.click()}>{value ? "Replace" : "Upload"}</Button>
          {value && <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={onRemove}>Remove</Button>}
        </div>
      </div>
    </div>
  )
}

export function LogoSection({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient()
  const b = useBranding()
  const save = useMutation({
    mutationFn: (next: Pick<Branding, "logo" | "logo_dark">) => send<Branding>("PUT", "/settings/branding", next),
    onSuccess: (r) => { qc.setQueryData(["branding"], r); toast("Saved. Your logo is in the sidebar.") },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't save the logo."),
  })
  const pick = (which: "logo" | "logo_dark") => async (f: File) => {
    try {
      const url = await read(f)
      save.mutate({ logo: which === "logo" ? url : b.data!.logo, logo_dark: which === "logo_dark" ? url : b.data!.logo_dark })
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }
  return (
    <section aria-labelledby="logo" className="flex flex-col gap-4 border-t pt-8">
      <div>
        <h2 id="logo" className="text-base font-medium">Logo</h2>
        <p className="text-sm text-muted-foreground">Shown at the top of the sidebar for everyone on your team. PNG, JPG, WebP or SVG, under 300 KB.</p>
      </div>
      {b.isPending ? <Skeleton className="h-36 w-full rounded-xl" /> : b.isError ? (
        <p role="alert" className="text-sm">{b.error.message}</p>
      ) : (
        <div className="flex flex-col gap-5">
          <Slot label="Logo" help="As it looks on white." value={b.data.logo} tile="light" disabled={!canEdit || save.isPending}
            onPick={pick("logo")} onRemove={() => save.mutate({ logo: null, logo_dark: null })} />
          {b.data.logo && (
            <Slot label="For dark mode (optional)" help="A light version. Without one, your logo sits on a white tile in dark mode." value={b.data.logo_dark}
              tile="dark" disabled={!canEdit || save.isPending} onPick={pick("logo_dark")} onRemove={() => save.mutate({ logo: b.data.logo, logo_dark: null })} />
          )}
        </div>
      )}
    </section>
  )
}

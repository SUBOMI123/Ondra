"use client"

/** Settings > How Ondra replies. One job: the rules Ondra checks before every message, saved together. */

import { IconCheck } from "@tabler/icons-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { OndraMark } from "@/components/ondra-mark"
import { errorText, type Replies, SaveBar, type SettingsData } from "@/components/settings/shell"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Switch } from "@/components/ui/switch"
import { send } from "@/lib/api"
import { cn } from "@/lib/utils"

const HANDOFF_PRESETS = ["A discount or final price", "What their trade-in is worth", "A delivery date", "A complaint", "Financing terms"]
// Early dealerships were saved with short keys; show them as the preset they mean, so nothing appears twice.
const LEGACY: Record<string, string> = {
  discount: "A discount or final price",
  "trade-in value": "What their trade-in is worth",
  "delivery date": "A delivery date",
  complaint: "A complaint",
}
const normalise = (r: Replies): Replies => ({ ...r, handoff_triggers: [...new Set(r.handoff_triggers.map((t) => LEGACY[t] ?? t))] })

export function RepliesSection({ data, canEdit }: { data: SettingsData; canEdit: boolean }) {
  const qc = useQueryClient()
  const saved = useMemo(() => normalise(data.replies), [data.replies])
  const [form, setForm] = useState<Replies>(saved)
  useEffect(() => {
    setForm(saved)
  }, [saved])
  const dirty = JSON.stringify(form) !== JSON.stringify(saved)
  const save = useMutation({
    mutationFn: () => send("PUT", "/settings/replies", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] })
      toast("Saved. Ondra follows these rules from its next reply.")
    },
  })
  const triggers = [...HANDOFF_PRESETS, ...form.handoff_triggers.filter((t) => !HANDOFF_PRESETS.includes(t))]

  return (
    <>
      <fieldset disabled={!canEdit} className="flex flex-col gap-8">
        <div className="flex items-start justify-between gap-6 rounded-xl border p-4">
          <div>
            <Label htmlFor="draft-mode" className="flex items-center gap-1.5">
              <OndraMark className="size-4 text-ai" /> Draft mode
            </Label>
            <p className="mt-1 text-sm text-muted-foreground">
              Ondra writes every reply and waits for your approval. On for your first week; turn it off when you trust the drafts.
            </p>
          </div>
          <Switch id="draft-mode" checked={form.draft_mode} onCheckedChange={(v) => setForm({ ...form, draft_mode: v })} />
        </div>

        <fieldset>
          <legend className="text-sm font-medium">Prices</legend>
          <RadioGroup value={form.price_disclosure} onValueChange={(v) => setForm({ ...form, price_disclosure: v as Replies["price_disclosure"] })} className="mt-3 gap-3">
            {([
              ["none", "Don't share prices", "Ondra passes every price question to your team."],
              ["listed", "Share listed prices", "Ondra can quote the price on your website. Never a final price or a discount."],
              ["range", "Share a price range", "Ondra gives a rounded range around the listed price."],
            ] as const).map(([v, t, d]) => (
              <Label key={v} htmlFor={`price-${v}`} className="flex cursor-pointer items-start gap-3 rounded-xl border p-4 font-normal has-data-[state=checked]:border-foreground/40">
                <RadioGroupItem value={v} id={`price-${v}`} className="mt-0.5" />
                <span>
                  <span className="block font-medium">{t}</span>
                  <span className="block text-sm text-muted-foreground">{d}</span>
                </span>
              </Label>
            ))}
          </RadioGroup>
        </fieldset>

        <fieldset>
          <legend className="text-sm font-medium">Always hand these to a person</legend>
          <p className="mt-1 text-sm text-muted-foreground">Ondra tells the customer someone will follow up, then passes the conversation on with a brief.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {triggers.map((h) => {
              const on = form.handoff_triggers.includes(h)
              return (
                <button
                  key={h}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setForm({ ...form, handoff_triggers: on ? form.handoff_triggers.filter((x) => x !== h) : [...form.handoff_triggers, h] })}
                  className={cn(
                    "flex min-h-9 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed",
                    on ? "border-foreground/40 bg-muted" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {on && <IconCheck className="size-3.5" aria-hidden="true" />}
                  {h}
                </button>
              )
            })}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-sm font-medium">Telling customers it&apos;s AI</legend>
          <RadioGroup value={form.ai_disclosure} onValueChange={(v) => setForm({ ...form, ai_disclosure: v as Replies["ai_disclosure"] })} className="mt-3 gap-3">
            {([
              ["when_asked", "When they ask", "Ondra never claims to be a person, and says it's your AI assistant whenever asked."],
              ["upfront", "In its first reply", "For states that require it. Ondra says it's your AI assistant when a conversation starts."],
            ] as const).map(([v, t, d]) => (
              <Label key={v} htmlFor={`disc-${v}`} className="flex cursor-pointer items-start gap-3 rounded-xl border p-4 font-normal has-data-[state=checked]:border-foreground/40">
                <RadioGroupItem value={v} id={`disc-${v}`} className="mt-0.5" />
                <span>
                  <span className="block font-medium">{t}</span>
                  <span className="block text-sm text-muted-foreground">{d}</span>
                </span>
              </Label>
            ))}
          </RadioGroup>
        </fieldset>
      </fieldset>
      {canEdit && (
        <SaveBar dirty={dirty} saving={save.isPending} error={save.isError ? errorText(save.error) : null}
          onSave={() => save.mutate()} onReset={() => { setForm(saved); save.reset() }} />
      )}
    </>
  )
}

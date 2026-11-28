"use client"

/** Settings > Business and hours. One job: the dealership's name, time zone and opening hours, which Ondra uses to say when you're open. */

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { type Business, type Day, errorText, SaveBar, type SettingsData } from "@/components/settings/shell"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { send } from "@/lib/api"

const DAYS: [Day, string][] = [
  ["mon", "Monday"], ["tue", "Tuesday"], ["wed", "Wednesday"], ["thu", "Thursday"],
  ["fri", "Friday"], ["sat", "Saturday"], ["sun", "Sunday"],
]

export function BusinessSection({ data, canEdit }: { data: SettingsData; canEdit: boolean }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<Business>(data.business)
  useEffect(() => {
    setForm(data.business)
  }, [data.business])
  const dirty = JSON.stringify(form) !== JSON.stringify(data.business)
  const save = useMutation({
    mutationFn: () => send("PUT", "/settings/business", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] })
      toast("Business details saved. Ondra uses the new hours from its next reply.")
    },
  })
  const setDay = (d: Day, span: [string, string] | null) => setForm((f) => ({ ...f, hours: { ...f.hours, [d]: span } }))

  return (
    <>
      <fieldset disabled={!canEdit} className="grid max-w-xl gap-6">
        <div className="grid gap-2">
          <Label htmlFor="biz-name">Dealership name</Label>
          <Input id="biz-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="biz-tz">Time zone</Label>
          <Select value={form.timezone} onValueChange={(v) => setForm({ ...form, timezone: v })} disabled={!canEdit}>
            <SelectTrigger id="biz-tz" className="w-full sm:w-72"><SelectValue /></SelectTrigger>
            <SelectContent className="max-h-72">
              {data.timezones.map((z) => <SelectItem key={z} value={z}>{z.replace(/_/g, " ")}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <p className="mb-2 text-sm font-medium" id="hours-label">Opening hours</p>
          <ul aria-labelledby="hours-label" className="divide-y rounded-xl border">
            {DAYS.map(([d, label]) => {
              const span = form.hours[d]
              return (
                <li key={d} className="grid grid-cols-[6.5rem_auto_minmax(0,1fr)] items-center gap-3 px-4 py-2.5 text-sm">
                  <span>{label}</span>
                  <Switch
                    checked={!!span}
                    onCheckedChange={(on) => setDay(d, on ? ["09:00", "18:00"] : null)}
                    aria-label={`Open on ${label}`}
                  />
                  {span ? (
                    <span className="flex flex-wrap items-center gap-2">
                      <Input type="time" value={span[0]} aria-label={`${label} opens`} className="w-32"
                        onChange={(e) => setDay(d, [e.target.value, span[1]])} />
                      <span className="text-muted-foreground">to</span>
                      <Input type="time" value={span[1]} aria-label={`${label} closes`} className="w-32"
                        onChange={(e) => setDay(d, [span[0], e.target.value])} />
                    </span>
                  ) : (
                    <span className="text-muted-foreground">Closed</span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      </fieldset>
      {canEdit && (
        <SaveBar dirty={dirty} saving={save.isPending} error={save.isError ? errorText(save.error) : null}
          onSave={() => save.mutate()} onReset={() => { setForm(data.business); save.reset() }} />
      )}
    </>
  )
}

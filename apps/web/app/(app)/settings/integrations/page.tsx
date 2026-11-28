"use client"

/**
 * Integrations. One job: connect the dealership's other systems and see at a glance that each one is working.
 * Three of them, each a section with its health in words first: leads to your CRM, your inventory, your service
 * system. A problem says what went wrong and what to do; nothing here is decorative.
 */

import { IconAlertTriangle, IconArrowLeft, IconCircleCheck, IconCircleDashed } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { api, send } from "@/lib/api"
import { cn } from "@/lib/utils"
import { fmt } from "@/lib/time"

type Health = { state: "off" | "ok" | "warning" | "error"; last_ok_at: string | null; last: Record<string, unknown> }
type Data = {
  crm: Health & { email: string; active: boolean; has_sender: boolean }
  inventory: Health & { url: string; every_hours: 0 | 1 | 6 | 24 }
  dms: Health & { provider: "off" | "mock" | "csv"; orders: number | null }
  can_edit: boolean
  can_import: boolean
}
type Skipped = { line: number; why: string }
type Preview = {
  created: number; updated: number; unchanged: number; sold: number; skipped: Skipped[]; skipped_count: number; duplicates: number
  partial: boolean; unknown_columns: string[]; examples: { created: string[]; updated: string[]; sold: string[] }
}

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

function when(iso: string | null) {
  return iso ? fmt(iso, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).replace(" AM", " am").replace(" PM", " pm") : null
}

function n(count: number, one: string, many = `${one}s`) {
  return `${count} ${count === 1 ? one : many}`
}

/** The integration's health, in words, with an icon. No colour: red is for VIPs and overdue items only. */
function HealthLine({ h, off, ok, problem }: { h: Health; off: string; ok: string; problem?: string }) {
  const text = h.state === "off" ? off : h.state === "error" ? (problem ?? "There's a problem.") : ok
  const Icon = h.state === "ok" ? IconCircleCheck : h.state === "off" ? IconCircleDashed : IconAlertTriangle
  return (
    <p className="flex items-start gap-2 text-sm" data-state={h.state}>
      <Icon aria-hidden="true" className={cn("mt-0.5 size-4 shrink-0", h.state === "off" && "text-muted-foreground")} />
      <span className={cn(h.state === "off" && "text-muted-foreground", h.state === "error" && "font-medium")}>
        {h.state === "error" ? "Not working. " : h.state === "warning" ? "Working, with a warning. " : ""}{text}
      </span>
    </p>
  )
}

function Block({ id, title, about, children }: { id: string; title: string; about: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-20 border-b pb-8 last:border-b-0">
      <h2 id={`${id}-h`} className="text-lg font-medium">{title}</h2>
      <p className="mt-1 max-w-prose text-sm text-muted-foreground">{about}</p>
      <div className="mt-5 grid gap-5">{children}</div>
    </section>
  )
}

/** Read a chosen file as text, for the import endpoints (they take the text, not a multipart upload). */
function FilePick({ label, accept, onText, disabled }: { label: string; accept: string; onText: (name: string, text: string) => void; disabled?: boolean }) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <>
      <input ref={ref} type="file" accept={accept} className="sr-only" tabIndex={-1} aria-hidden="true"
        onChange={async (e) => {
          const f = e.target.files?.[0]
          e.target.value = ""
          if (!f) return
          if (f.size > 5 * 1024 * 1024) return toast("That file is larger than 5 MB.")
          onText(f.name, await f.text())
        }} />
      <Button type="button" variant="outline" disabled={disabled} onClick={() => ref.current?.click()}>{label}</Button>
    </>
  )
}

/* ------------------------------------------------------------ leads to the CRM */

function CrmBlock({ d, canEdit }: { d: Data["crm"]; canEdit: boolean }) {
  const qc = useQueryClient()
  const [email, setEmail] = useState(d.email)
  useEffect(() => {
    setEmail(d.email)
  }, [d.email])
  const refresh = () => qc.invalidateQueries({ queryKey: ["integrations"] })
  const save = useMutation({
    mutationFn: (v: { email: string; active: boolean }) => send("PUT", "/integrations/crm", v),
    onSuccess: (_r, v) => { refresh(); toast(v.active ? "Saved. New leads go to your CRM from now on." : "Lead sending is off.") },
  })
  const test = useMutation({
    mutationFn: () => send("POST", "/integrations/crm/test"),
    onSuccess: () => { refresh(); toast("Test lead sent. Look for “Test Lead” in your CRM; it's safe to delete.") },
    onError: (e) => { refresh(); toast(errorText(e)) },
  })
  const lastDetail = typeof d.last.detail === "string" ? d.last.detail : undefined
  return (
    <Block id="crm" title="Leads to your CRM" about="When Ondra has a buyer's details and what they want, it emails the lead to your CRM in the standard format dealer CRMs read (ADF). Each lead is sent once. VIPs are never sent.">
      <HealthLine h={d} off="Not sending leads anywhere yet."
        ok={d.last_ok_at ? `Last lead sent ${when(d.last_ok_at)}.` : "Ready. No lead has been sent yet."} problem={lastDetail} />
      {!d.has_sender && (
        <p className="text-sm">Leads are emailed from your dealership&apos;s address. <Link href="/settings/channels" className="underline underline-offset-4">Add an email address under Channels</Link> first.</p>
      )}
      <form className="grid gap-2 sm:max-w-md" onSubmit={(e) => { e.preventDefault(); save.mutate({ email, active: true }) }}>
        <Label htmlFor="crm-email">Your CRM&apos;s lead address</Label>
        <div className="flex flex-wrap gap-2">
          <Input id="crm-email" type="email" value={email} disabled={!canEdit} onChange={(e) => setEmail(e.target.value)} placeholder="leads@yourdealership.crm.com" className="min-w-0 flex-1 basis-56" />
          {canEdit && <Button type="submit" disabled={save.isPending || !email.trim() || (email === d.email && d.active)}>{save.isPending ? "Saving…" : d.active ? "Save" : "Start sending leads"}</Button>}
        </div>
        <p className="text-sm text-muted-foreground">Your CRM gives you this address for incoming internet leads. Ask your CRM rep for the “ADF lead email”.</p>
        {save.isError && <p role="alert" className="text-sm">{errorText(save.error)}</p>}
      </form>
      {canEdit && d.active && (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => test.mutate()} disabled={test.isPending}>{test.isPending ? "Sending…" : "Send a test lead"}</Button>
          <Button variant="ghost" onClick={() => save.mutate({ email: d.email, active: false })} disabled={save.isPending}>Stop sending leads</Button>
        </div>
      )}
    </Block>
  )
}

/* ------------------------------------------------------------ inventory */

function PreviewLines({ p }: { p: Preview }) {
  const nothing = p.created + p.updated + p.sold === 0
  return (
    <div className="grid gap-1.5 text-sm">
      <p className="font-medium">
        {nothing ? "Nothing would change: every vehicle in this file is already up to date."
          : `This would add ${n(p.created, "vehicle")}, update ${p.updated}${p.sold ? `, and mark ${p.sold} sold` : ""}.`}
        {p.unchanged > 0 && !nothing && ` ${p.unchanged} already match.`}
      </p>
      {p.examples.created.length > 0 && <p className="text-muted-foreground">New: {p.examples.created.join("; ")}{p.created > p.examples.created.length ? "; and more" : ""}.</p>}
      {p.examples.sold.length > 0 && <p className="text-muted-foreground">No longer in the file, so marked sold: {p.examples.sold.join("; ")}{p.sold > p.examples.sold.length ? "; and more" : ""}.</p>}
      {p.partial && <p>This file lists far fewer vehicles than you have, so it looks cut short. Nothing will be marked sold.</p>}
      {p.skipped_count > 0 && (
        <div>
          <p>{n(p.skipped_count, "row")} can&apos;t be read and will be left out:</p>
          <ul className="mt-1 list-disc pl-5 text-muted-foreground">
            {p.skipped.slice(0, 5).map((s) => <li key={s.line}>Line {s.line}: {s.why}</li>)}
            {p.skipped_count > 5 && <li>and {p.skipped_count - 5} more</li>}
          </ul>
        </div>
      )}
      {p.duplicates > 0 && <p className="text-muted-foreground">{n(p.duplicates, "vehicle")} appeared twice; the later line is used.</p>}
    </div>
  )
}

function InventoryBlock({ d, canEdit, canImport }: { d: Data["inventory"]; canEdit: boolean; canImport: boolean }) {
  const qc = useQueryClient()
  const [file, setFile] = useState<{ name: string; text: string } | null>(null)
  const [whole, setWhole] = useState(false)
  const [url, setUrl] = useState(d.url)
  const [every, setEvery] = useState(String(d.every_hours))
  useEffect(() => {
    setUrl(d.url)
    setEvery(String(d.every_hours))
  }, [d.url, d.every_hours])
  const refresh = () => { qc.invalidateQueries({ queryKey: ["integrations"] }); qc.invalidateQueries({ queryKey: ["vehicles"] }) }
  const preview = useMutation({ mutationFn: (v: { name: string; text: string; whole: boolean }) =>
    send<Preview>("POST", "/inventory/import", { filename: v.name, content: v.text, whole_lot: v.whole, dry_run: true }) })
  const apply = useMutation({
    mutationFn: () => send<Preview>("POST", "/inventory/import", { filename: file?.name, content: file?.text, whole_lot: whole, dry_run: false }),
    onSuccess: (r) => { setFile(null); preview.reset(); refresh(); toast(`Imported: ${r.created} added, ${r.updated} updated${r.sold ? `, ${r.sold} marked sold` : ""}.`) },
  })
  const feed = useMutation({
    mutationFn: () => send("PUT", "/integrations/inventory-feed", { url, every_hours: Number(every) }),
    onSuccess: () => { refresh(); toast(Number(every) && url ? "Saved. The first fetch is starting now." : "Scheduled fetching is off.") },
  })
  const pick = (name: string, text: string) => { setFile({ name, text }); apply.reset(); preview.mutate({ name, text, whole }) }
  const last = d.last as { created?: number; updated?: number; sold?: number; skipped_count?: number; error?: string; partial?: boolean }
  const okText = d.last_ok_at
    ? `Last import ${when(d.last_ok_at)}: ${last.created ?? 0} added, ${last.updated ?? 0} updated, ${last.sold ?? 0} marked sold${last.skipped_count ? `, ${n(last.skipped_count, "row")} left out` : ""}${last.partial ? ". The file looked cut short, so nothing was marked sold" : ""}.`
    : "A feed address is saved. Nothing has been imported yet."
  return (
    <Block id="inventory" title="Your inventory" about="Ondra only offers cars that are in your inventory here. Bring it in from a file, or give us your feed's address and we'll fetch it on a schedule. Cars are matched by VIN, then stock number.">
      <HealthLine h={d} off="No inventory has been imported. The cars here were entered by hand." ok={okText} problem={last.error} />
      {canImport && (
        <div className="grid gap-3">
          <p className="text-sm font-medium">Import a file</p>
          <div className="flex flex-wrap items-center gap-3">
            <FilePick label={file ? "Choose a different file" : "Choose a CSV or XML file"} accept=".csv,.xml,.txt,text/csv,text/xml,application/xml" onText={pick} disabled={preview.isPending || apply.isPending} />
            {file && <span className="truncate text-sm text-muted-foreground" title={file.name}>{file.name}</span>}
          </div>
          <div className="flex items-start gap-3">
            <Switch id="whole-lot" checked={whole} className="mt-0.5" onCheckedChange={(v) => { setWhole(v); if (file) preview.mutate({ ...file, whole: v }) }} />
            <div className="grid gap-1">
              <Label htmlFor="whole-lot" className="font-normal">This file is my whole lot</Label>
              <p className="text-sm text-muted-foreground">On: cars from earlier imports that aren&apos;t in this file are marked sold. Cars you entered by hand are never touched.</p>
            </div>
          </div>
          <div aria-live="polite">
            {preview.isPending && <p className="text-sm text-muted-foreground">Reading the file…</p>}
            {preview.isError && <p role="alert" className="text-sm">{errorText(preview.error)}</p>}
            {file && preview.data && !preview.isPending && (
              <div className="grid gap-3 rounded-xl border p-4">
                <PreviewLines p={preview.data} />
                {apply.isError && <p role="alert" className="text-sm">{errorText(apply.error)}</p>}
                <div className="flex gap-2">
                  <Button onClick={() => apply.mutate()} disabled={apply.isPending || preview.data.created + preview.data.updated + preview.data.sold === 0}>
                    {apply.isPending ? "Importing…" : "Import these vehicles"}
                  </Button>
                  <Button variant="ghost" onClick={() => { setFile(null); preview.reset() }}>Cancel</Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); feed.mutate() }}>
        <p className="text-sm font-medium">Fetch it on a schedule</p>
        <div className="grid gap-3 sm:grid-cols-[1fr_11rem]">
          <div className="grid gap-2">
            <Label htmlFor="feed-url">Feed address</Label>
            <Input id="feed-url" type="url" value={url} disabled={!canEdit} onChange={(e) => setUrl(e.target.value)} placeholder="https://feeds.yourprovider.com/dealer-1234.csv" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="feed-every">How often</Label>
            <Select value={every} onValueChange={setEvery} disabled={!canEdit}>
              <SelectTrigger id="feed-every" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="0">Don&apos;t fetch</SelectItem>
                <SelectItem value="1">Every hour</SelectItem>
                <SelectItem value="6">Every 6 hours</SelectItem>
                <SelectItem value="24">Once a day</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">Your website or inventory provider can give you this. A fetched feed is treated as your whole lot.</p>
        {feed.isError && <p role="alert" className="text-sm">{errorText(feed.error)}</p>}
        {canEdit && <div><Button type="submit" variant="outline" disabled={feed.isPending || (url === d.url && Number(every) === d.every_hours)}>{feed.isPending ? "Saving…" : "Save schedule"}</Button></div>}
      </form>
    </Block>
  )
}

/* ------------------------------------------------------------ service system */

function DmsBlock({ d, canEdit }: { d: Data["dms"]; canEdit: boolean }) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: ["integrations"] })
  const choose = useMutation({
    mutationFn: (provider: Data["dms"]["provider"]) => send("PUT", "/integrations/dms", { provider }),
    onSuccess: () => { refresh(); toast("Saved.") },
    onError: (e) => toast(errorText(e)),
  })
  const upload = useMutation({
    mutationFn: (f: { name: string; text: string }) => send<{ loaded: number; skipped_count: number; skipped: Skipped[] }>("POST", "/integrations/dms/upload", { filename: f.name, content: f.text }),
    onSuccess: (r) => { refresh(); toast(`${n(r.loaded, "repair order")} loaded${r.skipped_count ? `, ${n(r.skipped_count, "row")} left out` : ""}. Ondra answers from them now.`) },
  })
  const last = d.last as { detail?: string; skipped?: number }
  return (
    <Block id="dms" title="Your service system" about="So Ondra can answer “is my car ready?” from your repair orders. It tells a customer only about their own car, found by the phone number or email they contact you from, and never gives a completion time or a cost.">
      <HealthLine h={d} off="Not connected. Ondra passes repair questions to a service advisor."
        ok={d.provider === "mock" ? "Using demo repair orders. Good for trying it out, not for real customers." : `${n(d.orders ?? 0, "repair order")} from your last upload${d.last_ok_at ? `, ${when(d.last_ok_at)}` : ""}${last.skipped ? `. ${n(last.skipped, "row")} couldn't be read and ${last.skipped === 1 ? "was" : "were"} left out` : ""}.`}
        problem={last.detail} />
      <RadioGroup value={d.provider} disabled={!canEdit || choose.isPending} onValueChange={(v) => choose.mutate(v as Data["dms"]["provider"])} className="gap-3" aria-label="Where repair orders come from">
        {([["off", "Not connected", "Repair questions go to a service advisor."],
          ["csv", "A repair-order export I upload", "Export open repair orders from your DMS as a CSV and upload it here, as often as you like."],
          ["mock", "Demo data", "Three made-up repair orders, to see how it answers."]] as const).map(([v, label, hint]) => (
          <div key={v} className="flex items-start gap-2.5">
            <RadioGroupItem value={v} id={`dms-${v}`} className="mt-0.5" disabled={v === "csv" && !d.orders && d.provider !== "csv"} />
            <div className="grid gap-0.5">
              <Label htmlFor={`dms-${v}`} className="font-normal">{label}</Label>
              <p className="text-sm text-muted-foreground">{hint}</p>
            </div>
          </div>
        ))}
      </RadioGroup>
      {canEdit && (
        <div className="grid gap-2">
          <div><FilePick label="Upload a repair-order export" accept=".csv,.txt,text/csv" onText={(name, text) => upload.mutate({ name, text })} disabled={upload.isPending} /></div>
          <p className="text-sm text-muted-foreground">It needs columns for the RO number, its status, and the customer&apos;s phone or email. Each upload replaces the last.</p>
          {upload.isError && <p role="alert" className="text-sm">{errorText(upload.error)}</p>}
          {upload.data && upload.data.skipped_count > 0 && (
            <ul className="list-disc pl-5 text-sm text-muted-foreground">
              {upload.data.skipped.slice(0, 5).map((s) => <li key={s.line}>Line {s.line} left out: {s.why}</li>)}
            </ul>
          )}
        </div>
      )}
      <p className="max-w-prose text-sm text-muted-foreground">A live connection to CDK, Reynolds, Tekion or DealerCenter needs their partner approval and isn&apos;t available yet.</p>
    </Block>
  )
}

export default function IntegrationsPage() {
  const q = useQuery({ queryKey: ["integrations"], queryFn: () => api<Data>("/integrations") })
  return (
    <>
      <SiteHeader title="Integrations" />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-6 lg:px-6">
        <Link href="/settings" className="flex items-center gap-1.5 self-start text-sm text-muted-foreground hover:text-foreground">
          <IconArrowLeft className="size-4" aria-hidden="true" /> Settings
        </Link>
        {q.isPending ? (
          <TableSkeleton rows={6} />
        ) : q.isError ? (
          <LoadError message={q.error.message} onRetry={() => q.refetch()} />
        ) : (
          <>
            {!q.data.can_edit && <p className="text-sm text-muted-foreground">Only admins can change these.{q.data.can_import ? " You can import an inventory file." : ""}</p>}
            <CrmBlock d={q.data.crm} canEdit={q.data.can_edit} />
            <InventoryBlock d={q.data.inventory} canEdit={q.data.can_edit} canImport={q.data.can_import} />
            <DmsBlock d={q.data.dms} canEdit={q.data.can_edit} />
          </>
        )}
      </div>
    </>
  )
}

"use client"

/**
 * Who gets what. One job: decide who gets each kind of message and what Ondra may do with it, then check it with a
 * real message. Rules read as plain sentences, in the order they're checked (the first that fits decides). The VIP
 * line is always first and can't be changed; what's left over goes to the usual team. The only blue on the page is
 * what Ondra does.
 */

import { IconArrowLeft, IconDotsVertical, IconPlus } from "@tabler/icons-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { LoadError, TableSkeleton } from "@/components/list-states"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { api, send } from "@/lib/api"
import { cn } from "@/lib/utils"
import { VipTag } from "@/components/vip"

type Topic = "sales" | "service" | "shipping" | "finance" | "complaint" | "other"
type Channel = "sms" | "whatsapp" | "email" | "phone"
type Ai = "auto" | "draft" | "off"
type Rule = {
  id: string
  position: number
  active: boolean
  topics: Topic[]
  channels: Channel[]
  hours: "any" | "open" | "closed"
  language: string | null
  deal_type: "sales" | "service" | null
  team: string | null
  user_id: string | null
  ai: Ai | null
  alert: boolean
}
type Person = { id: string; name: string; role: string }
type Routing = { rules: Rule[]; people: Person[]; vip_backup: string | null; can_edit: boolean }
type Preview = { topic: Topic; rule_id: string | null; team: string | null; person: string | null; in_now: boolean; back_at: string | null; ai: Ai; alert: boolean }
type Draft = Omit<Rule, "id" | "position">

const TOPICS: [Topic, string, string][] = [
  ["sales", "Sales", "Sales questions"], ["service", "Service", "Service questions"], ["shipping", "Shipping", "Shipping questions"],
  ["finance", "Finance", "Finance questions"], ["complaint", "Complaints", "Complaints"], ["other", "Anything else", "Other questions"],
]
const CHANNELS: [Channel, string, string][] = [
  ["sms", "Text", "by text"], ["whatsapp", "WhatsApp", "on WhatsApp"], ["email", "Email", "by email"], ["phone", "Calls", "on calls"],
]
const TOPIC_A: Record<Topic, string> = {
  sales: "a sales question", service: "a service question", shipping: "a shipping question", finance: "a finance question",
  complaint: "a complaint", other: "a general question",
}
const TEAMS: [string, string][] = [["sales", "Sales"], ["service", "Service"], ["manager", "Managers"], ["admin", "Admins"]]
const TEAM_LABEL: Record<string, string> = { ...Object.fromEntries(TEAMS), ops: "Operations", admin: "Admins" }
const LANGUAGES: [string, string][] = [["es", "Spanish"], ["fr", "French"], ["pt", "Portuguese"]]
const AI_LINE: Record<Ai, string> = {
  auto: "Ondra replies as usual.",
  draft: "Ondra drafts a reply for someone to approve.",
  off: "Ondra stays out. Nothing is sent.",
}
const BLANK: Draft = { active: true, topics: [], channels: [], hours: "any", language: null, deal_type: null, team: "sales", user_id: null, ai: null, alert: false }

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

function list(parts: string[]) {
  return parts.length <= 1 ? (parts[0] ?? "") : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`
}

/** A rule as a sentence: "Complaints by text go to Managers, marked urgent." */
function sentence(r: Draft, people: Person[]) {
  const what = r.topics.length ? list(r.topics.map((t) => TOPICS.find((x) => x[0] === t)?.[2] ?? t)) : "Everything"
  const where = r.channels.length ? ` ${list(r.channels.map((c) => CHANNELS.find((x) => x[0] === c)?.[2] ?? c))}` : ""
  const when = r.hours === "open" ? " while you're open" : r.hours === "closed" ? " while you're closed" : ""
  const lang = r.language ? ` in ${LANGUAGES.find((l) => l[0] === r.language)?.[1] ?? r.language}` : ""
  const deal = r.deal_type ? ` from customers with an open ${r.deal_type} deal` : ""
  const who = r.user_id ? (people.find((p) => p.id === r.user_id)?.name ?? "someone who has left") : (TEAM_LABEL[r.team ?? ""] ?? "Sales")
  const verb = r.topics.length === 0 ? "goes" : "go"
  return `${what}${where}${lang}${deal}${when} ${verb} to ${who}${r.alert ? ", marked urgent" : ""}.`
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        "min-h-9 rounded-full border px-3 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
        on ? "border-foreground/40 bg-muted" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}

function OndraLine({ ai, muted }: { ai: Ai; muted?: boolean }) {
  return (
    <span data-slot="ai-note" className={cn("flex items-center gap-1.5 text-sm text-ai", muted && "opacity-60")}>
      <OndraMark className="size-3.5 shrink-0" />
      {AI_LINE[ai]}
    </span>
  )
}

/* ------------------------------------------------------------ rule form (add or edit) */

function RuleForm({ initial, people, isNew, saving, error, onSave, onCancel }: {
  initial: Draft; people: Person[]; isNew: boolean; saving: boolean; error: string | null
  onSave: (d: Draft) => void; onCancel: () => void
}) {
  const [d, setD] = useState<Draft>(initial)
  const [more, setMore] = useState(!!initial.language || !!initial.deal_type)
  const flip = <T,>(xs: T[], x: T) => (xs.includes(x) ? xs.filter((y) => y !== x) : [...xs, x])
  const target = d.user_id ? `user:${d.user_id}` : `team:${d.team ?? "sales"}`
  return (
    <form className="grid gap-5 p-4" onSubmit={(e) => { e.preventDefault(); onSave(d) }} aria-label={isNew ? "New rule" : "Edit rule"}>
      <fieldset className="grid gap-2">
        <legend className="text-sm font-medium">What it&apos;s about</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {TOPICS.map(([t, label]) => (
            <Chip key={t} on={d.topics.includes(t)} onClick={() => setD({ ...d, topics: flip(d.topics, t) })}>{label}</Chip>
          ))}
        </div>
        <p className="text-sm text-muted-foreground">Leave them all off for any topic. Ondra works out the topic from the message.</p>
      </fieldset>
      <fieldset className="grid gap-2">
        <legend className="text-sm font-medium">How it arrives</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {CHANNELS.map(([c, label]) => (
            <Chip key={c} on={d.channels.includes(c)} onClick={() => setD({ ...d, channels: flip(d.channels, c) })}>{label}</Chip>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="rule-hours">When</Label>
          <Select value={d.hours} onValueChange={(hours) => setD({ ...d, hours: hours as Draft["hours"] })}>
            <SelectTrigger id="rule-hours" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any time</SelectItem>
              <SelectItem value="open">While you&apos;re open</SelectItem>
              <SelectItem value="closed">While you&apos;re closed</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="rule-who">Who gets it</Label>
          <Select value={target} onValueChange={(v) => setD(v.startsWith("user:") ? { ...d, user_id: v.slice(5), team: null } : { ...d, team: v.slice(5), user_id: null })}>
            <SelectTrigger id="rule-who" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel>A team, taking turns</SelectLabel>
                {TEAMS.map(([t, label]) => <SelectItem key={t} value={`team:${t}`}>{label}</SelectItem>)}
              </SelectGroup>
              <SelectGroup>
                <SelectLabel>One person</SelectLabel>
                {people.map((p) => <SelectItem key={p.id} value={`user:${p.id}`}>{p.name}</SelectItem>)}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
      </div>
      {more ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="rule-lang">Customer writes in</Label>
            <Select value={d.language ?? "any"} onValueChange={(v) => setD({ ...d, language: v === "any" ? null : v })}>
              <SelectTrigger id="rule-lang" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Any language</SelectItem>
                {LANGUAGES.map(([code, label]) => <SelectItem key={code} value={code}>{label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="rule-deal">Customer already has</Label>
            <Select value={d.deal_type ?? "any"} onValueChange={(v) => setD({ ...d, deal_type: v === "any" ? null : (v as "sales" | "service") })}>
              <SelectTrigger id="rule-deal" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Anything or nothing</SelectItem>
                <SelectItem value="sales">An open sales deal</SelectItem>
                <SelectItem value="service">An open service deal</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      ) : (
        <button type="button" className="justify-self-start text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline" onClick={() => setMore(true)}>
          Narrow it by language or open deal
        </button>
      )}
      <fieldset className="grid gap-2">
        <legend className="text-sm font-medium">What Ondra does with it</legend>
        <RadioGroup className="mt-2 gap-2.5" value={d.ai ?? "auto"} onValueChange={(v) => setD({ ...d, ai: v === "auto" ? null : (v as Ai) })}>
          {([["auto", "Replies as usual"], ["draft", "Drafts a reply for someone to approve"], ["off", "Stays out: a person replies"]] as const).map(([v, label]) => (
            <div key={v} className="flex items-center gap-2.5">
              <RadioGroupItem value={v} id={`rule-ai-${v}`} />
              <Label htmlFor={`rule-ai-${v}`} className="font-normal">{label}</Label>
            </div>
          ))}
        </RadioGroup>
      </fieldset>
      <div className="flex items-center gap-3">
        <Switch id="rule-alert" checked={d.alert} onCheckedChange={(alert) => setD({ ...d, alert })} />
        <Label htmlFor="rule-alert" className="font-normal">Mark it urgent and alert them</Label>
      </div>
      <p className="rounded-lg bg-muted/50 px-3 py-2 text-sm" aria-live="polite">
        <span className="text-muted-foreground">Reads as: </span>
        {sentence(d, people)}
      </p>
      {error && <p role="alert" className="text-sm">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>{saving ? "Saving…" : isNew ? "Add rule" : "Save rule"}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  )
}

/* ------------------------------------------------------------ check a message */

function CheckMessage({ rules }: { rules: Rule[] }) {
  const [text, setText] = useState("")
  const [channel, setChannel] = useState<Channel>("sms")
  const check = useMutation({ mutationFn: () => send<Preview>("POST", "/routing/preview", { text, channel }) })
  const r = check.data
  const ruleNumber = r?.rule_id ? rules.findIndex((x) => x.id === r.rule_id) + 1 : 0
  return (
    <section aria-labelledby="check-h" className="rounded-xl border p-4">
      <h2 id="check-h" className="font-medium">Check a message</h2>
      <p className="mt-1 text-sm text-muted-foreground">Type what a customer might send and see who would get it right now. Nothing is sent.</p>
      <form className="mt-4 grid gap-2 sm:grid-cols-[1fr_9rem_auto]" onSubmit={(e) => { e.preventDefault(); if (text.trim()) check.mutate() }}>
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="My brakes are squealing, can I bring it in Saturday?" aria-label="A customer's message" />
        <Select value={channel} onValueChange={(v) => setChannel(v as Channel)}>
          <SelectTrigger aria-label="How it arrives" className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>{CHANNELS.map(([c, label]) => <SelectItem key={c} value={c}>{label}</SelectItem>)}</SelectContent>
        </Select>
        <Button type="submit" variant="outline" disabled={check.isPending || !text.trim()}>{check.isPending ? "Checking…" : "See who gets it"}</Button>
      </form>
      <div aria-live="polite" className="mt-3 text-sm">
        {check.isError && <p role="alert">{errorText(check.error)}</p>}
        {r && !check.isPending && (
          <div className="grid gap-1.5">
            <p>
              Ondra reads this as {TOPIC_A[r.topic]}.{" "}
              {r.person ? (
                <>If a person is needed it goes to <span className="font-medium">{r.person}</span> ({TEAM_LABEL[r.team ?? ""] ?? r.team}), who is {r.in_now ? "in now" : "not in right now, so it waits for them"}{r.alert ? ", marked urgent" : ""}.</>
              ) : (
                <>Nobody is set up to take it. Add someone to the team first.</>
              )}
            </p>
            <OndraLine ai={r.ai} />
            <p className="text-muted-foreground">
              {ruleNumber > 0 ? `Decided by rule ${ruleNumber}.` : "No rule fits, so it goes to the usual team."} A VIP would skip all of this and go to the person looking after them.
            </p>
          </div>
        )}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------ page */

export default function RoutingPage() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ["routing"], queryFn: () => api<Routing>("/routing") })
  const [editing, setEditing] = useState<string | "new" | null>(null)
  const data = q.data
  const rules = data?.rules ?? []
  const canEdit = !!data?.can_edit
  const done = () => { setEditing(null); qc.invalidateQueries({ queryKey: ["routing"] }) }
  const toBody = (d: Draft) => ({ ...d, language: d.language || null })
  const save = useMutation({
    mutationFn: ({ id, d }: { id: string | "new"; d: Draft }) =>
      id === "new" ? send("POST", "/routing/rules", toBody(d)) : send("PUT", `/routing/rules/${id}`, toBody(d)),
    onSuccess: (_r, v) => { done(); toast(v.id === "new" ? "Rule added. It applies from the next message." : "Rule saved.") },
  })
  const change = useMutation({
    mutationFn: (job: { kind: "switch"; id: string; active: boolean } | { kind: "delete"; id: string } | { kind: "order"; ids: string[] }) =>
      job.kind === "switch" ? send("PATCH", `/routing/rules/${job.id}`, { active: job.active })
        : job.kind === "delete" ? send("DELETE", `/routing/rules/${job.id}`)
        : send("PUT", "/routing/order", { ids: job.ids }),
    onSuccess: (_r, job) => {
      qc.invalidateQueries({ queryKey: ["routing"] })
      if (job.kind !== "delete") return
      // Undo puts the rule back where it was: add it again, then restore the order.
      const before = rules
      const gone = before.find((r) => r.id === job.id)
      if (!gone) return
      toast("Rule deleted.", {
        action: {
          label: "Undo",
          onClick: async () => {
            try {
              const back = await send<Rule>("POST", "/routing/rules", toBody(gone))
              await send("PUT", "/routing/order", { ids: before.map((r) => (r.id === gone.id ? back.id : r.id)) })
            } catch (e) {
              toast(errorText(e))
            }
            qc.invalidateQueries({ queryKey: ["routing"] })
          },
        },
      })
    },
    onError: (e) => toast(errorText(e)),
  })

  const move = (i: number, by: number) => {
    const ids = rules.map((r) => r.id)
    ;[ids[i], ids[i + by]] = [ids[i + by], ids[i]]
    change.mutate({ kind: "order", ids })
  }

  return (
    <>
      <SiteHeader title="Who gets what" />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 lg:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/settings" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <IconArrowLeft className="size-4" aria-hidden="true" /> Settings
          </Link>
          {canEdit && editing === null && (
            <Button onClick={() => { save.reset(); setEditing("new") }}>
              <IconPlus /> Add a rule
            </Button>
          )}
        </div>
        <p className="max-w-prose text-sm text-muted-foreground">
          When a message, call or handoff needs a person, these are checked from the top and the first one that fits decides. Within a team, work goes to whoever is in and has waited longest.
          {data && !canEdit && " Only admins can change them."}
        </p>

        {q.isPending ? (
          <TableSkeleton rows={4} />
        ) : q.isError ? (
          <LoadError message={q.error.message} onRetry={() => q.refetch()} />
        ) : (
          <>
            <ol className="divide-y rounded-xl border" aria-label="Rules, in the order they are checked">
              <li className="flex items-start gap-3 px-4 py-3" data-vip>
                <VipTag />
                <div className="min-w-0">
                  <p>VIPs always go to the person looking after them{q.data.vip_backup ? `, or ${q.data.vip_backup} if nobody is` : ""}.</p>
                  <p className="text-sm text-muted-foreground">Always first. They get a personal reply and their calls ring through directly.</p>
                </div>
              </li>
              {rules.map((r, i) =>
                editing === r.id ? (
                  <li key={r.id}>
                    <RuleForm initial={r} people={q.data.people} isNew={false} saving={save.isPending} error={save.isError ? errorText(save.error) : null}
                      onSave={(d) => save.mutate({ id: r.id, d })} onCancel={() => setEditing(null)} />
                  </li>
                ) : (
                  <li key={r.id} className="flex items-start gap-3 px-4 py-3">
                    <span className="mt-0.5 w-4 shrink-0 text-center text-sm text-muted-foreground tabular-nums" aria-hidden="true">{i + 1}</span>
                    <div className={cn("min-w-0 flex-1", !r.active && "text-muted-foreground")}>
                      <p>{sentence(r, q.data.people)}</p>
                      {r.ai && r.ai !== "auto" && <OndraLine ai={r.ai} muted={!r.active} />}
                      {!r.active && <p className="text-sm">Switched off: skipped until you turn it back on.</p>}
                    </div>
                    {canEdit && (
                      <>
                        <Switch checked={r.active} onCheckedChange={(active) => change.mutate({ kind: "switch", id: r.id, active })} aria-label={`Rule ${i + 1} is ${r.active ? "on" : "off"}`} className="mt-0.5" />
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="-my-1.5 -mr-2" aria-label={`More for rule ${i + 1}`}><IconDotsVertical /></Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onSelect={() => { save.reset(); setEditing(r.id) }}>Edit</DropdownMenuItem>
                            {i > 0 && <DropdownMenuItem onSelect={() => move(i, -1)}>Move up</DropdownMenuItem>}
                            {i < rules.length - 1 && <DropdownMenuItem onSelect={() => move(i, 1)}>Move down</DropdownMenuItem>}
                            <DropdownMenuItem onSelect={() => change.mutate({ kind: "delete", id: r.id })}>Delete rule {i + 1}</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </>
                    )}
                  </li>
                ),
              )}
              {editing === "new" && (
                <li>
                  <RuleForm initial={BLANK} people={q.data.people} isNew saving={save.isPending} error={save.isError ? errorText(save.error) : null}
                    onSave={(d) => save.mutate({ id: "new", d })} onCancel={() => setEditing(null)} />
                </li>
              )}
              <li className="flex items-start gap-3 px-4 py-3">
                <span className="w-4 shrink-0" aria-hidden="true" />
                <div className="min-w-0">
                  <p>{rules.length ? "Everything else goes to the usual team." : "With no rules of your own, everything goes to the usual team."}</p>
                  <p className="text-sm text-muted-foreground">Sales, finance and shipping questions to Sales. Service questions to Service. Complaints to Managers.</p>
                </div>
              </li>
            </ol>
            <CheckMessage rules={rules} />
          </>
        )}
      </div>
    </>
  )
}

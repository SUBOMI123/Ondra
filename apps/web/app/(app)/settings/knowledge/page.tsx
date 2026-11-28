"use client"

/**
 * What Ondra knows. One job: answer the questions Ondra couldn't, once, so it can next time.
 * Unanswered questions come first (what needs a person), most-asked on top, each with a customer's own words.
 * The dealer's answers are one tab away; corrections (drafts people changed, replies rated wrong) a third.
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { api, ApiError, send } from "@/lib/api"
import { fmt } from "@/lib/time"

type Gap = { id: string; question: string; times: number; last_asked_at: string; asked: string | null }
type Answer = { id: string; question: string; answer: string; updated_at: string }
type Knowledge = { unanswered: Gap[]; answers: Answer[]; ignored: number; can_edit: boolean }
type Corrections = {
  edits: { message_id: string; before: string; after: string; at: string }[]
  rated: { message_id: string; rating: "wrong" | "tone"; note: string | null; by: string; reply: string; customer_said: string | null; at: string }[]
  good: number
}
type Tab = "unanswered" | "answers" | "corrections"

function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

function asQuestion(q: string) {
  const s = q.trim()
  return s ? `${s[0].toUpperCase()}${s.slice(1)}${/[?.!]$/.test(s) ? "" : "?"}` : ""
}

function day(iso: string) {
  return fmt(iso, { month: "short", day: "numeric" })
}

/* ------------------------------------------------------------ question and answer form */

function AnswerForm({ question, answer, submit, saving, error, onSave, onCancel }: {
  question: string; answer: string; submit: string; saving: boolean; error: string | null
  onSave: (v: { question: string; answer: string }) => void; onCancel: () => void
}) {
  const [q, setQ] = useState(question)
  const [a, setA] = useState(answer)
  return (
    <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); onSave({ question: q, answer: a }) }}>
      <div className="grid gap-2">
        <Label htmlFor="kb-q">The question, in plain words</Label>
        <Input id="kb-q" required minLength={3} maxLength={300} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Do you ship cars to Ghana?" />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="kb-a">Your answer</Label>
        <Textarea id="kb-a" required minLength={3} maxLength={4000} rows={3} value={a} onChange={(e) => setA(e.target.value)} autoFocus
          placeholder="Yes. We ship to Tema port through our freight partner; it takes about five weeks." />
        <p className="text-sm text-muted-foreground">Write it the way you&apos;d tell a new salesperson. Ondra puts it in its own words for each customer, and still hands prices, discounts and dates to a person.</p>
      </div>
      {error && <p role="alert" className="text-sm">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>{saving ? "Saving…" : submit}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  )
}

/* ------------------------------------------------------------ corrections */

function CorrectionsList({ onSaveAsAnswer }: { onSaveAsAnswer: (answer: string) => void }) {
  const q = useQuery({ queryKey: ["knowledge", "corrections"], queryFn: () => api<Corrections>("/knowledge/corrections"), retry: false })
  if (q.isPending) return <TableSkeleton rows={3} />
  if (q.isError)
    return q.error instanceof ApiError && q.error.status === 403
      ? <p className="rounded-xl border p-6 text-sm text-muted-foreground">Only owners, admins and managers can see corrections.</p>
      : <LoadError message={q.error.message} onRetry={() => q.refetch()} />
  const { edits, rated, good } = q.data
  if (edits.length === 0 && rated.length === 0)
    return (
      <div className="rounded-xl border p-6 text-sm">
        <p className="font-medium">No corrections yet</p>
        <p className="mt-1 max-w-prose text-muted-foreground">
          When someone changes one of Ondra&apos;s drafts before sending it, or rates a reply wrong or off in tone from the Inbox, it shows here so you can turn it into an answer.
          {good > 0 && ` ${good} ${good === 1 ? "reply has" : "replies have"} been rated good.`}
        </p>
      </div>
    )
  return (
    <div className="flex flex-col gap-6">
      {rated.length > 0 && (
        <section aria-labelledby="rated-h">
          <h2 id="rated-h" className="font-medium">Replies rated wrong or off in tone</h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {rated.map((r) => (
              <li key={r.message_id} className="grid gap-1.5 px-4 py-3 text-sm">
                {r.customer_said && <p className="text-muted-foreground">Customer: &ldquo;{r.customer_said}&rdquo;</p>}
                <p data-slot="ai-note" className="flex items-start gap-1.5 text-ai"><OndraMark className="mt-0.5 size-3.5 shrink-0" /><span>Ondra replied: &ldquo;{r.reply}&rdquo;</span></p>
                <p>{r.by.split(" ")[0]} rated it {r.rating === "wrong" ? "wrong" : "off in tone"} on {day(r.at)}{r.note ? `: ${r.note}` : "."}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
      {edits.length > 0 && (
        <section aria-labelledby="edits-h">
          <h2 id="edits-h" className="font-medium">Drafts someone changed before sending</h2>
          <ul className="mt-3 divide-y rounded-xl border">
            {edits.map((e) => (
              <li key={`${e.message_id}-${e.at}`} className="grid gap-1.5 px-4 py-3 text-sm">
                <p data-slot="ai-note" className="flex items-start gap-1.5 text-ai"><OndraMark className="mt-0.5 size-3.5 shrink-0" /><span>Ondra wrote: &ldquo;{e.before}&rdquo;</span></p>
                <p>Sent instead on {day(e.at)}: &ldquo;{e.after}&rdquo;</p>
                <div><Button variant="outline" size="sm" onClick={() => onSaveAsAnswer(e.after)}>Save what was sent as an answer</Button></div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

/* ------------------------------------------------------------ page */

export default function KnowledgePage() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ["knowledge"], queryFn: () => api<Knowledge>("/knowledge") })
  const [tab, setTab] = useState<Tab>("unanswered")
  // What's open for writing: a gap being answered, an answer being changed, or a new answer (with text to start from).
  const [open, setOpen] = useState<{ kind: "gap" | "answer"; id: string } | { kind: "new"; answer: string } | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ["knowledge"] })
  const save = useMutation({
    mutationFn: (v: { question: string; answer: string }) =>
      open?.kind === "gap" ? send("POST", `/knowledge/unanswered/${open.id}/answer`, v)
        : open?.kind === "answer" ? send("PUT", `/knowledge/answers/${open.id}`, v)
        : send("POST", "/knowledge/answers", v),
    onSuccess: () => {
      toast(open?.kind === "answer" ? "Answer saved." : "Saved. Ondra uses it from the next message.")
      setOpen(null)
      refresh()
    },
  })
  const act = useMutation({
    mutationFn: (job: { kind: "ignore" | "reopen-all"; id?: string } | { kind: "delete"; a: Answer }) =>
      job.kind === "ignore" ? send("POST", `/knowledge/unanswered/${job.id}/ignore`) : job.kind === "delete" ? send("DELETE", `/knowledge/answers/${job.a.id}`) : Promise.resolve(null),
    onSuccess: (_r, job) => {
      refresh()
      if (job.kind === "ignore") {
        const id = job.id
        toast("Taken off the list. Ondra will keep passing it to a person.", {
          action: { label: "Undo", onClick: () => send("POST", `/knowledge/unanswered/${id}/reopen`).then(refresh, (e) => toast(errorText(e))) },
        })
      }
      if (job.kind === "delete") {
        const a = job.a
        toast("Answer deleted. Ondra no longer knows it.", {
          action: { label: "Undo", onClick: () => send("POST", "/knowledge/answers", { question: a.question, answer: a.answer }).then(refresh, (e) => toast(errorText(e))) },
        })
      }
    },
    onError: (e) => toast(errorText(e)),
  })
  const start = (o: typeof open) => { save.reset(); setOpen(o) }
  const data = q.data
  const canEdit = !!data?.can_edit
  const formError = save.isError ? errorText(save.error) : null

  return (
    <>
      <SiteHeader title="What Ondra knows" />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6 lg:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/settings" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <IconArrowLeft className="size-4" aria-hidden="true" /> Settings
          </Link>
          {canEdit && tab === "answers" && open === null && (
            <Button onClick={() => start({ kind: "new", answer: "" })}><IconPlus /> Add an answer</Button>
          )}
        </div>
        <Tabs value={tab} onValueChange={(v) => { setTab(v as Tab); setOpen(null) }}>
          <TabsList>
            <TabsTrigger value="unanswered">Unanswered{data && <span className="ml-1.5 text-muted-foreground tabular-nums">{data.unanswered.length}</span>}</TabsTrigger>
            <TabsTrigger value="answers">Answers{data && <span className="ml-1.5 text-muted-foreground tabular-nums">{data.answers.length}</span>}</TabsTrigger>
            <TabsTrigger value="corrections">Corrections</TabsTrigger>
          </TabsList>
        </Tabs>

        {open?.kind === "new" && (
          <div className="rounded-xl border p-4">
            <AnswerForm key={`new-${open.answer}`} question="" answer={open.answer} submit="Add answer" saving={save.isPending} error={formError}
              onSave={(v) => save.mutate(v)} onCancel={() => setOpen(null)} />
          </div>
        )}

        {q.isPending ? (
          <TableSkeleton rows={5} />
        ) : q.isError ? (
          <LoadError message={q.error.message} onRetry={() => q.refetch()} />
        ) : tab === "unanswered" ? (
          q.data.unanswered.length === 0 ? (
            <div className="rounded-xl border p-6 text-sm">
              <p className="font-medium">Nothing waiting for an answer</p>
              <p className="mt-1 max-w-prose text-muted-foreground">
                When a customer asks something Ondra can&apos;t answer from what you&apos;ve told it, Ondra passes them to a person and the question lands here. Answer it once and Ondra can from then on.
                {q.data.ignored > 0 && ` ${q.data.ignored} ${q.data.ignored === 1 ? "question was" : "questions were"} taken off the list.`}
              </p>
            </div>
          ) : (
            <ul className="divide-y rounded-xl border">
              {q.data.unanswered.map((g) => (
                <li key={g.id} className="px-4 py-3">
                  {open?.kind === "gap" && open.id === g.id ? (
                    <div className="grid gap-4">
                      {g.asked && <p className="text-sm text-muted-foreground">A customer asked: &ldquo;{g.asked}&rdquo;</p>}
                      <AnswerForm question={asQuestion(g.question)} answer="" submit="Save answer" saving={save.isPending} error={formError}
                        onSave={(v) => save.mutate(v)} onCancel={() => setOpen(null)} />
                    </div>
                  ) : (
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{asQuestion(g.question)}</p>
                        {g.asked && <p className="truncate text-sm text-muted-foreground" title={g.asked}>A customer asked: &ldquo;{g.asked}&rdquo;</p>}
                        <p className="text-sm text-muted-foreground">
                          Asked {g.times === 1 ? "once" : <><span className="tabular-nums">{g.times}</span> times</>}, last on {day(g.last_asked_at)}
                        </p>
                      </div>
                      {canEdit && (
                        <>
                          <Button size="sm" onClick={() => start({ kind: "gap", id: g.id })}>Answer</Button>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="-mr-2" aria-label={`More for: ${g.question}`}><IconDotsVertical /></Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onSelect={() => act.mutate({ kind: "ignore", id: g.id })}>A person should always handle this</DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )
        ) : tab === "answers" ? (
          q.data.answers.length === 0 ? (
            <p className="rounded-xl border p-6 text-sm text-muted-foreground">No answers yet. Add what customers ask most: hours, where you are, what you service, how shipping works.</p>
          ) : (
            <ul className="divide-y rounded-xl border">
              {q.data.answers.map((a) => (
                <li key={a.id} className="px-4 py-3">
                  {open?.kind === "answer" && open.id === a.id ? (
                    <AnswerForm question={a.question} answer={a.answer} submit="Save answer" saving={save.isPending} error={formError}
                      onSave={(v) => save.mutate(v)} onCancel={() => setOpen(null)} />
                  ) : (
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{a.question}</p>
                        <p className="line-clamp-2 text-sm text-muted-foreground">{a.answer}</p>
                      </div>
                      {canEdit && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="-my-1.5 -mr-2" aria-label={`More for: ${a.question}`}><IconDotsVertical /></Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onSelect={() => start({ kind: "answer", id: a.id })}>Edit</DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => act.mutate({ kind: "delete", a })}>Delete this answer</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )
        ) : (
          <CorrectionsList onSaveAsAnswer={(answer) => { setTab("answers"); start({ kind: "new", answer }) }} />
        )}
      </div>
    </>
  )
}

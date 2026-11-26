"use client"

/**
 * Calls. One job: what happened on the phone, and who needs a call back.
 * A live call sits on top with the two things a person can do (listen, take over). Call-backs come next,
 * then the log, where each call says its outcome in words. Details open in a side sheet.
 * VIP calls never show an Ondra summary or transcript: Ondra doesn't take them.
 */

import {
  IconCrownFilled,
  IconHeadphones,
  IconPhoneCall,
  IconPhoneIncoming,
  IconPhoneOutgoing,
  IconPhoneX,
  IconPlayerPlayFilled,
} from "@tabler/icons-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { CALLS, LIVE_CALL, type CallLog } from "@/lib/examples"
import { cn } from "@/lib/utils"

function clock(s: number) {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`
}

function LiveCall() {
  const [secs, setSecs] = useState(LIVE_CALL.seconds)
  useEffect(() => {
    const t = setInterval(() => setSecs((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <section aria-label="Live call" className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-ai/30 bg-ai-subtle/40 p-4">
      <span className="relative flex size-9 shrink-0 items-center justify-center rounded-full bg-ai-subtle text-ai">
        <IconPhoneCall className="size-4" aria-hidden="true" />
        <span className="absolute inset-0 rounded-full border border-ai/40 motion-safe:animate-ping" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 font-medium">
          <OndraMark className="size-4 text-ai" /> Ondra is on a call now
        </p>
        <p className="text-sm text-muted-foreground">
          {LIVE_CALL.caller}. {LIVE_CALL.reason}. <span className="tabular-nums">{clock(secs)}</span>
        </p>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={() => toast("Listening in. The caller can't hear you.")}>
          <IconHeadphones /> Listen
        </Button>
        <Button size="sm" onClick={() => toast("Transferring the call to you. Ondra will tell the caller.")}>
          Take the call
        </Button>
      </div>
    </section>
  )
}

function DirectionIcon({ c }: { c: CallLog }) {
  const Icon = c.handledBy === "missed" ? IconPhoneX : c.direction === "in" ? IconPhoneIncoming : IconPhoneOutgoing
  return (
    <Icon
      className={cn("size-4 shrink-0", c.handledBy === "missed" && c.vip ? "text-vip" : c.handledBy === "ondra" ? "text-ai" : "text-muted-foreground")}
      aria-label={c.handledBy === "missed" ? "Missed call" : c.direction === "in" ? "Incoming call" : "Outgoing call"}
    />
  )
}

function CallRow({ c, onOpen }: { c: CallLog; onOpen: () => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        data-vip={c.vip || undefined}
        className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 px-4 py-3 text-left outline-none hover:bg-muted/50 focus-visible:bg-muted"
      >
        <span className="pt-1">
          <DirectionIcon c={c} />
        </span>
        <span className="min-w-0">
          <span className="flex items-center gap-1.5 font-medium">
            {c.vip && <IconCrownFilled className="size-3.5 shrink-0 text-vip" aria-label="VIP" />}
            <span className="truncate">{c.caller}</span>
          </span>
          <span className="block truncate text-sm text-muted-foreground">{c.outcome}</span>
        </span>
        <span className="text-right text-xs text-muted-foreground tabular-nums">
          {c.time}
          {c.duration !== "0:00" && <span className="block">{c.duration}</span>}
        </span>
      </button>
    </li>
  )
}

export default function CallsPage() {
  const [open, setOpen] = useState<CallLog | null>(null)
  const callbacks = CALLS.filter((c) => c.needsCallback)
  const log = CALLS.filter((c) => !c.needsCallback)
  return (
    <>
      <SiteHeader title="Calls" note="Example data until voice goes live in Step 5" />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-6 lg:px-6">
        <LiveCall />

        <section aria-labelledby="callbacks">
          <h2 id="callbacks" className="mb-2 text-sm font-medium text-muted-foreground">
            Call back <span className="tabular-nums">{callbacks.length}</span>
          </h2>
          <ul className="divide-y rounded-xl border">
            {callbacks.map((c) => (
              <CallRow key={c.id} c={c} onOpen={() => setOpen(c)} />
            ))}
          </ul>
        </section>

        <section aria-labelledby="log">
          <h2 id="log" className="mb-2 text-sm font-medium text-muted-foreground">
            Earlier
          </h2>
          <ul className="divide-y rounded-xl border">
            {log.map((c) => (
              <CallRow key={c.id} c={c} onOpen={() => setOpen(c)} />
            ))}
          </ul>
        </section>
      </div>

      <Sheet open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <SheetContent className="w-full sm:max-w-md" data-vip={open?.vip || undefined}>
          {open && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-1.5">
                  {open.vip && <IconCrownFilled className="size-4 text-vip" aria-label="VIP" />}
                  {open.caller}
                </SheetTitle>
                <SheetDescription>
                  {open.number}, {open.time}
                  {open.duration !== "0:00" ? `, ${open.duration}` : ""}
                </SheetDescription>
              </SheetHeader>
              <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 pb-4 text-sm">
                {open.needsCallback && (
                  <Button className="self-start" onClick={() => toast(`Calling ${open.caller} from the dealership's number…`)}>
                    <IconPhoneCall /> Call back
                  </Button>
                )}
                {open.handledBy === "missed" ? (
                  <p className="text-muted-foreground">{open.outcome}</p>
                ) : (
                  <>
                    {open.summary && (
                      <section data-slot={open.handledBy === "ondra" ? "ai-summary" : undefined}>
                        <h3 className={cn("flex items-center gap-1.5 text-xs font-medium", open.handledBy === "ondra" ? "text-ai" : "text-muted-foreground")}>
                          {open.handledBy === "ondra" ? (
                            <>
                              <OndraMark className="size-3.5" /> Summary by Ondra
                            </>
                          ) : (
                            `Notes from ${open.staff}`
                          )}
                        </h3>
                        <p className="mt-1.5 leading-relaxed">{open.summary}</p>
                      </section>
                    )}
                    <Button variant="outline" size="sm" className="self-start">
                      <IconPlayerPlayFilled /> Play recording, {open.duration}
                    </Button>
                    {open.transcript && (
                      <section>
                        <h3 className="mb-2 text-xs font-medium text-muted-foreground">Transcript</h3>
                        <ol className="flex flex-col gap-2.5">
                          {open.transcript.map((t, i) => (
                            <li key={i} className="grid grid-cols-[4rem_minmax(0,1fr)] gap-3">
                              <span className={cn("text-xs font-medium", t.who === "ondra" ? "text-ai" : "text-muted-foreground")}>
                                {t.who === "ondra" ? "Ondra" : t.who === "caller" ? "Caller" : open.staff}
                              </span>
                              <span>{t.text}</span>
                            </li>
                          ))}
                        </ol>
                      </section>
                    )}
                  </>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}

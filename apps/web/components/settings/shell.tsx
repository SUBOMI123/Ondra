"use client"

/**
 * The frame every settings page shares: the page's name in the header, a way back to the Settings index, one line on
 * what the page decides, and a note when you can look but not change. Plus the bits the forms share.
 */

import { IconArrowLeft } from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"

import { SiteHeader } from "@/components/dashboard/site-header"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"

export type Day = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"
export type Business = { name: string; timezone: string; hours: Record<Day, [string, string] | null> }
export type Replies = {
  draft_mode: boolean
  price_disclosure: "none" | "listed" | "range"
  handoff_triggers: string[]
  never_say: string[]
  ai_disclosure: "when_asked" | "upfront"
}
export type Channel = { id: string; channel: "sms" | "whatsapp" | "email" | "phone"; address: string; provider: string; active: boolean; live: boolean }
export type SettingsData = { business: Business; replies: Replies; channels: Channel[]; can_edit: boolean; timezones: string[] }

export function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: () => api<SettingsData>("/settings") })
}

export function errorText(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong. Try again."
}

export function SettingsShell({ title, description, readOnly, wide, children }: {
  title: string
  description: string
  /** Shown under the description when this person can look but not change. */
  readOnly?: string | false
  wide?: boolean
  children: React.ReactNode
}) {
  return (
    <>
      <SiteHeader title={title} />
      <div className={`mx-auto flex w-full flex-col gap-6 px-4 py-6 lg:px-6 ${wide ? "max-w-4xl" : "max-w-3xl"}`}>
        <div className="flex flex-col gap-3">
          <Link href="/settings" className="flex w-fit items-center gap-1.5 rounded-sm text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
            <IconArrowLeft className="size-4" aria-hidden="true" /> Settings
          </Link>
          <p className="max-w-prose text-sm text-pretty text-muted-foreground">{description}</p>
          {readOnly && <p className="text-sm">{readOnly}</p>}
        </div>
        {children}
      </div>
    </>
  )
}

/** For pages that read /settings: a skeleton while it loads, and a retry when it doesn't. */
export function WithSettings({ children }: { children: (d: SettingsData) => React.ReactNode }) {
  const q = useSettings()
  if (q.isPending)
    return (
      <div className="flex flex-col gap-4" aria-label="Loading">
        <Skeleton className="h-10 w-full max-w-xl" />
        <Skeleton className="h-72 w-full max-w-xl" />
      </div>
    )
  if (q.isError)
    return (
      <div role="alert" className="rounded-xl border p-4 text-sm">
        <p>This didn&apos;t load. {errorText(q.error)}</p>
        <Button variant="outline" className="mt-3" onClick={() => q.refetch()}>Try again</Button>
      </div>
    )
  return <>{children(q.data)}</>
}

export const VIEW_ONLY = "View only. Owners and admins can change these."

/** Save row for a form: the button is enabled only when something changed. */
export function SaveBar({ dirty, saving, error, onSave, onReset }: {
  dirty: boolean; saving: boolean; error: string | null; onSave: () => void; onReset: () => void
}) {
  return (
    <div className="mt-6 flex flex-wrap items-center gap-3">
      <Button onClick={onSave} disabled={!dirty || saving}>{saving ? "Saving…" : "Save changes"}</Button>
      {dirty && !saving && <Button variant="ghost" onClick={onReset}>Discard</Button>}
      {error && <p role="alert" className="text-sm">{error}</p>}
    </div>
  )
}

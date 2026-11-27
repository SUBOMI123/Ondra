/**
 * How a VIP looks, everywhere: a small "VIP" tag in ink, and a ring around their initials where there's an avatar.
 * No crown and no red (founder, 2026-11-27): red now means overdue and nothing else, so a VIP no longer looks like
 * a problem. The word does the work; the ring makes them findable in a list at a glance.
 * A VIP surface still never shows anything Ondra-blue: no drafts, summaries or "let Ondra reply" (ondra-ui rule).
 */

import { cn } from "@/lib/utils"

export function VipTag({ className, size = "sm" }: { className?: string; size?: "sm" | "lg" }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-[4px] border border-vip/50 font-semibold leading-none text-vip",
        size === "lg" ? "h-6 px-1.5 text-xs" : "h-[18px] px-1 text-[11px]",
        className,
      )}
      title="VIP: always handled by a person, never by Ondra"
    >
      VIP
    </span>
  )
}

export function initials(name: string) {
  const parts = name.replace(/^\+/, "").split(/\s+/).filter(Boolean)
  if (!parts.length || /^\d/.test(parts[0])) return "#"
  return ((parts[0][0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase()
}

/** A client's initials. A VIP gets a ring in ink, offset from the circle. */
export function ClientAvatar({ name, vip, className }: { name: string; vip?: boolean; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground",
        vip && "bg-background text-foreground ring-[1.5px] ring-vip ring-offset-2 ring-offset-background",
        className,
      )}
    >
      {initials(name)}
    </span>
  )
}

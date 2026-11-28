/**
 * Shortcuts: one-click slices of the Inbox, linked from the sidebar. The sidebar's counts and the Inbox's
 * filter both use `matches` below, so the number next to a view is always the number of rows it opens.
 */

import { IconMoonStars, IconPencilCheck, IconUserStar, type Icon } from "@tabler/icons-react"

export type ViewRow = {
  bucket: string
  drafts?: number
  after_hours_lead?: boolean
  contact: { is_vip: boolean }
}

export type Shortcut = {
  id: string
  name: string
  icon: Icon
  /** Only admins and managers, who are the people who can see VIPs. */
  vipsOnly?: boolean
  matches: (r: ViewRow) => boolean
  empty: string
}

export const SHORTCUTS: Shortcut[] = [
  {
    id: "drafts",
    name: "Drafts to approve",
    icon: IconPencilCheck,
    matches: (r) => (r.drafts ?? 0) > 0,
    empty: "No drafts waiting. Anything Ondra writes in draft mode shows up here for you to approve.",
  },
  {
    id: "vips",
    name: "VIPs waiting",
    icon: IconUserStar,
    vipsOnly: true,
    matches: (r) => r.contact.is_vip && r.bucket === "needs",
    empty: "No VIP is waiting for you.",
  },
  {
    id: "after-hours",
    name: "After-hours leads",
    icon: IconMoonStars,
    matches: (r) => !!r.after_hours_lead,
    empty: "No leads came in while you were closed this past week.",
  },
]

export const viewById = (id: string | null) => SHORTCUTS.find((v) => v.id === id) ?? null

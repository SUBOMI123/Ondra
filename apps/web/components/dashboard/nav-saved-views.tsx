"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"

import { ACTIVE_ITEM } from "@/lib/nav"
import { SAVED_VIEWS, type ViewRow } from "@/lib/saved-views"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

/** Saved views open the Inbox filtered. Counts come from the Inbox's own list, so they match what opens. */
export function NavSavedViews({ rows, seesVips }: { rows: ViewRow[] | undefined; seesVips: boolean }) {
  const pathname = usePathname()
  const filter = useSearchParams().get("filter")
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Saved views</SidebarGroupLabel>
      <SidebarMenu>
        {SAVED_VIEWS.filter((v) => seesVips || !v.vipsOnly).map((v) => {
          const active = pathname === "/inbox" && filter === v.id
          const n = rows?.filter(v.matches).length
          return (
            <SidebarMenuItem key={v.id}>
              <SidebarMenuButton asChild isActive={active} className={ACTIVE_ITEM}>
                <Link href={`/inbox?filter=${v.id}`} aria-current={active ? "page" : undefined}>
                  <v.icon />
                  <span>{v.name}</span>
                </Link>
              </SidebarMenuButton>
              {!!n && <SidebarMenuBadge>{n}</SidebarMenuBadge>}
            </SidebarMenuItem>
          )
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}

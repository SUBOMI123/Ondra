"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"

import { ACTIVE_ITEM } from "@/lib/nav"
import { SHORTCUTS, type ViewRow } from "@/lib/shortcuts"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

/**
 * Shortcuts open the Inbox filtered. Counts come from the Inbox's own list, so they match what opens.
 * "VIPs waiting" shows to owners and managers, and to anyone who looks after a VIP: the Inbox list only holds the
 * VIPs a person may see, so for them it's their own.
 */
export function NavShortcuts({ rows, seesVips }: { rows: ViewRow[] | undefined; seesVips: boolean }) {
  const pathname = usePathname()
  const filter = useSearchParams().get("filter")
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Shortcuts</SidebarGroupLabel>
      <SidebarMenu>
        {SHORTCUTS.filter((v) => !v.vipsOnly || seesVips || !!rows?.some((r) => r.contact.is_vip)).map((v) => {
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

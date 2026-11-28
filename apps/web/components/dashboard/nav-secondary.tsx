"use client"

import * as React from "react"
import { type Icon } from "@tabler/icons-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { useShell } from "@/components/shell/shell"
import { ACTIVE_ITEM, isActivePath } from "@/lib/nav"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

export function NavSecondary({
  items,
  ...props
}: {
  items: ({ title: string; icon: Icon } & ({ url: string; action?: never } | { action: "search"; url?: never }))[]
} & React.ComponentPropsWithoutRef<typeof SidebarGroup>) {
  const pathname = usePathname()
  const { openSearch } = useShell()
  return (
    <SidebarGroup {...props}>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.title}>
              {item.action === "search" ? (
                <SidebarMenuButton onClick={openSearch} tooltip="Search (⌘K)">
                  <item.icon />
                  <span>{item.title}</span>
                </SidebarMenuButton>
              ) : (
                <SidebarMenuButton asChild isActive={isActivePath(pathname, item.url)} className={ACTIVE_ITEM}>
                  <Link href={item.url} aria-current={isActivePath(pathname, item.url) ? "page" : undefined}>
                    <item.icon />
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              )}
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

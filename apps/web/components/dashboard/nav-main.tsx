"use client"

import { IconPencilPlus, type Icon } from "@tabler/icons-react"
import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"

import { useShell } from "@/components/shell/shell"
import { ACTIVE_ITEM, isActivePath } from "@/lib/nav"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

export function NavMain({
  items,
}: {
  items: {
    title: string
    url: string
    icon?: Icon
    badge?: string
    soon?: string
  }[]
}) {
  const pathname = usePathname()
  // On a shortcut (/inbox?filter=…) the shortcut is the highlighted item, not Inbox: one place you are, one highlight.
  const onShortcut = !!useSearchParams().get("filter")
  const { openCompose } = useShell()
  const active = (url: string) => isActivePath(pathname, url) && !(url === "/inbox" && onShortcut)
  return (
    <SidebarGroup>
      <SidebarGroupContent className="flex flex-col gap-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="New message"
              onClick={() => openCompose()}
              className="min-w-8 bg-primary text-primary-foreground duration-200 ease-linear hover:bg-primary/90 hover:text-primary-foreground active:bg-primary/90 active:text-primary-foreground"
            >
              <IconPencilPlus />
              <span>New message</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.title}>
              {item.soon ? (
                <SidebarMenuButton tooltip={`${item.title} arrives in ${item.soon}`} aria-disabled="true" className="opacity-50">
                  {item.icon && <item.icon />}
                  <span>{item.title}</span>
                </SidebarMenuButton>
              ) : (
                <SidebarMenuButton asChild tooltip={item.title} isActive={active(item.url)} className={ACTIVE_ITEM}>
                  <Link href={item.url} aria-current={active(item.url) ? "page" : undefined}>
                    {item.icon && <item.icon />}
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              )}
              {item.badge && <SidebarMenuBadge>{item.badge}</SidebarMenuBadge>}
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

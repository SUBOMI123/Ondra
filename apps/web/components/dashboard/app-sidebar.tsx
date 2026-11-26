"use client"

import { useQuery } from "@tanstack/react-query"
import * as React from "react"

import { api } from "@/lib/api"
import {
  IconCalendarEvent,
  IconCar,
  IconChecklist,
  IconCrown,
  IconHelp,
  IconLayoutDashboard,
  IconLayoutKanban,
  IconMessages,
  IconMoonStars,
  IconPhone,
  IconSearch,
  IconPencilCheck,
  IconSettings,
  IconUsers,
} from "@tabler/icons-react"

import { useAuth } from "@/components/providers"
import { NavDocuments } from "@/components/dashboard/nav-documents"
import { NavMain } from "@/components/dashboard/nav-main"
import { NavSecondary } from "@/components/dashboard/nav-secondary"
import { NavUser } from "@/components/dashboard/nav-user"
import { OndraMark } from "@/components/ondra-mark"
import Wordmark from "@/components/wordmark"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

// Screens that exist link to their page; the rest arrive with their build step (docs/ROADMAP.md).
const data = {
  navMain: [
    { title: "Today", url: "/", icon: IconLayoutDashboard },
    { title: "Inbox", url: "/inbox", icon: IconMessages },
    { title: "Calls", url: "/calls", icon: IconPhone },
    { title: "Calendar", url: "/calendar", icon: IconCalendarEvent },
    { title: "Clients", url: "/clients", icon: IconUsers },
    { title: "Deals", url: "/deals", icon: IconLayoutKanban },
    { title: "Tasks", url: "/tasks", icon: IconChecklist },
    { title: "Inventory", url: "/inventory", icon: IconCar },
  ],
  navSecondary: [
    { title: "Settings", url: "/settings", icon: IconSettings },
    { title: "Help", url: "#", icon: IconHelp },
    { title: "Search", url: "#", icon: IconSearch },
  ],
  views: [
    { name: "VIPs waiting", url: "#", icon: IconCrown },
    { name: "Drafts to approve", url: "#", icon: IconPencilCheck },
    { name: "After-hours leads", url: "#", icon: IconMoonStars },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { me } = useAuth()
  // Real counts: conversations that need a person, and my open tasks. Same queries as those pages, so live
  // updates refresh both. No badge when the count is zero or unknown.
  const inbox = useQuery({ queryKey: ["conversations"], queryFn: () => api<{ counts: { needs: number } }>("/conversations?view=all"), enabled: !!me })
  const tasks = useQuery({ queryKey: ["tasks", "mine", "open"], queryFn: () => api<{ items: unknown[] }>("/tasks?scope=mine&status=open"), enabled: !!me })
  const badge = (n?: number) => (n ? String(n) : undefined)
  const navMain = data.navMain.map((item) =>
    item.url === "/inbox" ? { ...item, badge: badge(inbox.data?.counts.needs) }
      : item.url === "/tasks" ? { ...item, badge: badge(tasks.data?.items.length) } : item,
  )
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild className="data-[slot=sidebar-menu-button]:p-1.5!">
              <a href="#" aria-label="Ondra, Today">
                <span className="flex h-5 items-center group-data-[collapsible=icon]:hidden"><Wordmark className="h-[18px] w-auto" /></span>
                <OndraMark className="hidden size-5! text-foreground group-data-[collapsible=icon]:block" />
                <span className="ml-auto truncate text-xs font-normal text-muted-foreground group-data-[collapsible=icon]:hidden">{me?.tenant_name}</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navMain} />
        <NavDocuments items={data.views} />
        <NavSecondary items={data.navSecondary} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={{ name: me?.name ?? "", email: me?.email ?? "", avatar: "" }} />
      </SidebarFooter>
    </Sidebar>
  )
}

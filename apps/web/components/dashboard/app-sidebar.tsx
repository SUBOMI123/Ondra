"use client"

import * as React from "react"
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
    { title: "Inbox", url: "#", icon: IconMessages, soon: "Step 3" },
    { title: "Calls", url: "#", icon: IconPhone, soon: "Step 5" },
    { title: "Calendar", url: "#", icon: IconCalendarEvent, soon: "Step 4" },
    { title: "Clients", url: "/clients", icon: IconUsers },
    { title: "Deals", url: "#", icon: IconLayoutKanban, soon: "Step 3" },
    { title: "Tasks", url: "#", icon: IconChecklist, soon: "Step 3" },
    { title: "Inventory", url: "/inventory", icon: IconCar },
  ],
  navSecondary: [
    { title: "Settings", url: "#", icon: IconSettings },
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
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild className="data-[slot=sidebar-menu-button]:p-1.5!">
              <a href="#" aria-label="Ondra, Today">
                <span className="flex h-5 items-center"><Wordmark className="h-[18px] w-auto" /></span>
                <span className="ml-auto truncate text-xs font-normal text-muted-foreground">{me?.tenant_name}</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
        <NavDocuments items={data.views} />
        <NavSecondary items={data.navSecondary} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={{ name: me?.name ?? "", email: me?.email ?? "", avatar: "" }} />
      </SidebarFooter>
    </Sidebar>
  )
}

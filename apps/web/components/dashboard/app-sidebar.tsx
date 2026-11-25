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

// Example user and saved views for the UI prototype; real data arrives with Step 1 (auth) and Step 3 (inbox).
const data = {
  user: { name: "Daniel Okafor", email: "daniel@prestigemotors.com", avatar: "" },
  navMain: [
    { title: "Today", url: "#", icon: IconLayoutDashboard, active: true },
    { title: "Inbox", url: "#", icon: IconMessages, badge: "12" },
    { title: "Calls", url: "#", icon: IconPhone },
    { title: "Calendar", url: "#", icon: IconCalendarEvent },
    { title: "Clients", url: "#", icon: IconUsers },
    { title: "Deals", url: "#", icon: IconLayoutKanban },
    { title: "Tasks", url: "#", icon: IconChecklist, badge: "2" },
    { title: "Inventory", url: "#", icon: IconCar },
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
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild className="data-[slot=sidebar-menu-button]:p-1.5!">
              <a href="#" aria-label="Ondra, Today">
                <span className="flex h-5 items-center"><Wordmark className="h-[18px] w-auto" /></span>
                <span className="ml-auto truncate text-xs font-normal text-muted-foreground">Prestige Motors</span>
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
        <NavUser user={data.user} />
      </SidebarFooter>
    </Sidebar>
  )
}

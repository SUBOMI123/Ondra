"use client"

import { IconSearch } from "@tabler/icons-react"
import { useEffect, useState } from "react"

import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { zoneNote } from "@/lib/time"

/** When the reader isn't in the dealership's time zone, every time on screen is the dealership's: say so. */
function ZoneNote() {
  const [note, setNote] = useState<string | null>(null)
  useEffect(() => {
    setNote(zoneNote())
  }, [])
  return note ? <span className="mr-1 hidden text-xs text-muted-foreground tabular-nums sm:inline" title="Times are shown in the dealership's time zone">Times in {note}</span> : null
}

export function SiteHeader({ title = "Today", note }: { title?: string; note?: string }) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />
        <h1 className="text-base font-medium">{title}</h1>
        {note && <span className="hidden text-sm text-muted-foreground lg:inline">{note}</span>}
        <div className="ml-auto flex items-center gap-2">
          <ZoneNote />
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Search clients, cars and messages">
            <IconSearch />
          </Button>
          <Button variant="outline" size="sm" className="hidden w-72 justify-start gap-2 text-muted-foreground lg:flex">
            <IconSearch />
            <span className="truncate">Search clients, cars, messages</span>
            <Kbd className="ml-auto">⌘K</Kbd>
          </Button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

"use client"

import { IconSearch } from "@tabler/icons-react"
import { useEffect, useState } from "react"

import { useShell } from "@/components/shell/shell"

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
  return note ? <span className="mr-1 hidden text-xs text-muted-foreground tabular-nums xl:inline" title="Times are shown in the dealership's time zone">Times in {note}</span> : null
}

/** `whose`: the Mine / Everyone switch, right after the title, on every screen that has one. */
export function SiteHeader({ title = "Today", note, whose }: { title?: string; note?: string; whose?: React.ReactNode }) {
  const { openSearch } = useShell()
  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />
        <h1 className="text-base font-medium">{title}</h1>
        {whose && <div className="ml-2 sm:ml-3">{whose}</div>}
        {note && <span className="hidden text-sm text-muted-foreground lg:inline">{note}</span>}
        <div className="ml-auto flex items-center gap-2">
          <ZoneNote />
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Search clients, cars and messages" onClick={openSearch}>
            <IconSearch />
          </Button>
          <Button variant="outline" size="sm" className="hidden w-56 justify-start gap-2 text-muted-foreground lg:flex xl:w-72" onClick={openSearch}>
            <IconSearch />
            <span className="truncate">Search clients, cars, messages</span>
            <Kbd className="ml-auto">⌘K</Kbd>
          </Button>
          {/* On a phone the theme lives in the account menu, so the header keeps room for the title and switch. */}
          <div className="hidden sm:block"><ThemeToggle /></div>
        </div>
      </div>
    </header>
  )
}

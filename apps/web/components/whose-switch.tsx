"use client"

/**
 * Mine / Dealership, as the page title itself: "My inbox" or "Dealership inbox", with a chevron to switch. The title
 * says what you're looking at, so the scope is read as part of it rather than as one more control beside it (the
 * old segmented pill sat between the title and the search and read as a second navigation).
 */

import { IconCheck, IconChevronDown } from "@tabler/icons-react"

import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import type { Whose } from "@/lib/whose"

const OPTIONS: [Whose, string, string][] = [
  ["mine", "My", "Your clients and your work"],
  ["everyone", "Dealership", "Everything at the dealership, everyone's work"],
]

export function WhoseTitle({ value, onChange, noun }: { value: Whose; onChange: (w: Whose) => void; noun: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        data-whose={value}
        aria-label={`${value === "mine" ? "My" : "Dealership"} ${noun}. Switch between yours and the whole dealership's`}
        className="-mx-1.5 flex items-center gap-1 rounded-md px-1.5 py-1 text-base font-medium outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring data-[state=open]:bg-muted"
      >
        <span>{value === "mine" ? "My" : "Dealership"} {noun}</span>
        <IconChevronDown className="size-4 text-muted-foreground" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {OPTIONS.map(([key, label, detail]) => (
          <DropdownMenuItem key={key} onSelect={() => onChange(key)} className="items-start gap-2 py-2">
            <IconCheck className={`mt-0.5 size-4 ${value === key ? "" : "invisible"}`} aria-hidden="true" />
            <span className="flex flex-col">
              <span>{label} {noun}</span>
              <span className="text-xs text-muted-foreground">{detail}</span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

"use client"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Whose } from "@/lib/whose"

/** Mine / Everyone, in the page header, the same on every screen that has it. */
export function WhoseSwitch({ value, onChange, what }: { value: Whose; onChange: (w: Whose) => void; what: string }) {
  return (
    <Tabs value={value} onValueChange={(v) => onChange(v as Whose)}>
      <TabsList aria-label={`Whose ${what}`} className="h-8">
        <TabsTrigger value="mine" className="px-2.5 text-xs sm:text-sm">Mine</TabsTrigger>
        <TabsTrigger value="everyone" className="px-2.5 text-xs sm:text-sm">Everyone</TabsTrigger>
      </TabsList>
    </Tabs>
  )
}

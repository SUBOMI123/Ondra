"use client"

import { ChartAreaInteractive } from "@/components/dashboard/chart-area-interactive"
import { DataTable } from "@/components/dashboard/data-table"
import { SectionCards } from "@/components/dashboard/section-cards"
import { SiteHeader } from "@/components/dashboard/site-header"

import data from "@/components/dashboard/data.json"

// Today. Metrics, chart and leads are example data until the inbox (Step 3) and analytics (Step 9) exist.
export default function TodayPage() {
  return (
    <>
      <SiteHeader title="Today" note="Example numbers until conversations are live" />
      <div className="flex flex-1 flex-col">
        <div className="@container/main flex flex-1 flex-col gap-2">
          <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
            <SectionCards />
            <div className="px-4 lg:px-6">
              <ChartAreaInteractive />
            </div>
            <DataTable data={data as Parameters<typeof DataTable>[0]["data"]} />
          </div>
        </div>
      </div>
    </>
  )
}

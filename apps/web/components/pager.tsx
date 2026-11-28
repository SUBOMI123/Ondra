"use client"

/** Page through a long list: where you are ("26–50 of 312 clients", "Page 2 of 13") and Previous / Next. One page
 * only: just the count. Moving to another page brings the top of the list back into view. */

import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react"

import { Button } from "@/components/ui/button"

export function Pager({ page, perPage, total, noun, onPage }: { page: number; perPage: number; total: number; noun: [string, string]; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / perPage))
  const from = total === 0 ? 0 : page * perPage + 1
  const to = Math.min(total, (page + 1) * perPage)
  const go = (p: number) => {
    onPage(p)
    document.querySelector("main")?.scrollTo({ top: 0, behavior: "smooth" })
    window.scrollTo({ top: 0, behavior: "smooth" })
  }
  return (
    <nav aria-label="Pages" className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground tabular-nums">
      <span>{from}–{to} of {total.toLocaleString("en-US")} {total === 1 ? noun[0] : noun[1]}</span>
      {pages > 1 && (
        <span className="flex items-center gap-3">
          <span>Page {page + 1} of {pages}</span>
          <span className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => go(page - 1)}><IconChevronLeft /> Previous</Button>
            <Button variant="outline" size="sm" disabled={page + 1 >= pages} onClick={() => go(page + 1)}>Next <IconChevronRight /></Button>
          </span>
        </span>
      )}
    </nav>
  )
}

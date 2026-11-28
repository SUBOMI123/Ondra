"use client"

/** Search and New message, opened from anywhere: the sidebar, the header bar, ⌘K (Ctrl+K), or a page that wants to
 * write to a particular client (`openCompose({ id, name })`). One of each, shared, so they behave the same everywhere. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { ComposeDialog, type ComposeTo } from "./compose"
import { SearchPalette } from "./search"

type Shell = { openSearch: () => void; openCompose: (to?: ComposeTo) => void }
const ShellContext = createContext<Shell>({ openSearch: () => {}, openCompose: () => {} })

export function useShell() {
  return useContext(ShellContext)
}

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [searching, setSearching] = useState(false)
  const [composing, setComposing] = useState(false)
  const [to, setTo] = useState<ComposeTo | null>(null)
  const openSearch = useCallback(() => setSearching(true), [])
  const openCompose = useCallback((who?: ComposeTo) => { setTo(who ?? null); setComposing(true) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setSearching((s) => !s)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const value = useMemo(() => ({ openSearch, openCompose }), [openSearch, openCompose])
  return (
    <ShellContext.Provider value={value}>
      {children}
      <SearchPalette open={searching} onOpenChange={setSearching} />
      <ComposeDialog open={composing} onOpenChange={setComposing} to={to} />
    </ShellContext.Provider>
  )
}

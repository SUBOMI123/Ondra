"use client"

/**
 * Whose work a screen shows: "mine" or "everyone" (docs/PLAN.md item 6). The same switch on Inbox, Calls, Calendar,
 * Tasks and Deals. Default by role: salespeople and service see their own work first, admins and managers see the
 * dealership. The choice is remembered per screen, in this browser only (a convenience, not a setting).
 */

import { useCallback, useEffect, useState } from "react"

import { useAuth } from "@/components/providers"

export type Whose = "mine" | "everyone"
export type WhoseScreen = "inbox" | "calls" | "calendar" | "tasks" | "deals"

export function defaultWhose(role: string | undefined): Whose {
  return role === "admin" || role === "manager" || role === "viewer" ? "everyone" : "mine"
}

const key = (screen: WhoseScreen) => `ondra.whose.${screen}`

export function useWhose(screen: WhoseScreen): [Whose, (w: Whose) => void] {
  const { me } = useAuth()
  const [chosen, setChosen] = useState<Whose | null>(null)
  useEffect(() => {
    try {
      const v = localStorage.getItem(key(screen))
      if (v === "mine" || v === "everyone") setChosen(v)
    } catch {
      // storage blocked: the role's default stands
    }
  }, [screen])
  const set = useCallback((w: Whose) => {
    setChosen(w)
    try {
      localStorage.setItem(key(screen), w)
    } catch {
      // not remembered, still applied
    }
  }, [screen])
  return [chosen ?? defaultWhose(me?.role), set]
}

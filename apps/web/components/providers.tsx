"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import { useRouter } from "next/navigation"
import { createContext, useCallback, useContext, useEffect, useState } from "react"

import { api, CLERK, logout as apiLogout, refresh, type Me } from "@/lib/api"
import { setDealerZone } from "@/lib/time"

import type { ClerkState } from "./clerk-bridge"

// Loaded only when Clerk is the sign-in provider, so local development never loads Clerk.
const ClerkSync = CLERK ? dynamic(() => import("./clerk-bridge").then((m) => m.ClerkSync), { ssr: false }) : null

type AuthState = {
  // "no-team": signed in with Clerk but not a member of any dealership.
  status: "loading" | "signed-in" | "signed-out" | "no-team"
  me: Me | null
  signOut: () => Promise<void>
  reload: () => Promise<void>
}
const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth outside Providers")
  return ctx
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }))
  const [status, setStatus] = useState<AuthState["status"]>("loading")
  const [me, setMe] = useState<Me | null>(null)
  const router = useRouter()

  const reload = useCallback(async () => {
    try {
      const m = await api<Me>("/me")
      setDealerZone(m.timezone) // before any screen renders a time
      setMe(m)
      setStatus("signed-in")
    } catch {
      setMe(null)
      setStatus("signed-out")
    }
  }, [])

  useEffect(() => {
    // Local sign-in: restore a session from the refresh cookie on first load. (Clerk reports through ClerkSync.)
    if (!CLERK) refresh().then((ok) => (ok ? reload() : setStatus("signed-out")))
  }, [reload])

  const onClerk = useCallback((c: ClerkState) => {
    if (c.status === "ready") reload()
    else setStatus(c.status === "loading" ? "loading" : c.status)
    if (c.status !== "ready") setMe(null)
  }, [reload])

  const signOut = useCallback(async () => {
    if (CLERK) {
      queryClient.clear()
      const { clerkSignOut } = await import("./clerk-bridge")
      await clerkSignOut()
      return
    }
    await apiLogout()
    queryClient.clear()
    setMe(null)
    setStatus("signed-out")
    router.replace("/login")
  }, [queryClient, router])

  return (
    <QueryClientProvider client={queryClient}>
      {ClerkSync && <ClerkSync onChange={onClerk} />}
      <AuthContext.Provider value={{ status, me, signOut, reload }}>{children}</AuthContext.Provider>
    </QueryClientProvider>
  )
}

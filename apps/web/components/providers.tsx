"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { createContext, useCallback, useContext, useEffect, useState } from "react"

import { api, logout as apiLogout, refresh, type Me } from "@/lib/api"

type AuthState = { status: "loading" | "signed-in" | "signed-out"; me: Me | null; signOut: () => Promise<void>; reload: () => Promise<void> }
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
      setMe(await api<Me>("/me"))
      setStatus("signed-in")
    } catch {
      setMe(null)
      setStatus("signed-out")
    }
  }, [])

  useEffect(() => {
    // Restore a session from the refresh cookie on first load.
    refresh().then((ok) => (ok ? reload() : setStatus("signed-out")))
  }, [reload])

  const signOut = useCallback(async () => {
    await apiLogout()
    queryClient.clear()
    setMe(null)
    setStatus("signed-out")
    router.replace("/login")
  }, [queryClient, router])

  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={{ status, me, signOut, reload }}>{children}</AuthContext.Provider>
    </QueryClientProvider>
  )
}

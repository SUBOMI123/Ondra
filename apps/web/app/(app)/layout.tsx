"use client"

import { useRouter } from "next/navigation"
import { useEffect } from "react"

import { AppSidebar } from "@/components/dashboard/app-sidebar"
import { useAuth } from "@/components/providers"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Skeleton } from "@/components/ui/skeleton"
import { MfaRequired } from "@/components/mfa-required"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { status, me } = useAuth()
  const router = useRouter()
  useEffect(() => {
    if (status === "signed-out" || status === "no-team") router.replace("/login")
  }, [status, router])

  if (status !== "signed-in") {
    return (
      <div className="flex min-h-svh items-center justify-center" aria-busy="true" aria-label="Loading">
        <Skeleton className="h-8 w-40" />
      </div>
    )
  }
  // Clerk: an owner or admin who signed in without two-step sign-in sets it up before anything else.
  if (me?.mfa_required) return <MfaRequired />
  return (
    <SidebarProvider
      style={{ "--sidebar-width": "calc(var(--spacing) * 64)", "--header-height": "calc(var(--spacing) * 12)" } as React.CSSProperties}
    >
      <AppSidebar variant="inset" />
      <SidebarInset className="min-w-0">{children}</SidebarInset>
    </SidebarProvider>
  )
}

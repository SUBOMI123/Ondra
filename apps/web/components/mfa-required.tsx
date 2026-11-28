"use client"

/**
 * Two-step sign-in, required. One job: an owner or admin turns on a second sign-in step, then gets back to work.
 * Shown when the API says this session lacks it (Clerk mode only). Clerk's own profile screen does the setup;
 * the session only counts the second step from their next sign-in, so they sign in again afterwards.
 */

import dynamic from "next/dynamic"

import { useAuth } from "@/components/providers"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import Wordmark from "@/components/wordmark"

const ClerkSecurity = dynamic(() => import("@/components/clerk-bridge").then((m) => m.ClerkSecurity), { ssr: false })

export function MfaRequired() {
  const { me, signOut } = useAuth()
  return (
    <div className="flex min-h-svh flex-col gap-6 p-6 md:p-10">
      <div className="flex items-center justify-between">
        <Wordmark className="h-6 w-auto" />
        <ThemeToggle />
      </div>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        <div className="max-w-xl">
          <h1 className="text-2xl font-semibold tracking-tight text-balance">Turn on two-step sign-in</h1>
          <p className="mt-2 text-sm text-pretty text-muted-foreground">
            As {me?.role === "owner" ? "an owner" : "an admin"} you can see every client, VIPs included, so Ondra asks
            for a second step when you sign in. Add an authenticator app under Security below, then sign in again.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => signOut()}>I&apos;ve added it. Sign in again</Button>
          </div>
        </div>
        <div className="flex justify-center md:justify-start">
          <ClerkSecurity />
        </div>
      </main>
    </div>
  )
}

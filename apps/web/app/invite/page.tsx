"use client"

/**
 * Invite. One job: a new teammate sets their password and gets in.
 * Reached from the one-time link an owner or admin created in Settings > Team.
 */

import { IconEye, IconEyeOff } from "@tabler/icons-react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import Wordmark from "@/components/wordmark"
import { acceptInvite } from "@/lib/api"

function InviteForm() {
  const router = useRouter()
  const token = useSearchParams().get("token")
  const [password, setPassword] = useState("")
  const [show, setShow] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!token) {
    return (
      <>
        <h1 className="text-2xl font-semibold tracking-tight">This link is incomplete</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Open the full invite link you were sent, or ask whoever invited you for a new one.
        </p>
      </>
    )
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password.length < 12) {
      setError("Use at least 12 characters.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await acceptInvite(token!, password)
      router.replace("/login?welcome=1")
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work. Try again.")
      setBusy(false)
    }
  }

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Set your password</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">You&apos;ve been invited to your dealership&apos;s Ondra. Choose a password to finish.</p>
      <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-5">
        <div className="grid gap-2">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input id="password" type={show ? "text" : "password"} autoComplete="new-password" required minLength={12}
              value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 pr-11" aria-describedby="pw-hint" />
            <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"}
              className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-md text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
              {show ? <IconEyeOff className="size-4" /> : <IconEye className="size-4" />}
            </button>
          </div>
          <p id="pw-hint" className="text-sm text-muted-foreground">At least 12 characters. A short sentence works well.</p>
        </div>
        {error && <p role="alert" className="rounded-md border px-3 py-2.5 text-sm">{error}</p>}
        <Button type="submit" size="lg" className="h-11 w-full" disabled={busy}>{busy ? "Saving…" : "Set password and continue"}</Button>
      </form>
      <p className="mt-6 text-sm text-muted-foreground">
        Already set up? <Link href="/login" className="underline underline-offset-4 hover:text-foreground">Sign in</Link>
      </p>
    </>
  )
}

export default function InvitePage() {
  return (
    <div className="flex min-h-svh flex-col gap-4 p-6 md:p-10">
      <div className="flex items-center justify-between">
        <Link href="/login" aria-label="Ondra"><Wordmark className="h-6 w-auto" /></Link>
        <ThemeToggle />
      </div>
      <main className="flex flex-1 items-center justify-center">
        <div className="w-full max-w-[22rem]">
          <Suspense fallback={null}><InviteForm /></Suspense>
        </div>
      </main>
    </div>
  )
}

"use client"

import { IconCalendarCheck, IconCrownFilled, IconEye, IconEyeOff, IconMoonStars } from "@tabler/icons-react"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { OndraMark } from "@/components/ondra-mark"
import { useAuth } from "@/components/providers"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import Wordmark from "@/components/wordmark"
import { ApiError, login } from "@/lib/api"

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://useondra.com"

// Example figures for the side panel, labelled as such on screen.
const OVERNIGHT = [
  { icon: IconMoonStars, value: "41", text: "leads answered after hours", ai: true },
  { icon: IconCalendarCheck, value: "19", text: "test drives and service slots booked", ai: true },
  { icon: IconCrownFilled, value: "2", text: "VIP calls rang straight to you", vip: true },
]

export default function LoginPage() {
  const { status, reload } = useAuth()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [show, setShow] = useState(false)
  const [welcome, setWelcome] = useState(false)
  useEffect(() => {
    setWelcome(new URLSearchParams(window.location.search).has("welcome"))
  }, [])

  useEffect(() => {
    if (status === "signed-in") router.replace("/")
  }, [status, router])

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setBusy(true)
    setError(null)
    try {
      await login(String(fd.get("email")), String(fd.get("password")))
      await reload()
      router.replace("/")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach Ondra. Check your connection and try again.")
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-svh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      {/* Form side */}
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex items-center justify-between">
          <a href={SITE_URL} aria-label="Ondra home">
            <Wordmark className="h-6 w-auto" />
          </a>
          <ThemeToggle />
        </div>

        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-[22rem]">
            <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              {welcome ? "You're set up. Sign in with your email and the password you just chose." : "Use the email your dealership added you with."}
            </p>

            <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-5">
              <div className="grid gap-2">
                <Label htmlFor="email">Work email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  required
                  autoFocus
                  placeholder="you@dealership.com"
                  aria-invalid={error ? true : undefined}
                  className="h-11"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={show ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    aria-invalid={error ? true : undefined}
                    className="h-11 pr-11"
                  />
                  <button
                    type="button"
                    onClick={() => setShow((v) => !v)}
                    aria-label={show ? "Hide password" : "Show password"}
                    aria-pressed={show}
                    className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-md text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {show ? <IconEyeOff className="size-4" /> : <IconEye className="size-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive">
                  {error}
                </p>
              )}

              <Button type="submit" size="lg" className="h-11 w-full" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </form>

            <p className="mt-6 text-sm text-muted-foreground">
              Forgot your password? Ask your dealership&apos;s owner or admin to reset it.
            </p>
          </div>
        </div>

        <p className="text-center text-sm text-muted-foreground lg:text-left">
          New to Ondra?{" "}
          <a href={`${SITE_URL}/#demo`} className="font-medium text-foreground underline-offset-4 hover:underline">
            Book a demo
          </a>
        </p>
      </div>

      {/* The showroom floor, after hours */}
      <div className="dark relative hidden overflow-hidden bg-neutral-950 lg:block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/login-floor.jpg"
          alt="Ondra's agents at their desks on a dealership floor after closing"
          className="absolute inset-0 size-full object-cover object-center"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-black/30" aria-hidden="true" />

        <div className="absolute inset-x-0 bottom-0 p-10 text-white">
          <p className="max-w-md text-2xl leading-snug font-medium tracking-tight text-balance">
            Your floor stays staffed after you lock up.
          </p>
          <div className="mt-6 max-w-md rounded-xl border border-white/10 bg-black/55 p-5 backdrop-blur-md">
            <div className="flex items-baseline justify-between">
              <p className="text-sm font-medium">While you were away</p>
              <p className="text-xs text-white/55">Example dealership</p>
            </div>
            <ul className="mt-4 grid gap-3">
              {OVERNIGHT.map((row) => (
                <li key={row.text} className="flex items-center gap-3 text-sm">
                  <span
                    className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${
                      row.vip ? "bg-vip-subtle text-vip" : "bg-ai-subtle text-ai"
                    }`}
                  >
                    {row.ai ? <OndraMark className="size-4" /> : <row.icon className="size-4" aria-hidden="true" />}
                  </span>
                  <span className="text-lg font-semibold tabular-nums">{row.value}</span>
                  <span className="text-white/75">{row.text}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

"use client"

/**
 * Clerk, when NEXT_PUBLIC_AUTH_PROVIDER=clerk. Clerk proves who someone is; Ondra's API decides what they may do.
 * This bridge hands Clerk's session tokens to the API client, picks the person's dealership (a Clerk
 * Organization; most people belong to one), and reports the state to Providers. Rendered only in Clerk mode.
 */

import { SignIn, SignUp, useAuth as useClerkAuth, useClerk, useOrganizationList, UserProfile } from "@clerk/nextjs"
import { shadcn } from "@clerk/ui/themes"
import { useEffect, useRef } from "react"

import { setTokenSource } from "@/lib/api"

export type ClerkState = { status: "loading" | "signed-out" | "no-team" | "ready"; orgId: string | null }

let signOutFn: (() => Promise<void>) | null = null
export function clerkSignOut(): Promise<void> {
  return signOutFn ? signOutFn() : Promise.resolve()
}

export function ClerkSync({ onChange }: { onChange: (s: ClerkState) => void }) {
  const { isLoaded, isSignedIn, orgId, getToken } = useClerkAuth()
  const clerk = useClerk()
  const { isLoaded: listLoaded, setActive, userMemberships } = useOrganizationList({ userMemberships: true })
  const tokenRef = useRef(getToken)
  useEffect(() => {
    tokenRef.current = getToken
  }, [getToken])
  useEffect(() => {
    signOutFn = () => clerk.signOut({ redirectUrl: "/login" })
  }, [clerk])

  useEffect(() => {
    if (!isLoaded) {
      onChange({ status: "loading", orgId: null })
      return
    }
    if (!isSignedIn) {
      setTokenSource(null)
      onChange({ status: "signed-out", orgId: null })
      return
    }
    setTokenSource(() => tokenRef.current())
    if (orgId) {
      onChange({ status: "ready", orgId })
      return
    }
    // Signed in with no dealership active: choose their first one, or say they're not on a team.
    if (!listLoaded) return
    const first = userMemberships.data?.[0]?.organization.id
    if (first) {
      setActive?.({ organization: first })
    } else {
      onChange({ status: "no-team", orgId: null })
    }
  }, [isLoaded, isSignedIn, orgId, listLoaded, userMemberships.data, setActive, onChange])
  return null
}

/** Clerk's components in Ondra's look: the shadcn theme reads our tokens (see globals.css). */
export const clerkAppearance = {
  theme: shadcn,
  elements: {
    // Fit the screen: Clerk's card has a fixed width that overflows a phone.
    rootBox: "w-full",
    cardBox: "w-full max-w-full",
    // Ondra is invite-only: no "Don't have an account? Sign up" (Clerk's Invite-only mode also blocks it).
    footerAction: { display: "none" },
  },
}

export function ClerkSignIn() {
  return <SignIn routing="hash" appearance={clerkAppearance} />
}

/** Accepting an invitation: Clerk reads the invitation from the link and creates the account. */
export function ClerkSignUp() {
  return <SignUp routing="hash" appearance={clerkAppearance} />
}

export function ClerkSecurity() {
  return <UserProfile routing="hash" appearance={clerkAppearance} />
}

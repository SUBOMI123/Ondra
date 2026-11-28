/**
 * Next.js proxy (formerly middleware). With Clerk as the sign-in provider it runs Clerk's middleware, which keeps
 * Clerk's session cookies current; access to data is enforced by Ondra's API on every request, not here.
 * With local sign-in it does nothing.
 */

import { clerkMiddleware } from "@clerk/nextjs/server"
import { NextResponse } from "next/server"

export default process.env.NEXT_PUBLIC_AUTH_PROVIDER === "clerk" ? clerkMiddleware() : () => NextResponse.next()

export const config = {
  matcher: [
    // Skip Next.js internals and static files, as in Clerk's Next.js guide.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
  ],
}

import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "./globals.css";

import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";

import { ClerkProvider } from "@clerk/nextjs"

import { Providers } from "@/components/providers"
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

export const metadata: Metadata = { title: "Ondra Workspace", icons: { icon: "/favicon.svg" } };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <MaybeClerk>
        {/* Light, dark, or follow the device (default). The choice is kept per browser for now; per user once auth exists. */}
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <TooltipProvider delayDuration={200}>
            <Providers>{children}</Providers>
            <Toaster />
          </TooltipProvider>
        </ThemeProvider>
        </MaybeClerk>
      </body>
    </html>
  );
}

// Clerk wraps the app only when it's the sign-in provider (inside <body>, as Clerk's Next.js guide requires).
function MaybeClerk({ children }: { children: React.ReactNode }) {
  if (process.env.NEXT_PUBLIC_AUTH_PROVIDER !== "clerk") return <>{children}</>
  return <ClerkProvider signInUrl="/login" signUpUrl="/invite" afterSignOutUrl="/login">{children}</ClerkProvider>
}

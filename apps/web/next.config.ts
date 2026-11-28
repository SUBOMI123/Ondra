import type { NextConfig } from "next";

// Security headers (security audit, 2026-11-28). The dashboard can't be framed (a hostile page could otherwise trick
// a signed-in manager into clicking), scripts and connections are limited to Ondra's own origins, and browsers are
// told to stay on https. Scripts allow 'unsafe-inline' because the App Router inlines its bootstrap scripts; a nonce
// per request would remove that, at the cost of rendering every page dynamically. Everything a person types is
// rendered as React text, which is the main defence; this limits the damage if that ever slips.
const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const clerk = process.env.NEXT_PUBLIC_AUTH_PROVIDER === "clerk";
const dev = process.env.NODE_ENV !== "production";
// TODO(verify): Clerk's CSP guide (clerk.com/docs/security/clerk-csp) lists its Frontend API host, img.clerk.com and
// Cloudflare's bot check; with a custom Clerk domain, add it here.
const clerkHosts = clerk ? ["https://*.clerk.accounts.dev", "https://*.clerk.com", "https://challenges.cloudflare.com"] : [];

const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""} ${clerkHosts.join(" ")}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src 'self' ${api} ${clerkHosts.join(" ")}${dev ? " ws:" : ""}`,
  `frame-src ${clerk ? "https://challenges.cloudflare.com" : "'none'"}`,
  "worker-src 'self' blob:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

// PREVIEW=1 builds with relative asset paths so the export can be hosted from any folder (the shared preview).
const nextConfig: NextConfig = {
  // Static export only for the shared preview; the real app runs as a Next.js server.
  ...(process.env.PREVIEW === "1" ? { output: "export" as const } : {}),
  images: { unoptimized: true },
  ...(process.env.PREVIEW === "1" ? { assetPrefix: "./app" } : {}),
  ...(process.env.PREVIEW === "1" ? {} : { headers: async () => [{ source: "/:path*", headers: securityHeaders }] }),
  poweredByHeader: false,
};

export default nextConfig;

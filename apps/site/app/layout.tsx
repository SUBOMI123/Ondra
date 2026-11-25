import type { Metadata, Viewport } from "next";
import { SITE_URL } from "@/lib/config";
import "@fontsource-variable/funnel-display";
import "@fontsource-variable/funnel-sans";
import "@fontsource-variable/jetbrains-mono";
import "./globals.css";

const title = "Ondra: AI agents that staff your dealership";
const description =
  "Ondra answers every call, WhatsApp, text and email your dealership gets, qualifies the buyer, books the visit and hands the right conversations to the right person. VIPs always reach you directly.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title,
  description,
  openGraph: { title, description, type: "website", siteName: "Ondra" },
  twitter: { card: "summary_large_image", title, description },
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#06080B",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
      </head>
      <body className="font-sans">{children}</body>
    </html>
  );
}

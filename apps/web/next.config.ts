import type { NextConfig } from "next";

// PREVIEW=1 builds with relative asset paths so the export can be hosted from any folder (the shared preview).
const nextConfig: NextConfig = {
  // Static export only for the shared preview; the real app runs as a Next.js server.
  ...(process.env.PREVIEW === "1" ? { output: "export" as const } : {}),
  images: { unoptimized: true },
  ...(process.env.PREVIEW === "1" ? { assetPrefix: "./app" } : {}),
};

export default nextConfig;

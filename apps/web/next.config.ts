import type { NextConfig } from "next";

// UI-only for now (mock data, no API). Static export keeps previews simple; Step 1 adds the API and auth.
// PREVIEW=1 builds with relative asset paths so the export can be hosted from any folder (the shared preview).
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  ...(process.env.PREVIEW === "1" ? { assetPrefix: "./app" } : {}),
};

export default nextConfig;

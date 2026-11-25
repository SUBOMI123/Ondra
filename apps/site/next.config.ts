import type { NextConfig } from "next";

// Static export: the marketing site is plain HTML/CSS/JS and can be hosted anywhere
// (Vercel, Netlify, Cloudflare Pages, S3). No server is needed.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;

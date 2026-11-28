"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"

export type Branding = { name: string; logo: string | null; logo_dark: string | null }

/** The dealership's name and logo (Settings > Business and hours). Rarely changes, so it's kept for a while. */
export function useBranding(enabled = true) {
  return useQuery({ queryKey: ["branding"], queryFn: () => api<Branding>("/settings/branding"), enabled, staleTime: 10 * 60_000 })
}

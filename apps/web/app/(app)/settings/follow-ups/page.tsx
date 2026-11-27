"use client"

import { FollowUpsSection } from "@/components/settings/follow-ups-section"
import { SettingsShell } from "@/components/settings/shell"

export default function FollowUpsPage() {
  return (
    <SettingsShell title="Follow-ups" description="Checking back with customers who went quiet: when, what's said, and whether someone approves it first.">
      <FollowUpsSection />
    </SettingsShell>
  )
}

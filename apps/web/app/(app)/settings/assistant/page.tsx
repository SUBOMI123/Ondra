"use client"

import { OwnerAssistantSection } from "@/components/settings/owner-assistant-section"
import { SettingsShell } from "@/components/settings/shell"

export default function AssistantPage() {
  return (
    <SettingsShell title="Your WhatsApp assistant" description="Yours alone: a morning briefing, an alert when a VIP is waiting, and a number to send voice notes and questions to.">
      <OwnerAssistantSection />
    </SettingsShell>
  )
}

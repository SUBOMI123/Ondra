"use client"

import { ChannelsSection } from "@/components/settings/channels-section"
import { SettingsShell, useSettings, VIEW_ONLY, WithSettings } from "@/components/settings/shell"

export default function ChannelsPage() {
  const s = useSettings()
  return (
    <SettingsShell title="Channels" description="Your existing number, WhatsApp and email. Customers keep using them; messages to them reach Ondra while they're on." readOnly={s.data && !s.data.can_edit && VIEW_ONLY}>
      <WithSettings>{(d) => <ChannelsSection data={d} canEdit={d.can_edit} />}</WithSettings>
    </SettingsShell>
  )
}

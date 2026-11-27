"use client"

import { RepliesSection } from "@/components/settings/replies-section"
import { SettingsShell, useSettings, VIEW_ONLY, WithSettings } from "@/components/settings/shell"

export default function RepliesPage() {
  const s = useSettings()
  return (
    <SettingsShell title="How Ondra replies" description="The rules Ondra checks before every message. It never promises what you haven't allowed." readOnly={s.data && !s.data.can_edit && VIEW_ONLY}>
      <WithSettings>{(d) => <RepliesSection data={d} canEdit={d.can_edit} />}</WithSettings>
    </SettingsShell>
  )
}

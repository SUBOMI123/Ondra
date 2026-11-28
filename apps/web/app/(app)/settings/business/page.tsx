"use client"

import { BusinessSection } from "@/components/settings/business-section"
import { LogoSection } from "@/components/settings/logo-section"
import { SettingsShell, useSettings, VIEW_ONLY, WithSettings } from "@/components/settings/shell"

export default function BusinessPage() {
  const s = useSettings()
  return (
    <SettingsShell title="Business and hours" description="Ondra answers outside these hours, and tells customers when you'll be back." readOnly={s.data && !s.data.can_edit && VIEW_ONLY}>
      <WithSettings>{(d) => <BusinessSection data={d} canEdit={d.can_edit} />}</WithSettings>
      {s.data && <LogoSection canEdit={s.data.can_edit} />}
    </SettingsShell>
  )
}

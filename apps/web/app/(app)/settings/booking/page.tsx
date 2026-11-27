"use client"

import { BookingSection } from "@/components/settings/booking-section"
import { SettingsShell, useSettings, VIEW_ONLY, WithSettings } from "@/components/settings/shell"

export default function BookingPage() {
  const s = useSettings()
  return (
    <SettingsShell title="Booking" description="What customers can book with Ondra, how long it takes, and who or what it needs. Ondra only offers times when the right person and bay are free." readOnly={s.data && !s.data.can_edit && VIEW_ONLY}>
      <WithSettings>{(d) => <BookingSection canEdit={d.can_edit} />}</WithSettings>
    </SettingsShell>
  )
}

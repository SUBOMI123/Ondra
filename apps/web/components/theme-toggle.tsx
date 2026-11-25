"use client"

import { IconDeviceDesktop, IconMoon, IconSun } from "@tabler/icons-react"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

/** Light, dark or follow the device. Rendered after mount so the server and client agree. */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  return (
    <ToggleGroup
      type="single"
      size="sm"
      variant="outline"
      value={mounted ? theme : undefined}
      onValueChange={(v) => v && setTheme(v)}
      aria-label="Theme"
    >
      <ToggleGroupItem value="light" aria-label="Light theme">
        <IconSun />
      </ToggleGroupItem>
      <ToggleGroupItem value="dark" aria-label="Dark theme">
        <IconMoon />
      </ToggleGroupItem>
      <ToggleGroupItem value="system" aria-label="Match device">
        <IconDeviceDesktop />
      </ToggleGroupItem>
    </ToggleGroup>
  )
}

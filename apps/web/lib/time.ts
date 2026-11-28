/**
 * Every time in the dashboard is the dealership's time, wherever the person reading it is. An owner checking in
 * from Lagos sees that Aisha wrote at 2:10 am Dallas time, not 8:10 am, because that's when it happened for the
 * business: before opening, after hours, during a shift. The header says which zone when it isn't the reader's own.
 * The zone comes from /me and is set once, before any screen renders.
 */

let ZONE: string | undefined

export function setDealerZone(tz: string | undefined) {
  ZONE = tz
}

export function dealerZone() {
  return ZONE
}

/** The reader's zone is not the dealership's: say so, as "Chicago time". Null when they match. */
export function zoneNote() {
  if (!ZONE) return null
  const mine = Intl.DateTimeFormat().resolvedOptions().timeZone
  if (mine === ZONE) return null
  const now = new Date()
  const offset = (tz: string) => new Date(now.toLocaleString("en-US", { timeZone: tz })).getTime()
  if (offset(mine) === offset(ZONE)) return null // same clock, different name
  return `${ZONE.split("/").pop()?.replace(/_/g, " ")} time`
}

const d = (x: string | Date) => (typeof x === "string" ? new Date(x) : x)

/** Any Intl date formatting, in the dealership's zone. */
export function fmt(x: string | Date, opts: Intl.DateTimeFormatOptions) {
  return d(x).toLocaleString("en-US", { ...opts, timeZone: ZONE })
}

/** "2:10 am" */
export function clock(x: string | Date) {
  return fmt(x, { hour: "numeric", minute: "2-digit" }).toLowerCase()
}

/** "2026-11-27", the dealership's calendar day. */
export function dayKey(x: string | Date) {
  return d(x).toLocaleDateString("en-CA", { timeZone: ZONE })
}

/** Whole days from `x` to today, by the dealership's calendar: 0 today, 1 yesterday, -1 tomorrow. */
export function daysAgo(x: string | Date) {
  return Math.round((Date.parse(dayKey(new Date())) - Date.parse(dayKey(x))) / 86_400_000)
}

export const isToday = (x: string | Date) => daysAgo(x) === 0

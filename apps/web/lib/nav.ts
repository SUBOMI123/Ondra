/** Is `url` the section the user is on? "/" only matches exactly; others match their sub-pages too
 * (/clients/profile is still Clients). */
export function isActivePath(pathname: string, url: string): boolean {
  if (url === "/") return pathname === "/"
  return pathname === url || pathname.startsWith(url + "/")
}

/** Classes for the active sidebar item: a visible fill, full-strength text, medium weight. */
export const ACTIVE_ITEM =
  "data-[active=true]:bg-sidebar-active data-[active=true]:font-medium data-[active=true]:text-sidebar-accent-foreground data-[active=true]:hover:bg-sidebar-active"

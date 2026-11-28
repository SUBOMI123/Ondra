// Automated part of the ondra-ui review (.claude/skills/ondra-ui/references/review.md).
// Run against a running dashboard and API:  npm run review:ui   (BASE_URL defaults to http://localhost:3001)
// Checks every page at 390, 768, 1024 and 1440 wide, in light and dark:
//   no horizontal scroll, exactly one h1, no AI-blue inside VIP surfaces, no icon buttons without a label,
// and greps the source for hex colours, middle-dot strings and the sparkles icon. Exits non-zero on failure.
// It also proves nothing is dead: no link to "#", every in-app link on every page opens a real page, and every
// control in the sidebar and header (each nav link, the logo, Search, ⌘K, the header search, New message) does
// what it says.
const { execSync } = require("node:child_process")
// Playwright: a dev dependency in CI; this cloud machine provides it globally.
const { chromium } = require("playwright")

const BASE = process.env.BASE_URL ?? "http://localhost:3001"
// Add every new page here.
const PAGES = ["/", "/inbox", "/calls", "/calendar", "/clients", "/deals", "/tasks", "/inventory", "/settings", "/settings/business", "/settings/channels", "/settings/integrations", "/settings/team", "/settings/routing", "/settings/replies", "/settings/knowledge", "/settings/follow-ups", "/settings/booking", "/settings/assistant", "/help", "/invite?token=example", "/b?t=example"]
const WIDTHS = [390, 768, 1024, 1440]
// The screens that list someone's work have one Mine / Everyone switch, in the header (docs/PLAN.md item 6).
const WHOSE = ["/inbox", "/calls", "/calendar", "/tasks", "/deals"]
const failures = []

const grep = (pattern, extra = "") => {
  try {
    return execSync(`grep -rnE ${JSON.stringify(pattern)} app components --include=*.tsx ${extra}`, { encoding: "utf8" }).trim()
  } catch {
    return ""
  }
}
const hex = grep("#[0-9a-fA-F]{3,8}\\b").split("\n").filter((l) => l && !/components\/ui\/|wordmark\.tsx|ondra-mark\.tsx/.test(l))
if (hex.length) failures.push(`Hex colours in components (use tokens):\n  ${hex.join("\n  ")}`)
const dots = grep("·")
if (dots) failures.push(`Middle-dot metadata strings:\n  ${dots}`)
const effects = grep("useEffect\\(\\(\\) => [^{]")
if (effects) failures.push(`Effects must have a block body (a returned Promise, e.g. from scrollIntoView, crashes React):\n  ${effects}`)
const deadLinks = grep('href="#"|url: "#"')
if (deadLinks) failures.push(`Links that go nowhere (href "#"): give them a page or an action:\n  ${deadLinks}`)
const sparkles = grep("IconSparkles")
if (sparkles) failures.push(`Sparkles icon (use OndraMark for Ondra):\n  ${sparkles}`)

async function main() {
const browser = await chromium.launch()
for (const scheme of ["light", "dark"]) {
  const ctx = await browser.newContext({ colorScheme: scheme })
  const page = await ctx.newPage()
  await page.goto(`${BASE}/login`)
  await page.fill("#email", process.env.REVIEW_EMAIL ?? "owner@prestigemotors.example")
  await page.fill("#password", process.env.REVIEW_PASSWORD ?? "ondra-dev-password")
  await page.click("button[type=submit]")
  await page.waitForURL(`${BASE}/`)
  // Plus one real client profile and one VIP profile, found through the Clients list.
  // The first load after sign-in can wait on a token refresh; give it time rather than fail the whole review.
  await page.goto(`${BASE}/clients`, { waitUntil: "networkidle" })
  // After a code change the dev server recompiles on first visit and can miss the first data load: reload once.
  await page.waitForSelector("a[href^='/clients/profile']", { timeout: 30000 }).catch(async () => {
    await page.reload({ waitUntil: "networkidle" })
    await page.waitForSelector("a[href^='/clients/profile']", { timeout: 30000 })
  })
  const profiles = await page.$$eval("a[href^='/clients/profile']", (as) => [as[0].getAttribute("href"), as.find((a) => a.closest("[data-vip]"))?.getAttribute("href")].filter(Boolean))
  if (scheme === "light") await checkShell(page)
  const linked = new Set()
  for (const path of [...PAGES, ...profiles]) {
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 })
      await page.goto(BASE + path)
      if (WHOSE.includes(path)) await page.waitForSelector("header [role=tablist][aria-label^='Whose']", { timeout: 10000 }).catch(() => {})
      await page.waitForTimeout(700)
      const r = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth - innerWidth,
        h1: document.querySelectorAll("h1").length,
        vipAi: document.querySelectorAll("[data-vip] [data-slot^=ai-], [data-vip] .text-ai").length,
        whose: document.querySelectorAll("header [role=tablist][aria-label^='Whose']").length,
        where: `${location.pathname} h1="${document.querySelector("h1")?.textContent ?? ""}"`,
        unlabeled: [...document.querySelectorAll("button, a")].filter((b) => !b.textContent.trim() && !b.getAttribute("aria-label") && !b.getAttribute("aria-labelledby") && !b.title && !(b.labels && b.labels.length)).length,
      }))
      if (width === 1440) {
        for (const href of await page.$$eval("a[href^='/']", (as) => as.map((a) => a.getAttribute("href")))) linked.add(href.split("#")[0])
      }
      const at = `${path} at ${width}px (${scheme})`
      const landed = new URL(page.url()).pathname
      if (landed !== path.split("?")[0]) failures.push(`${at}: landed on ${landed} instead (a sign-in refresh race sends people to Today)`)
      if (r.overflow > 0) failures.push(`${at}: scrolls sideways by ${r.overflow}px`)
      if (r.h1 !== 1) failures.push(`${at}: ${r.h1} h1 elements (want 1)`)
      if (r.vipAi) failures.push(`${at}: ${r.vipAi} AI-blue elements inside a VIP surface (product rule)`)
      if (r.whose !== (WHOSE.includes(path) ? 1 : 0)) failures.push(`${at}: ${r.whose} Mine / Everyone switches in the header (want ${WHOSE.includes(path) ? 1 : 0}; page showed ${r.where})`)
      if (r.unlabeled) failures.push(`${at}: ${r.unlabeled} icon buttons or links without a label`)
    }
  }
  // Every in-app link found on any page opens a real page (not Next's 404).
  if (scheme === "light") {
    for (const href of linked) {
      const res = await page.goto(BASE + href)
      if (!res || res.status() >= 400) failures.push(`Link to ${href} is broken (${res ? res.status() : "no response"})`)
    }
  }
  await ctx.close()
}
await browser.close()

if (failures.length) {
  console.error(`UI review: ${failures.length} problem(s)\n- ${failures.join("\n- ")}`)
  process.exit(1)
}
console.log(`UI review passed: ${PAGES.length + 2} pages x ${WIDTHS.length} widths x 2 themes, every in-app link, every shell control, plus source checks.`)
}

// Every control in the shell does something: each nav link and the logo go to their page; Search, the header search
// box and ⌘K open search (and a search finds and opens a client); New message opens the message panel.
async function checkShell(page) {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BASE}/inbox`)
  const sidebar = page.locator("[data-sidebar=sidebar]").first()
  await sidebar.waitFor()
  const links = await sidebar.locator("a[href]").evaluateAll((as) => as.map((a) => ({ href: a.getAttribute("href"), name: a.getAttribute("aria-label") || a.textContent.trim() })))
  for (const { href, name } of links) {
    await page.goto(`${BASE}/settings`)
    await sidebar.locator(`a[href="${href}"]`).first().click()
    try {
      await page.waitForURL((u) => u.pathname + u.search === href || u.pathname === href.split("?")[0], { timeout: 15000 })
    } catch {
      failures.push(`Sidebar "${name}" didn't open ${href} (stayed on ${page.url()})`)
    }
  }
  // Wait until the page is interactive (the sidebar has rendered its items) before pressing keys or clicking.
  const ready = async () => {
    await page.goto(`${BASE}/settings`)
    await sidebar.getByRole("button", { name: "New message" }).waitFor()
    await page.waitForTimeout(500)
  }
  const opens = async (label, act, expect) => {
    await ready()
    await act()
    try {
      await page.getByRole("dialog").filter({ has: expect(page) }).waitFor({ timeout: 5000 })
    } catch {
      failures.push(`${label} didn't open anything`)
    }
    await page.keyboard.press("Escape")
  }
  const searchBox = (p) => p.getByPlaceholder(/Name, phone, stock number/)
  await opens("Sidebar Search", () => sidebar.getByRole("button", { name: "Search" }).click(), searchBox)
  await opens("Header search bar", () => page.locator("header").getByRole("button", { name: /Search clients, cars, messages/ }).click(), searchBox)
  await opens("⌘K", () => page.keyboard.press("Control+k"), searchBox)
  await opens("New message", () => sidebar.getByRole("button", { name: "New message" }).click(), (p) => p.getByText("Write to a client on WhatsApp"))
  // A search finds a client and opens them.
  await ready()
  await page.keyboard.press("Control+k")
  await searchBox(page).fill("Grace")
  try {
    await page.getByRole("option", { name: /Grace/ }).first().click({ timeout: 10000 })
    await page.waitForURL(/\/clients\/profile\?id=/, { timeout: 15000 })
  } catch {
    failures.push("Searching \"Grace\" didn't find and open a client")
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})

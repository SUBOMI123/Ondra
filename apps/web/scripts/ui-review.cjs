// Automated part of the ondra-ui review (.claude/skills/ondra-ui/references/review.md).
// Run against a running dashboard and API:  npm run review:ui   (BASE_URL defaults to http://localhost:3001)
// Checks every page at 390, 768, 1024 and 1440 wide, in light and dark:
//   no horizontal scroll, exactly one h1, no AI-blue inside VIP surfaces, no icon buttons without a label,
// and greps the source for hex colours, middle-dot strings and the sparkles icon. Exits non-zero on failure.
const { execSync } = require("node:child_process")
// Playwright: a dev dependency in CI; this cloud machine provides it globally.
const { chromium } = require("playwright")

const BASE = process.env.BASE_URL ?? "http://localhost:3001"
// Add every new page here.
const PAGES = ["/", "/inbox", "/calls", "/calendar", "/clients", "/deals", "/tasks", "/inventory", "/settings", "/settings/team", "/settings/routing", "/settings/knowledge", "/settings/integrations", "/invite?token=example"]
const WIDTHS = [390, 768, 1024, 1440]
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
  await page.goto(`${BASE}/clients`)
  await page.waitForSelector("a[href^='/clients/profile']")
  const profiles = await page.$$eval("a[href^='/clients/profile']", (as) => [as[0].getAttribute("href"), as.find((a) => a.querySelector("[aria-label=VIP]"))?.getAttribute("href")].filter(Boolean))
  for (const path of [...PAGES, ...profiles]) {
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 })
      await page.goto(BASE + path)
      await page.waitForTimeout(700)
      const r = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth - innerWidth,
        h1: document.querySelectorAll("h1").length,
        vipAi: document.querySelectorAll("[data-vip] [data-slot^=ai-], [data-vip] .text-ai").length,
        unlabeled: [...document.querySelectorAll("button, a")].filter((b) => !b.textContent.trim() && !b.getAttribute("aria-label") && !b.getAttribute("aria-labelledby") && !b.title && !(b.labels && b.labels.length)).length,
      }))
      const at = `${path} at ${width}px (${scheme})`
      if (r.overflow > 0) failures.push(`${at}: scrolls sideways by ${r.overflow}px`)
      if (r.h1 !== 1) failures.push(`${at}: ${r.h1} h1 elements (want 1)`)
      if (r.vipAi) failures.push(`${at}: ${r.vipAi} AI-blue elements inside a VIP surface (product rule)`)
      if (r.unlabeled) failures.push(`${at}: ${r.unlabeled} icon buttons or links without a label`)
    }
  }
  await ctx.close()
}
await browser.close()

if (failures.length) {
  console.error(`UI review: ${failures.length} problem(s)\n- ${failures.join("\n- ")}`)
  process.exit(1)
}
console.log(`UI review passed: ${PAGES.length + 2} pages x ${WIDTHS.length} widths x 2 themes, plus source checks.`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})

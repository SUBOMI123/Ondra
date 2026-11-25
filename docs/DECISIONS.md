# Decisions

## 2026-11-25: Marketing site as its own static app (`apps/site`)

**Decision:** The landing page is a separate Next.js static export in `apps/site`, not part of `apps/web`.
**Why:** It can ship now, before the API or the dashboard exist. It hosts free on any static host, and a marketing deploy can't break the product.
**Alternatives:** A route in `apps/web` (couples marketing deploys to the app and needs the app scaffolded first). A plain HTML file (fastest, but the copy and components would be rewritten later anyway).

## 2026-11-25: The 3D walk-through is a section, not the entry gate

**Decision:** The page opens with a normal hero (headline, sample WhatsApp conversation, Book a demo). The walk-through comes straight after it, because it continues the hero's "fully staffed" line. It is 480vh long and lazy-loaded.
**Why:** The mockup put 900vh of scroll-driven 3D and 600KB of inline three.js in front of the value proposition and the call to action. Dealers mostly open links on their phones from WhatsApp, and they need to see what it is and how to book in the first screen. The walk-through is still the memorable part, so it stays.
**Alternatives:** Keep the mockup's full-screen intro (worse load time, CTA nine screens down, weak on mobile). Drop the 3D entirely (loses the concept that makes the page distinctive).

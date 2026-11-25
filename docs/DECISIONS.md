# Decisions

## 2026-11-25: Marketing site as its own static app (`apps/site`)

**Decision:** The landing page is a separate Next.js static export in `apps/site`, not part of `apps/web`.
**Why:** It can ship now, before the API or the dashboard exist. It hosts free on any static host, and a marketing deploy can't break the product.
**Alternatives:** A route in `apps/web` (couples marketing deploys to the app and needs the app scaffolded first). A plain HTML file (fastest, but the copy and components would be rewritten later anyway).

## 2026-11-25: The 3D walk-through is a section, not the entry gate

**Decision:** The page opens with a normal hero (headline, sample WhatsApp conversation, Book a demo). The walk-through comes straight after it, because it continues the hero's "fully staffed" line. It is 480vh long and lazy-loaded.
**Why:** The mockup put 900vh of scroll-driven 3D and 600KB of inline three.js in front of the value proposition and the call to action. Dealers mostly open links on their phones from WhatsApp, and they need to see what it is and how to book in the first screen. The walk-through is still the memorable part, so it stays.
**Alternatives:** Keep the mockup's full-screen intro (worse load time, CTA nine screens down, weak on mobile). Drop the 3D entirely (loses the concept that makes the page distinctive).

## 2026-11-25: `ondra-ui` skill is the basis for all UI work

**Decision:** UI rules live in a project skill at `.claude/skills/ondra-ui/` (SKILL.md plus references for tokens, marketing, dashboard, components, AI and VIP rendering, copy and review). `CLAUDE.md` points to it.
**Why:** One place that every Claude Code session loads for UI work, distilled from a review of anthropics/skills, impeccable, shadcn/ui, Radix, cmdk, sonner, vaul, Tailwind v4, Magic UI, Tremor, Recharts, Tabler, Storybook, daisyUI and Mantine.
**Alternatives:** A design doc in `docs/` (not loaded automatically), or adopting Impeccable as-is (generic, and depends on its own CLI).

## 2026-11-25: Component stack for apps/web

**Decision:** shadcn/ui on **Radix** (`init -b radix`, unified `radix-ui` package), Tabler icons, shadcn Chart on Recharts 3, sonner, cmdk, vaul (pinned, mobile only). No daisyUI, Mantine or Tremor components. Storybook later.
**Why:** cmdk and vaul sit on Radix Dialog; Tabler has the WhatsApp and Instagram marks lucide lacks; Tremor Raw is still on React 18 and Recharts 2. daisyUI and Mantine bring competing theme systems.
**Alternatives:** Base UI (shadcn's default since July 2026; reconsider if vaul, which is unmaintained, becomes a problem).

## 2026-11-25: Walk-through figures stay stylised

**Decision:** The 3D agents are faceless porcelain mannequins built in code, not realistic people.
**Why:** The page's closing line is "None of them are people", and realistic humans would contradict it. Licensed rigged characters cost 3-10MB each and stutter on phones. Blender can't run in this environment.
**Alternatives:** Licensed realistic characters in glTF (heavy, uncanny). A Blender-rendered image sequence scrubbed by scroll (best quality; needs a 3D artist and licensed assets).

## 2026-11-25: Hero image is AI-generated for now

**Decision:** `apps/site/public/hero-showroom.jpg` was generated with Figma's image generator (no badges, plates or people). It is a placeholder.
**Why:** Stock photo hosts are blocked from the build environment, and the page needed real atmosphere.
**Alternatives:** Replace with the pilot dealer's own showroom photographed at dusk, once we have written permission.

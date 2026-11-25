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

## 2026-11-25: The walk-through is a photographic scroll tour with robot agents (supersedes the three.js floor)

**Decision:** Replace the real-time three.js scene with five photoreal stills on a sticky stage (`apps/site/components/FloorTour.tsx`): entrance, reception and WhatsApp, bookings and service, handoffs and follow-ups, the owner's office. The agents are humanoid robots. Labels are pinned to coordinates in each photo.
**Why:** The goal is for it to feel real. Real-time 3D can't get there on a phone: photoreal cars and characters need licensed models of 20-50MB each and a GPU budget dealers' phones don't have, and procedural models look like toys. Stills give photographic quality at about 150KB per scene, and the page dropped three.js (about 700KB of JS). Robots read as AI agents at a glance and keep the closing line ("None of them are people") true.
**Alternatives:** Licensed glTF cars and robots in three.js (heavy, still not photographic). A Blender render sequence scrubbed frame by frame (smoothest camera moves, needs a 3D artist and licensed assets; worth it once there's budget). Mannequins (tried, rejected by the founder as not real enough).

## 2026-11-25: Hero image is AI-generated for now

**Decision:** `apps/site/public/hero-showroom.jpg` and the floor tour scenes in `apps/site/public/floor/` were generated with Figma's image generator (no badges, plates or people; art direction in the `ondra-ui` skill, `references/marketing.md`). They are placeholders.
**Why:** Stock photo hosts are blocked from the build environment, and the page needed real atmosphere.
**Alternatives:** Replace with the pilot dealer's own showroom photographed at dusk, once we have written permission.

## 2026-11-24: Showroom cars are four free Blend Swap models, two of them not licensed for commercial use

**Decision:** The 3D floor loads four Blend Swap models from the founder's Desktop (`build_scene.py --cars`, loader in `design/3d/floor/cars.py`): 1968 Mustang GT Fastback (CC0), Audi A8 2010 by 50Groszy (CC-BY-SA 3.0), BMW M4 F82 (CC-BY 3.0, marked Fan Art) and Lamborghini Urus 2019 (CC-BY-NC 3.0). Badges, logos, plates and lettering are removed; the grille shapes of the BMW, Audi and Urus remain. Paint is recoloured black, silver and bronze.
**Why:** The founder confirmed all four after being told which licences were a problem. This gives four recognisable cars now, without the $50-300 per model for licensed production assets.
**Risk (open):** Only the Mustang is clearly cleared for commercial use. The BMW's page says Fan Art may not be used commercially "under any circumstance", and the Urus is NonCommercial. The Audi's licence file allows commercial use with credit but the author's readme asks for none, and share-alike may reach our modified model. A marketing page is commercial use. The renders are local and unpublished; do not ship frames containing the BMW, Urus or Audi to `apps/site` until each has permission from its author or is replaced with a licensed model. Credit if shipped: Audi A8 by 50Groszy, BMW M4 and Lamborghini Urus by their Blend Swap authors (#81957, #92440), 1968 Mustang GT Fastback (#82339, no credit required).
**Alternatives:** Mustang only in three colours (clean licence, one car shape). Licensed models from CGTrader, TurboSquid or BlenderKit.

## 2026-11-25: Rebrand to "Night Shift": dark, Ondra blue, Funnel type

**Decision:** The brand moves from paper, ink and amber with Archivo Expanded to a dark-first palette (night `#06080B`, Ondra blue `#2F6CF6`, VIP red), set in Funnel Display, Funnel Sans and JetBrains Mono (free, OFL, self-hosted via fontsource). Ondra blue is both the brand and the colour of anything the AI did; in the dashboard, primary actions are neutral so blue keeps that meaning. The hero uses the first frame of the 3D walk instead of the generated photo.
**Why:** The founder found the old look AI-template-like (it sat close to the "warm cream editorial" cliché) and wanted it techy, futuristic, friendly and marketable. Dark reads as an AI product and matches the night render. The founder rejected mint and asked for blue, since Numa owns violet. Funnel's notched letterforms keep it out of the Inter-on-black look that Numa and most AI startups share.
**Alternatives:** Spruce and mint (light), Chrome and signal yellow, and Night Shift with mint. All three were shown on the direction board. Inter or Geist (rejected as the category default). Mona Sans (kept in reserve).

## 2026-11-25: Night-sky direction with Inter, frosted pills and Motion (supersedes Night Shift / Funnel)

**Decision:** Inter Variable (cv01, ss03) at light weights; a blue-black void with a twilight-navy sky over the 3D floor; frosted-white pill buttons; periwinkle for the AI, coral for VIPs. Motion (`motion`, formerly Framer Motion) for product UI that plays out on scroll (inbox thread), a CSS blur-in on the hero headline, and an animated channel-flow diagram. The `frontend-design` skill now sets design direction; `ondra-ui` keeps tokens and product rules.
**Why:** The founder found Funnel and the saturated blue still "very AI", pointed to Numa (Inter regular at large size, frosted pills, navy night sky) and Linear, and asked for Framer-quality motion. Measured Numa directly: Inter 400 at 56px, -0.04em tracking, white 80% pill buttons with dark text.
**Alternatives:** Build in Framer via its connector (not connected yet; code keeps the 3D walk and ownership). Funnel Display (rejected by the founder).

## 2026-11-25: Champagne palette and product stories in the middle of the page

**Decision:** The hero and grounds move from navy to a warm "champagne night": espresso grounds, a sodium-amber glow off the floor, champagne pill buttons. The AI stays a cool periwinkle. The WhatsApp, VIP, owner-briefing and guardrails sections became short product stories that play once on scroll (`components/stories.tsx`, `useStory`): a buyer in Lagos answered while Dallas sleeps, a VIP call ringing past the AI, the morning briefing approved by voice note, and a draft whose price and delivery promise are held back and rewritten.
**Why:** The founder found the navy hero and white pills too close to Numa. Flai owns oxblood and crimson. Warm champagne is unclaimed, matches the 3D render's amber light, and reads as luxury dealership. The static text blocks felt flat next to the animated inbox and diagram.
**Alternatives:** Petrol (teal night; its buttons went back to rejected mint), Graphite chrome (too close to Linear). Compared as rendered heroes.

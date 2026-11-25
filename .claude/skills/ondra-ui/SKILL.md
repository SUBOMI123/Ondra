---
name: ondra-ui
description: Ondra's design system and UI rules for anything visual in this repo. Use whenever you build, restyle, review or write copy for the marketing site (apps/site) or the dealer dashboard (apps/web - Today, Inbox, Calls, Calendar, Clients, Tasks, Settings), including new components, Tailwind classes or theme tokens, shadcn or Radix components, charts, icons, empty and error states, motion, the floor tour and its photography, emails that render HTML, and screenshots or critiques of a page. Covers the champagne-night palette (espresso grounds, sodium glow, champagne pill actions, periwinkle for the AI, red for VIPs), Inter Variable and JetBrains Mono, layout, motion, UX copy, and how AI-generated and VIP content must look. Use it even for a small tweak to a button or a label. Not for backend, API, database or agent-prompt work with no UI.
---

# Ondra UI

Design direction and craft come from the `frontend-design` skill; this skill holds Ondra's tokens and the product rules. Read both for UI work.

Ondra is staff for a car dealership: AI agents at every desk, people where a person is needed, and the owner's office that VIPs reach directly. The brand is a luxury showroom at night ("champagne night"): warm espresso grounds, a sodium-amber glow off the floor, quiet light-weight Inter type, champagne pill buttons, a soft periwinkle that marks anything the AI did, coral for VIPs only. Product UI that moves (the inbox, the channel diagram, the stories in `components/stories.tsx`) and the 3D floor carry the personality; the chrome stays quiet. Reference points the founder chose: Numa (numa.com) and Linear.

Visual authority, in order: the user's words, this skill, `design/README.md`, the prototypes in `design/mockups/` (`landing.html`, `app.html`). The prototypes predate the Night Shift rebrand (they use paper, ink and amber); keep their layouts and content, take colour and type from this skill.

## 1. Pick the mode from the surface, then read one file

| Surface | Mode | Read now |
|---|---|---|
| `apps/site`, any marketing page, email campaign, social image | **Persuade**: earn attention, one memorable move | `references/marketing.md` |
| `apps/web`, anything a dealer operates | **Operate**: the tool disappears into the task | `references/dashboard.md` |

A landing page for the product is still Persuade. A settings screen is still Operate even if it is pretty. Read only the file for your surface. Read `references/tokens.md` before writing any CSS or Tailwind classes, and `references/components.md` before adding or restyling a component.

## 2. Named rules (these are product rules, not taste)

<!-- rule:blue-is-the-ai -->
**Blue is the AI.** Periwinkle (`ai` `#B3C5FF` text, `ai-subtle` `#121B36` surface, `brand` `#8AA6FF` dots and rings) marks anything Ondra said, drafted, booked, summarised or suggested, always with a label naming it ("Sent by Ondra"). Blue is atmosphere and provenance, never a loud fill. Actions are champagne pills (`btn-primary`: `#EAD9B5` with near-black text) and ghost pills (`btn-quiet`). No saturated blue buttons anywhere.

<!-- rule:red-is-rare -->
**Red is rare.** VIP coral (`vip` `#FF8A80` on `vip-subtle` `#34161A`) is for VIP contacts and overdue items only. Errors use Ink with a clear message, destructive buttons use an outline and an explicit verb, bad deltas are muted grey with a down arrow.

<!-- rule:vip-has-no-ai -->
**VIPs never meet the AI.** A VIP surface shows no AI-blue draft, suggestion, summary or "let Ondra reply" affordance. Calls read "Rings you directly". This mirrors the product rule in `CLAUDE.md`, so a VIP component that renders anything AI-blue is a bug.

<!-- rule:not-the-ai-template -->
**Earn the category look.** Inter on a dark navy sky is the category's language (Numa, Linear); Ondra speaks it on purpose. What keeps it from being a template: the 3D floor, real product UI that moves, drawings that explain (the channel-flow diagram), precise type (light weights, tight tracking, `cv01`/`ss03`), and no decoration that isn't information: no glowing orbs, no gradient text, no sparkle confetti.

<!-- rule:no-fake-proof -->
**Label illustrative values honestly.** Sample conversations, KPI numbers and names on marketing pages are examples, never claims. No invented stats, logos or testimonials. See `docs/marketing/positioning.md` for the claims we cannot make yet.

## 3. Type

- **Inter Variable** for everything, with `font-feature-settings: "cv01", "ss03"` (set on `body`). Self-hosted via `@fontsource-variable/inter`.
- Display and section headings at weight **400** with tight tracking (-0.035 to -0.045em); never bold display type. Card titles 500. Body 400.
- **JetBrains Mono** (`font-mono`) for data only: timestamps in product mocks, VINs, stock numbers, call durations. Never decorative.
- Tabular numerals wherever digits line up. Headings `text-wrap: balance`, paragraphs `text-wrap: pretty`, prose 60-72ch.

## 4. Before you build

Write these down (in your head or a comment), then build:
1. The one job of the screen or section, in one sentence.
2. The one signature move (marketing: the 3D floor walk; dashboard: the Ondra-blue provenance trail). Spend boldness there and keep everything around it quiet.
3. Every state it needs: default, hover, focus-visible, active, disabled, loading (skeleton), empty, error, and AI-pending / AI-sent / VIP variants where they apply.
4. Real content: dealer vocabulary, plausible US prices and times, buyers in Lagos and Dallas. No lorem ipsum.

Build with tokens only. A hex literal in a component is a bug; add a token instead.

## 5. Never ship

<!-- rule:never-ship -->
- Tracked uppercase eyebrows or kickers above headings ("HOW IT WORKS" over "How it works")
- Metadata strung together with middle dots ("Lagos · WhatsApp · 2:14 am"); use layout, not punctuation
- Numbered markers (01, 02) on things that are not a real sequence
- Gradient text, coloured glow shadows, radial halos, glassmorphism as decoration
- Identical icon-heading-text card grids as page structure; nested cards
- A rounded card with a coloured bar down one side (fine only on square list rows)
- Purple, violet or cyan accents; any colour outside the tokens
- Monospace as a costume for "technical"; emoji standing in for icons
- Bounce or elastic easing; fade-and-slide-up on every section; anything that animates on its own in the walk-through
- Spinners inside content (use a skeleton of the final size); a modal where inline would do
- Buzzwords: streamline, empower, supercharge, seamless, cutting-edge, next-generation, world-class
- "Bot" for the product, robot icons in the UI, or human faces on the agents (they are not people)
- Saturated blue buttons; bold (600+) display headlines; purple or violet anywhere
- Fade-and-slide on every section. Motion is for the hero load, the 3D walk, and product UI playing out

## 6. Finish

Run `references/review.md` on a screenshot at 390, 768 and 1440 wide before calling UI work done. Answer each check with a selector or a computed value, not "looks fine". Accessibility checks live there on purpose: designing with them in front of you tends to produce timid work, so design first, then verify hard.

## Reference map

| File | Read when |
|---|---|
| `references/tokens.md` | Before any CSS, Tailwind class or colour decision |
| `references/marketing.md` | Working on `apps/site` or any marketing asset |
| `references/dashboard.md` | Working on `apps/web`, including charts, KPIs, icons, formatting |
| `references/components.md` | Adding or restyling a component (shadcn, Radix, cmdk, sonner, vaul, Magic UI) |
| `references/ai-and-vip.md` | Rendering anything the AI did, drafts, approvals, VIPs, opt-outs |
| `references/copy.md` | Writing any user-facing words |
| `references/review.md` | Before calling UI work done |
| `references/NOTICE.md` | Attribution for adapted material |

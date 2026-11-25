---
name: ondra-ui
description: Ondra's design system and UI rules for anything visual in this repo. Use whenever you build, restyle, review or write copy for the marketing site (apps/site) or the dealer dashboard (apps/web - Today, Inbox, Calls, Calendar, Clients, Tasks, Settings), including new components, Tailwind classes or theme tokens, shadcn or Radix components, charts, icons, empty and error states, motion, the floor tour and its photography, emails that render HTML, and screenshots or critiques of a page. Covers the Night Shift palette (night, Ondra blue, VIP red), Funnel Display, Funnel Sans and JetBrains Mono, layout, motion, UX copy, and how AI-generated and VIP content must look. Use it even for a small tweak to a button or a label. Not for backend, API, database or agent-prompt work with no UI.
---

# Ondra UI

Ondra is staff for a car dealership: AI agents at every desk, people where a person is needed, and the owner's office that VIPs reach directly. The brand is **Night Shift**: the dealership after dark, when Ondra does its best work. Near-black grounds, one electric-azure signal that is also the colour of the AI, red only for VIPs. Techy and precise, but friendly and plain-spoken. It is not a purple-glow AI startup, not Inter on black, and not a generic SaaS card kit.

Visual authority, in order: the user's words, this skill, `design/README.md`, the prototypes in `design/mockups/` (`landing.html`, `app.html`). The prototypes predate the Night Shift rebrand (they use paper, ink and amber); keep their layouts and content, take colour and type from this skill.

## 1. Pick the mode from the surface, then read one file

| Surface | Mode | Read now |
|---|---|---|
| `apps/site`, any marketing page, email campaign, social image | **Persuade**: earn attention, one memorable move | `references/marketing.md` |
| `apps/web`, anything a dealer operates | **Operate**: the tool disappears into the task | `references/dashboard.md` |

A landing page for the product is still Persuade. A settings screen is still Operate even if it is pretty. Read only the file for your surface. Read `references/tokens.md` before writing any CSS or Tailwind classes, and `references/components.md` before adding or restyling a component.

## 2. Named rules (these are product rules, not taste)

<!-- rule:blue-is-ondra -->
**Blue is Ondra.** Ondra blue (`brand` `#2F6CF6`, `brand-text` `#7FA9FF` as text) is both the brand and the colour of anything the AI said, drafted, booked, summarised or suggested, always with a label naming it ("Sent by Ondra"). The brand is the AI, so the two never disagree. Consequences:
- On the **marketing site**, primary CTAs are blue: there it is Ondra speaking.
- In the **dashboard**, primary actions are neutral (white fill with night text on dark, night fill on light), so blue keeps meaning "the AI did this". A person's actions never wear blue.
- Blue fills take white text (4.6:1). Blue as text on dark uses `brand-text` or `ai` (`#9DBCFF`), never the fill colour.

<!-- rule:red-is-rare -->
**Red is rare.** VIP red (`vip` `#FF7A7A` on `vip-subtle` `#3A1517` in the dark theme) is for VIP contacts and overdue items only. Errors use Ink with a clear message, destructive buttons use an outline and an explicit verb, bad deltas are muted grey with a down arrow.

<!-- rule:vip-has-no-ai -->
**VIPs never meet the AI.** A VIP surface shows no AI-blue draft, suggestion, summary or "let Ondra reply" affordance. Calls read "Rings you directly". This mirrors the product rule in `CLAUDE.md`, so a VIP component that renders anything AI-blue is a bug.

<!-- rule:not-the-ai-template -->
**Not the AI template.** The category default is Inter or Geist on black with a violet glow (Numa, Synthflow and most AI startups). Ondra stays out of it with Funnel's notched letterforms, one azure signal instead of gradients, real rendered imagery (the 3D floor) and working product UI as proof. No glowing orbs, no purple, no sparkle-and-waveform decoration, no glass cards as decoration.

<!-- rule:no-fake-proof -->
**Label illustrative values honestly.** Sample conversations, KPI numbers and names on marketing pages are examples, never claims. No invented stats, logos or testimonials. See `docs/marketing/positioning.md` for the claims we cannot make yet.

## 3. Type

Three free (OFL) families, self-hosted through `@fontsource-variable`:
- **Funnel Display**, weight 600 (500 for very large sizes): page titles, section headings, the hero headline, large numerals. Its notches and ink traps carry the "engineered" feel. Use the `font-display` utility.
- **Funnel Sans**: everything functional. Body, labels, buttons, nav, table cells, inputs.
- **JetBrains Mono** (`font-mono`): data only. Timestamps in product mocks, VINs, stock numbers, call durations, phone numbers in tables. Never as decoration.
- Tabular numerals wherever digits line up.
- Headings `text-wrap: balance`, paragraphs `text-wrap: pretty`, prose 60-72ch.
- Tight tracking on display sizes (-0.025 to -0.035em), normal on text.
- More space above a heading than below it.
- Arabic, if the exporter market needs it: pair with IBM Plex Sans Arabic or Noto Kufi Arabic.

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
- Blue on a person's action in the dashboard; blue fills with dark text; the blue fill colour used as small text
- Inter, Geist or Space Grotesk; purple or violet anywhere

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

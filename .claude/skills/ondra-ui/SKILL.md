---
name: ondra-ui
description: Ondra's design system and UI rules for anything visual in this repo. Use whenever you build, restyle, review or write copy for the marketing site (apps/site) or the dealer dashboard (apps/web - Today, Inbox, Calls, Calendar, Clients, Tasks, Settings), including new components, Tailwind classes or theme tokens, shadcn or Radix components, charts, icons, empty and error states, motion, the floor tour and its photography, emails that render HTML, and screenshots or critiques of a page. Covers the Ink, Paper, Sodium, AI-blue and VIP-red tokens, Archivo widths, layout, motion, UX copy, and how AI-generated and VIP content must look. Use it even for a small tweak to a button or a label. Not for backend, API, database or agent-prompt work with no UI.
---

# Ondra UI

Ondra is staff for a car dealership: AI agents at every desk, people where a person is needed, and the owner's office that VIPs reach directly. The interface should feel like a well-run showroom at night: calm, precise, warm light on dark glass, nothing shouting. It is not a purple AI startup and not a generic SaaS card kit.

Visual authority, in order: the user's words, this skill, `design/README.md`, the prototypes in `design/mockups/` (`landing.html`, `app.html`). Where the prototypes break a rule below (they have a glowing amber dot and a loose radius set), the rule wins.

## 1. Pick the mode from the surface, then read one file

| Surface | Mode | Read now |
|---|---|---|
| `apps/site`, any marketing page, email campaign, social image | **Persuade**: earn attention, one memorable move | `references/marketing.md` |
| `apps/web`, anything a dealer operates | **Operate**: the tool disappears into the task | `references/dashboard.md` |

A landing page for the product is still Persuade. A settings screen is still Operate even if it is pretty. Read only the file for your surface. Read `references/tokens.md` before writing any CSS or Tailwind classes, and `references/components.md` before adding or restyling a component.

## 2. Named rules (these are product rules, not taste)

<!-- rule:amber-is-for-doing -->
**Amber is for doing.** Sodium `#F2A33A` marks the primary action, the active nav item and the current selection. It is a fill with Ink text on it (8.6:1). Never amber text on Paper (1.8:1), never white on amber (2.1:1), never amber as decoration.

<!-- rule:blue-means-the-ai-did-it -->
**Blue means the AI did it.** AI blue `#1E3F7A` on `#EAF1FF` marks anything Ondra said, drafted, booked, summarised or suggested, always with a label naming it ("Drafted by Ondra"). Nothing else is blue. When a person edits or sends it, the blue goes.

<!-- rule:red-is-rare -->
**Red is rare.** VIP red `#A3191E` on `#FFE9EA` is for VIP contacts and overdue items only. Errors use Ink with a clear message, destructive buttons use an outline and an explicit verb, bad deltas are muted grey with a down arrow.

<!-- rule:vip-has-no-ai -->
**VIPs never meet the AI.** A VIP surface shows no AI-blue draft, suggestion, summary or "let Ondra reply" affordance. Calls read "Rings you directly". This mirrors the product rule in `CLAUDE.md`, so a VIP component that renders anything AI-blue is a bug.

<!-- rule:paper-is-not-the-cream-template -->
**Paper is not the cream template.** Paper `#F1EFEA` sits next to the warm-cream look that marks AI-generated pages. What keeps Ondra out of it: Archivo, never a serif; no italic accent word in a headline; no terracotta or clay; real dealership imagery. Do not add any of those.

<!-- rule:no-fake-proof -->
**Label illustrative values honestly.** Sample conversations, KPI numbers and names on marketing pages are examples, never claims. No invented stats, logos or testimonials. See `docs/marketing/positioning.md` for the claims we cannot make yet.

## 3. Type

One family: Archivo (variable, `wdth` 62-125, `wght` 300-800).
- `wdth` 125, weight 700-800: page titles, section headings, the hero headline, large KPI numerals. Use the `font-display` utility from the tokens.
- `wdth` 100: everything functional. Body, labels, buttons, nav, table cells, inputs, chart text.
- Tabular numerals wherever digits line up: prices, times, KPIs, tables.
- Headings `text-wrap: balance`, paragraphs `text-wrap: pretty`, prose 60-72ch.
- More space above a heading than below it.
- Never a display width in a button, label or table cell.

## 4. Before you build

Write these down (in your head or a comment), then build:
1. The one job of the screen or section, in one sentence.
2. The one signature move (marketing: the walk-through, the showroom photo; dashboard: the AI-blue provenance trail). Spend boldness there and keep everything around it quiet.
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
- White text on amber; amber text on Paper; an amber focus ring on Paper

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

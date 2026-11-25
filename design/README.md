# Design

UI concepts for Ondra. These are static prototypes with sample data, not production code. Use them as the reference for layout, copy and tone when building `apps/web` and the marketing site.

## Mockups

| File | What it is |
|---|---|
| `mockups/landing.html` | Marketing landing page. A photo of a dealership exterior zooms in as you scroll, then you walk through a 3D dealership floor where each desk is staffed by an AI agent with a label above it (voice, messaging, booking, service, routing, follow-up). The walk ends at the owner's glass office: VIP calls skip the agents and ring straight through. |
| `mockups/app.html` | Clickable dashboard prototype: Today (revenue dashboard), Inbox, Calls, Calendar, Clients, Tasks and Settings (appointment types, routing rules, knowledge and unanswered questions, channel connections). |

Open either file directly in a browser. `landing.html` embeds three.js (r150), so it runs offline apart from the fonts and the exterior photo.

## The landing page concept

- **Outside:** a real photo of a dealership exterior with the headline "Your dealership, fully staffed." Replace the stock photo with the pilot dealer's own showroom (with permission).
- **Walk in:** scroll-driven only. Nothing animates on its own.
- **The floor:** stylised 3D figures at desks, like an architect's model, so the agents read as staff without pretending to be real people.
- **Labels:** each agent's label shows its role, its desk and what it's doing right now.
- **The owner's office:** the one room with a red label, because VIPs never reach the AI.
- **Close:** "None of them are people. All of them are on your side."

## Visual language (Night Shift, November 2026)

Superseded the original paper, ink and amber look; the mockups keep their layouts but not their colours. Full tokens and rules are in the `ondra-ui` skill (`.claude/skills/ondra-ui/references/tokens.md`).

| Token | Value | Use |
|---|---|---|
| Night / bg / surface | `#06080B` / `#0A0D12` / `#121822` | Grounds, darkest to lightest |
| Text | `#EAF0F7`, muted `#8E9CB0` | |
| Ondra blue | `#2F6CF6` fill, `#7FA9FF` as text | The brand, and anything the AI did |
| VIP red | `#FF7A7A` on `#3A1517` | VIPs and overdue only |
| Type | Funnel Display (headings), Funnel Sans (text), JetBrains Mono (data) | Free, OFL, self-hosted |

## Known gaps

- The exterior photo is linked from Unsplash. The artifact viewer and some hosts block external images; embed or self-host it for production.
- The 3D figures are built from primitives. Realistic people would need licensed 3D models.
- On phones the labels can crowd the scene; the mobile layout needs a pass before launch.

## Since the mockups

- The marketing site now lives in `apps/site`. The UI rules for everything (tokens, components, copy, review) are in the `ondra-ui` skill at `.claude/skills/ondra-ui/`; where these mockups disagree with it, the skill wins.
- The 3D walk-through in `landing.html` has been replaced on the live site by a photographic floor tour with robot agents (`apps/site/components/FloorTour.tsx`). See `docs/DECISIONS.md` for why.
- The hero and tour images are generated placeholders (`apps/site/public/`, prompts in `docs/marketing/image-prompts.md`) until we have the pilot dealer's own showroom.

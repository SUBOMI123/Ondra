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

## Visual language

| Token | Value | Use |
|---|---|---|
| Ink | `#16171B` / `#17181C` | Text, sidebar |
| Paper | `#F2F2EF` / `#F1EFEA` | App and page backgrounds |
| Sodium amber | `#F2A33A` | Primary actions, active states |
| AI blue | `#1E3F7A` on `#EAF1FF` | Anything the AI said or did |
| VIP red | `#A3191E` on `#FFE9EA` | VIPs and overdue items only |
| Type | Archivo (Google Fonts), width 125 for headings, 100 for body | |

## Known gaps

- The exterior photo is linked from Unsplash. The artifact viewer and some hosts block external images; embed or self-host it for production.
- The 3D figures are built from primitives. Realistic people would need licensed 3D models.
- On phones the labels can crowd the scene; the mobile layout needs a pass before launch.

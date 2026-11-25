# Ondra roadmap: from landing page to pilot

How we get from the marketing site to a dealer using Ondra. The build order and acceptance criteria are in `BUILD_PLAN.md` §12; this file adds sequencing: what design must be ready before each step, what the founders must have in place, and when a pilot can start. Written 2026-11-25.

## Where we are

- **Done:** the marketing site (`apps/site`), logo, brand palette, hosting architecture (`docs/ARCHITECTURE.md`), demo form wired to Formspree.
- **Not started:** the product itself. No API, database, dashboard or agent exists yet.
- **Out of date:** `design/mockups/app.html` and the dashboard part of the `ondra-ui` skill (`references/dashboard.md`). Both predate the champagne palette and the move away from a Lagos-only story: they use an old navy palette, a font width Inter doesn't have, and Lagos sample data. They must be refreshed before any dashboard screen is built (D0 below).

## Three tracks, run in parallel

### 1. Founders: things only you can do, with long lead times

Start these now. Several take weeks and block a real pilot, not the build.

| Item | Blocks | Lead time |
|---|---|---|
| Meta Business verification, then apply as a Meta Tech Provider | Real WhatsApp (Step 2 uses mocks until then) | Weeks |
| A2P 10DLC registration for business texting | Real SMS | Weeks |
| Pick Twilio or Telnyx (§17.1) | Real SMS (Step 2), voice (Step 5) | A decision |
| Accounts: Anthropic API, LiveKit Cloud, Postmark | Real replies, voice, email | Days |
| Pilot dealer: their WhatsApp export, typical calls, current tools and DMS | Golden conversations (Step 2 needs 20), DMS adapter (Step 7) | Depends on the dealer |
| Pick STT and TTS vendors after a latency and accent test (§17.3) | Voice (Step 5) | Test by Step 5 |
| Pick the container host and Postgres (Fly.io or Render, Neon or Supabase) | First staging deploy | A decision |
| Pricing model (§17.6) | Self-serve onboarding (Step 11) | Before Step 11 |
| Confirm the product name and trademark (§16.1) | Printing, signage, legal docs | Before launch |

### 2. Design: one step ahead of the build

Every screen is designed and approved before the step that builds it, so engineering never waits on taste decisions. Designs are clickable prototypes built in code (React, with mock data), shown in the shared preview so they can be reviewed on a phone, because that's where the real product runs. Figma is optional and only for exploration.

| # | Design work | Needed for | Screens |
|---|---|---|---|
| D0 | **Dashboard design system.** Apply the champagne palette to an all-day work tool: light or dark default, density, tables, forms, sheets, every state (loading, empty, error, AI-drafted, VIP, opted out). Rewrite `references/dashboard.md` and refresh `app.html`. | Step 1 | Component sheet |
| D1 | App shell, sign-in, navigation, role switching, phone layout | Step 1 | Sign in, shell, empty Today |
| D2 | **Inbox** (the core screen), thread with calls inline, AI brief panel, approving drafts, take over and hand back, client profile and timeline, task board with SLA timers | Steps 2 and 3 | Inbox, Client, Tasks |
| D3 | Calendar by person and bay, drag to reschedule, appointment types and resources in settings | Step 4 | Calendar, Settings: booking |
| D4 | Calls list, call detail with transcript and recording, live call view with barge and transfer | Step 5 | Calls, Live call |
| D5 | Routing rules builder, follow-up sequences, "Questions Ondra couldn't answer", rating AI replies | Step 6 | Settings: routing, Knowledge |
| D6 | Integrations with health status, inventory | Step 7 | Settings: integrations, Inventory |
| D7 | Owner's WhatsApp briefing templates and approval buttons | Step 8 | Message templates |
| D8 | Home dashboard: KPIs, pipeline, AI vs staff | Step 9 | Today |
| D9 | Audit log, data export and delete | Step 10 | Settings: compliance |
| D10 | Self-serve onboarding wizard | Step 11 | Onboarding |

### 3. Build: BUILD_PLAN §12, one step at a time

Each step ends with its acceptance tests passing and a demo, then stops for review before the next begins (as `CLAUDE.md` requires).

| Step | What | Design needed |
|---|---|---|
| 1 | Foundations: monorepo, Docker Compose, FastAPI, migrations, auth and roles, tenant isolation with row-level security, dashboard shell, seed data | D0, D1 |
| 2 | Channel gateway and text agent, with mocks for every channel, VIP and draft-mode policy, 20 golden conversations | D2 (partly) |
| 3 | Inbox, clients, tasks | D2 |
| 4 | Booking | D3 |
| 5 | Voice | D4 |
| 6 | Routing, follow-ups, learning loop, opt-outs | D5 |
| 7 | Integrations (ADF, inventory feed, DMS adapter) | D6 |
| 8 | Owner WhatsApp layer | D7 |
| 9 | Analytics dashboard | D8 |
| 10 | Hardening and compliance | D9 |
| 11 | Instagram and self-serve onboarding | D10 |

## When a pilot can start

- **Earliest useful pilot: after Step 4, in draft mode, on text channels.** Ondra drafts replies and bookings, and staff approve every one. That needs real SMS or WhatsApp from the founder track, and the pilot dealer's data for the evals.
- **Calls join after Step 5.** Phone calls are dealers' busiest channel, so the pilot is only fully representative from here.
- **Automatic replies** are turned on channel by channel once the dealer trusts the drafts, which is the same path the website describes.

## Rules that apply throughout

From `CLAUDE.md`: tenant isolation proven by tests, a mock for every external service, `docker compose up` with no real accounts, unverified API details behind interfaces marked `TODO(verify)`, and decisions logged in `docs/DECISIONS.md`. The product rules (VIPs never get AI, opt-outs block every channel, consent before automated outreach, no price or date commitments without policy, dealers keep their numbers) get tests from the step that first touches them.

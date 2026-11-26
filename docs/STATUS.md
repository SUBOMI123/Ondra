# Status

The one place to see where Ondra is. Updated with every piece of work (see `CLAUDE.md`). Plan and acceptance criteria:
`BUILD_PLAN.md` §12. Why things are the way they are: `docs/DECISIONS.md`. Sequencing and founder lead times: `docs/ROADMAP.md`.

**Last updated:** 2026-11-26 · **Now:** Step 2, the last open item (reply latency) · **Next:** Step 3, Inbox

## Build steps

| Step | What | Status |
|---|---|---|
| 1 | Foundations: monorepo, Docker Compose, Postgres with row-level security, auth and roles, dashboard shell, seed data | **Done** (accepted 2026-11-25) |
| 2 | Channel gateway and text agent | **Almost done**: 3 of 4 acceptance checks met, latency open |
| 3 | Inbox, clients, tasks (API first, then screens) | Not started; screens designed with example data |
| 4 | Booking | Not started; Calendar designed with example data |
| 5 | Voice | Not started; Calls designed with example data |
| 6 | Routing, follow-ups, learning loop | Not started |
| 7 | Integrations (ADF, inventory feed, DMS) | Not started |
| 8 | Owner WhatsApp layer | Not started |
| 9 | Analytics | Not started |
| 10 | Hardening and compliance | Not started |
| 11 | Instagram and self-serve onboarding | Not started |

### Step 2 acceptance

| Check | Status | Evidence |
|---|---|---|
| A mock WhatsApp message gets a correct AI reply in under 5 s | **Open** | Correct: yes. Median about 3 s; turns with 3 or 4 tool lookups take 5 to 6.4 s |
| A VIP gets no AI reply and an alert is created | Met | `test_vip_gets_no_ai_and_the_owner_is_alerted`; live stack check |
| Draft mode stores a draft | Met | `test_draft_mode_stores_a_draft_and_sends_nothing` |
| 20 golden conversations pass | Met | 22 runnable, all pass against the real model (`evals/run.py --repeat 2`: 44/44) |

## What works today

- **Marketing site** (`apps/site`): live-ready static site, demo form to Formspree.
- **API** (`apps/api`):
  - sign-in, roles and tenant isolation;
  - clients, inventory, team;
  - settings (business hours, reply rules, channels) and team management (invite, roles, deactivate);
  - channel webhooks for WhatsApp, SMS and email (mock until provider accounts exist);
  - the AI agent with its policy layer;
  - knowledge search with Voyage embeddings.
- **Dashboard** (`apps/web`): sign-in, invite acceptance, Settings, Clients, client profile and Inventory on real data. Today, Inbox, Tasks, Deals, Calendar and Calls are designed but show **example data** until their steps.
- **Quality:** 99 Python tests, 22 golden conversations against the real model, and `npm run review:ui` on 12 pages.

## Waiting on the founders

| Item | Blocks | Status |
|---|---|---|
| Rotate the Anthropic and Voyage keys (both were pasted in chat) and set them in the environment settings | Security | **Do now** |
| Counsel: may a person reply after STOP when the customer writes in again (golden 009) | Step 6 opt-out handling | Open |
| Counsel: which states need AI disclosure up front (the setting exists) | Pilot launch | Open |
| Meta Business verification, Tech Provider application | Live WhatsApp | Not started (weeks) |
| A2P 10DLC registration; pick Twilio or Telnyx | Live SMS, voice | Not started (weeks) |
| Postmark account (also needed to email invites) | Live email, invite emails | Not started |
| Real conversations: mystery-shop dealers, pilot exports | Replacing the synthetic golden set | Not started |
| Container host and managed Postgres | First staging deploy | Not decided |

## Known gaps (honest list)

- The AI turn runs as a background task, not a durable queue: an API restart mid-reply loses that reply (Step 3 moves it to the worker).
- Delivery receipts from providers are logged, not stored.
- Team invites are shown as a link to copy; nothing is emailed yet.
- Connecting a channel registers the address; provider onboarding (Meta Embedded Signup, Twilio numbers) is Step 11.
- The golden conversations are synthetic. `must` checks are pattern-based and can misjudge good replies.
- Docker Hub rate-limits image pulls from this build environment; local images are layered from the last good build.

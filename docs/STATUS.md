# Status

The one place to see where Ondra is. Updated with every piece of work (see `CLAUDE.md`). Plan and acceptance criteria:
`BUILD_PLAN.md` §12. Why things are the way they are: `docs/DECISIONS.md`. Sequencing and founder lead times: `docs/ROADMAP.md`.

**Last updated:** 2026-11-26. **Now:** Step 5, Voice: call handling done (5b); voice worker next (5c)

## Build steps

| Step | What | Status |
|---|---|---|
| 1 | Foundations: monorepo, Docker Compose, Postgres with row-level security, auth and roles, dashboard shell, seed data | **Done** (accepted 2026-11-25) |
| 2 | Channel gateway and text agent | **Done** (2026-11-26), all 4 acceptance checks met |
| 3 | Inbox, clients, tasks | **Done** (2026-11-26), both acceptance checks met in a real browser |
| 4 | Booking | **Done** (2026-11-26), all acceptance checks met with the real model |
| 5 | Voice | In progress: call records, VIP routing, missed calls and summaries done. Voice worker, Calls screen, real phone line to come |
| 6 | Routing, follow-ups, learning loop | Not started |
| 7 | Integrations (ADF, inventory feed, DMS) | Not started |
| 8 | Owner WhatsApp layer | Not started |
| 9 | Analytics | Not started |
| 10 | Hardening and compliance | Not started |
| 11 | Instagram and self-serve onboarding | Not started |

### Step 4 acceptance

| Check | Status | Evidence |
|---|---|---|
| A dealer creates a custom appointment type in settings | Met | Browser: Settings > Booking > Add appointment type ("EV charging walkthrough"); `test_a_dealer_creates_a_custom_type_and_books_it` |
| AI books a test drive and a service appointment (with a bay) from a WhatsApp chat | Met | Mock WhatsApp, real model, worker: test drive of the CR-V Saturday 10 am with Daniel; brake service tomorrow 7 am in Bay 1 with Maria, customer waiting |
| Without double-booking | Met | A third customer asked for the same Saturday 10 am and was offered 9:00, 11:00 or 11:30. No person or bay overlaps in the database. Exclusion constraints; a race of 5 simultaneous bookings yields exactly 1 (fails without the constraint) |
| Reminders fire | Met | Test drive reminder sent through the worker ("Reminder from Prestige Motors: your test drive is Saturday at 10 am with Daniel..."). Reminders skip moved, cancelled and opted-out appointments, and respect quiet hours |
| Staff see them in the calendar | Met | Calendar shows both with Ondra's mark; details show the bay; showed, no-show and cancel actions |

### Step 3 acceptance

| Check | Status | Evidence |
|---|---|---|
| A staff user can work a lead end to end in the UI | Met | Browser run on a fresh stack (`scratchpad/step3-acceptance.cjs`). New text appears live without reload. Ondra's draft is edited and sent, credited to the approver. Take over, then a staff reply. Opted-out client has no reply box. Task completed with undo. Client history shows the reply and Ondra's brief. VIP profile has no AI content |
| An overdue task escalates | Met | Seeded overdue task escalated by the worker to the manager within a minute of start; `test_overdue_tasks_escalate_once_to_a_manager_then_owner` |

### Step 2 acceptance

| Check | Status | Evidence |
|---|---|---|
| A mock WhatsApp message gets a correct AI reply in under 5 s | Met, with a tail | Typical replies: median about 3 s. Replies needing a lookup and a handoff (export buyer on WhatsApp, email leads) take three model rounds and run 5 to 6 s when the model is slower: 1 in 100 turns on 2026-11-26 morning, 4 in 40 on the Step 3 rerun |
| A VIP gets no AI reply and an alert is created | Met | `test_vip_gets_no_ai_and_the_owner_is_alerted`; live stack check |
| Draft mode stores a draft | Met | `test_draft_mode_stores_a_draft_and_sends_nothing` |
| 20 golden conversations pass | Met | 22 runnable, all pass against the real model: 110 of 110 across the last two runs (`--repeat 2` and `--repeat 3`) |

## What works today

- **Marketing site** (`apps/site`): static site ready to deploy, demo form to Formspree.
- **API** (`apps/api`):
  - sign-in, roles and tenant isolation;
  - clients with timeline, inventory;
  - settings and team management;
  - channel webhooks (mock until provider accounts exist);
  - the AI agent with its policy layer;
  - knowledge search (Voyage);
  - inbox conversations (approve and edit drafts, reply, take over, hand back, assign);
  - tasks with deadlines in opening hours, and escalation;
  - live updates (server-sent events).
- **Worker** (`python -m ondra_api.worker`, compose service `worker`): runs the AI's replies from a durable Postgres queue with retries, and escalates overdue tasks every minute.
- **Calls (API, Step 5):** call records, routing before anyone speaks (VIP rings the owner, never the AI), missed-call text-back only with recorded consent (otherwise a call-back task), summaries after the call, calls in the Inbox thread and client timeline. No voice agent or phone line yet.
- **Booking:** appointment types from templates or custom, bays and loaners, availability (hours, notice, buffer, eligible staff, bays), the AI's booking tools, database-enforced no double-booking, reminders, the calendar, no-show tracking.
- **Dashboard** (`apps/web`) on real data: sign-in, invites, Inbox (live), Tasks, Clients and client profile, Inventory, Calendar (live), Settings (including Booking), and sidebar counts. Today, Deals and Calls still show **example data** until their steps (Today and Deals: Step 9 analytics and pipeline; Calls: Step 5).
- **Quality:** 141 Python tests, 22 golden conversations against the real model, browser acceptance runs, and `npm run review:ui` on 12 pages.

## Waiting on the founders

| Item | Blocks | Status |
|---|---|---|
| Rotate the Anthropic, Voyage and LiveKit keys (all were pasted in chat) and set them in the environment settings | Security | **After testing, before anything goes live** (founder decision) |
| Counsel: may a person reply after STOP when the customer writes in again (golden 009) | Step 6 opt-out handling | Open |
| Counsel: which states need AI disclosure up front (the setting exists) | Pilot launch | Open |
| Counsel: may we text back a missed call when the caller hasn't opted in to texts? Today we don't, so most first-time callers get a call-back task, not a text | Missed-call text-back reach | Open |
| Counsel: call recording consent (two-party states) | Keeping call recordings | Open |
| Meta Business verification, Tech Provider application | Live WhatsApp | Not started (weeks) |
| A2P 10DLC registration; pick Twilio or Telnyx | Live SMS, voice | Not started (weeks) |
| Postmark account (also needed to email invites) | Live email, invite emails | Not started |
| Real conversations: mystery-shop dealers, pilot exports | Replacing the synthetic golden set | Not started |
| Container host and managed Postgres | First staging deploy | Not decided |

## Known gaps (honest list)

- **In draft mode, a booking happens at once; only the reply waits for approval.** The slot is held, so nobody else takes it, but the customer isn't told until a person approves. That's arguably right (holding the slot), but it's your call.
- **Transport can't be changed after booking** (for example, adding a loaner later). Ondra asks wait, loaner or drop-off before booking a service. A person can edit it from the calendar in a later step.
- Resources are capacity 1. A "bay" that takes two cars needs to be two resources.
- Test drives aren't tied to a specific car in stock yet (the car is noted in details). Holding the demo car itself needs a `demo_vehicle` resource per car, planned with inventory in Step 7.

- **"New message" (starting a conversation with a customer) isn't built.** Business-initiated messages need consent checks and WhatsApp templates; that work is planned for Step 6 (follow-ups).
- **A worker crash at the wrong moment can send a reply twice:** after the provider accepted the send, but before the job was marked done. Fix with per-message idempotency keys before real providers go live.
- Delivery receipts from providers are logged, not stored on the message.
- Team invites are shown as a link to copy; nothing is emailed yet.
- Connecting a channel registers the address; provider onboarding (Meta Embedded Signup, Twilio numbers) is Step 11.
- The golden conversations are synthetic. `must` checks are pattern-based and can misjudge good replies.
- **Reply latency tail, growing:** replies that look something up, act (hand off or book), then write take three model rounds, so they run 5 to 6.5 s when the model is slow. On the Step 4 run, 9 of 52 turns were over 5 s (median 3.4 s), up from 4 of 40 in Step 3 and 1 of 100 in Step 2: booking adds rounds, and per-call times were higher that run (up to 4 s for one call). The remaining fix is a faster model for the final reply-writing round, which changes the plan's model choice (§6.1): a founder decision, and it matters more for voice in Step 5.
- In this build environment, containers can't reach Voyage (Anthropic is reachable), so the seed's embedding step falls back and the knowledge backfill runs from the host. Production hosts won't have this limit.
- Docker Hub rate-limits image pulls from this build environment; local images are layered from the last good build.

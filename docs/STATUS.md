# Status

The one place to see where Ondra is. Updated with every piece of work (see `CLAUDE.md`). Plan and acceptance criteria:
`BUILD_PLAN.md` §12. Why things are the way they are: `docs/DECISIONS.md`. Sequencing and founder lead times: `docs/ROADMAP.md`.

**Last updated:** 2026-11-28. **Now:** One top role (Admin; owner merged into it) and every-control-works are done from `docs/PLAN.md`; the rest of that plan is in progress. Steps 6 to 9 are built with their acceptance checks met, and the code-only gaps found along the way are closed (Deals board, honest texting on calls, handoffs said once, rating notes and eval export, per-person numbers, the owner's assistant thread, pinned feed downloads). Waiting for the founder before Step 10. Step 5, Voice, is parked with a backlog (below).

## Build steps

| Step | What | Status |
|---|---|---|
| 1 | Foundations: monorepo, Docker Compose, Postgres with row-level security, auth and roles, dashboard shell, seed data | **Done** (accepted 2026-11-25) |
| 2 | Channel gateway and text agent | **Done** (2026-11-26), all 4 acceptance checks met |
| 3 | Inbox, clients, tasks | **Done** (2026-11-26), both acceptance checks met in a real browser |
| 4 | Booking | **Done** (2026-11-26), all acceptance checks met with the real model |
| 5 | Voice | **Parked with a backlog** (2026-11-27). Acceptance: real call books an appointment, met; latency measured and logged, met (2.7 s average, target 1 s not reached); warm transfer to a manager on a real call, **not yet proven** |
| 6 | Routing, follow-ups, learning loop | **Built; all 3 acceptance checks met** (2026-11-27). Two parts of the plan's learning loop are not built: exporting ratings into the eval set, and automatic pattern-finding across draft edits (see Known gaps) |
| 7 | Integrations (ADF, inventory feed, DMS) | **Built; all 3 acceptance checks met** (2026-11-27). No real CRM, feed or DMS has been connected: everything is proven against mocks and files |
| 8 | Owner WhatsApp layer | **Built; both acceptance checks met** (2026-11-27), on the mock WhatsApp channel. Real voice notes need a transcription service (founder decision) and real delivery needs the dealer's WhatsApp connected and two templates approved |
| 9 | Analytics | **Built; acceptance check met** (2026-11-27). The Today page runs on real events; the Deals board is still example data |
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
| An overdue task escalates | Met | Seeded overdue task escalated by the worker to the manager within a minute of start; `test_overdue_tasks_escalate_once_to_a_manager_then_an_admin` |

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
- **Voice agent** (`apps/voice`, see `docs/VOICE.md`): LiveKit Agents worker on the same tools as text, every spoken sentence checked before it's said, warm transfer, per-turn latency on the call record. Runs against the real model in text mode; registers with the LiveKit Cloud project. Not yet on a phone line.
- **Sign-in with Clerk** (switch `AUTH_PROVIDER=clerk`): Clerk handles sign-in, two-step sign-in and invitation emails; Ondra keeps roles, permissions and tenant isolation. Admins must use two-step sign-in (one top role since 2026-11-28; owner merged into admin). Invite-only. Prestige Motors is linked to a Clerk Organization on the development instance. Proven in a real browser with Clerk test accounts: a salesperson signs in to the dashboard; an owner without two-step sign-in is held on the setup screen and gets no client data. Local sign-in remains for development and tests.
- **Calls (API, Step 5):** call records, routing before anyone speaks (VIP rings the owner, never the AI), missed-call text-back only with recorded consent (otherwise a call-back task), summaries after the call, calls in the Inbox thread and client timeline. No voice agent or phone line yet.
- **Booking:** appointment types from templates or custom, bays and loaners, availability (hours, notice, buffer, eligible staff, bays), the AI's booking tools, database-enforced no double-booking, reminders, the calendar, no-show tracking.
- **Dashboard** (`apps/web`) on real data (the Inbox shows one thread per client across text, WhatsApp, email and calls): sign-in, invites, Inbox (live), Tasks, Clients and client profile, Inventory, Calendar (live), Settings (including Booking), Team (search, role and status filters, 25 per page), and sidebar counts. Calls (call-backs first, Ondra's summaries and transcripts, VIP calls with no AI content) and phone threads in the Inbox are on real data. Today and Deals still show **example data** until Step 9 (analytics and pipeline).
- **Quality:** 166 Python tests, 22 golden conversations against the real model, browser acceptance runs, and `npm run review:ui` on 13 pages.

### Step 9 acceptance

| Check | Status | Evidence |
|---|---|---|
| Every metric on the dashboard is traceable to events | Met | `test_every_number_is_traceable_to_its_events`: for each number, `GET /analytics/trace` returns exactly as many events as the number, each a real row in `events`. On the page, "See what's behind this" opens that list (checked in a browser) |
| Numbers match a hand-calculated test fixture | Met | Three days worked out by hand in `packages/core/tests/test_metrics.py`, checked as plain functions and again through the API and database in `test_the_dashboard_matches_the_hand_calculated_fixture` (including the 11:30 pm lead landing on the dealership's day) |

### Step 8 acceptance

| Check | Status | Evidence |
|---|---|---|
| Briefing arrives at the configured local time with correct counts | Met in tests | `test_the_briefing_arrives_at_the_configured_time_with_correct_counts`: each of the five numbers moves by exactly what was added; the job is lined up for 7:30 in the dealership's zone (also across a clock change), sends the template with those numbers, and lines up the next day. Sent from Settings in a real browser too |
| A voice note updates the right client and creates a task | Met with the real model, mock transcription | "Sara Kling ... wants the white Highlander now, budget's forty thousand. Have Daniel give her a call tomorrow": Sarah King's deal updated, a task for Daniel Okafor due the next day at 5 pm, and the owner told what was done. The words came from a mock transcriber, not real audio |

### Step 7 acceptance

| Check | Status | Evidence |
|---|---|---|
| A qualified lead produces a valid ADF/XML email | Met in tests | `test_a_qualified_lead_produces_a_valid_adf_email_once`: a lead captured from a text conversation is emailed once to the CRM address; the XML passes Ondra's ADF checker (built from the DTD) and carries the car, the buyer and their notes. Not yet received by a real CRM |
| Inventory CSV import updates stock | Met | `test_a_csv_import_updates_stock_after_a_preview` (price and mileage updated, new cars added, the AI's search sees them); also run in a real browser: a 4-row file previewed, 3 imported, 1 bad row reported |
| RO status answered from mock DMS | Met with the real model | Golden 006: "hey is my car ready yet?" answered "not yet, waiting on parts, Maria is your advisor" with no invented date (4 of 4 runs); full golden set 27 of 27 |

### Step 6 acceptance

| Check | Status | Evidence |
|---|---|---|
| Rules route test messages correctly across 10 scenarios | Met in tests; rules created, reordered, switched off and checked in a real browser | `apps/api/tests/test_routing.py`: 12 routing scenarios plus tenant isolation, each a real message through the webhook, job queue and Postgres (round-robin, keeping a customer's rep, service, complaint rule with alert, VIP over any rule, a named person per channel, AI kept out of a topic, capacity, nobody in, Lagos covering Dallas, drafts after hours, rule order, empty team) |
| STOP on SMS blocks all outbound to that contact | Met in tests | `test_stop_on_sms_blocks_all_outbound_on_every_channel`: after STOP by text, the lined-up follow-up is cancelled, consent is opted out on all four channels, a person's reply is refused on text and WhatsApp, a reminder is blocked, a later message gets no AI reply, and nothing leaves any channel |
| An unanswered question answered by the dealer is used by the AI on the next identical question | Met | Real model, 2026-11-27: "Do you install remote starters on cars you sell?" was handed to service and listed as unanswered; after the answer was saved, the next customer asking the same got "Yes, our service department installs remote starters on most models, and it's usually done the same day". Also `test_an_unanswered_question_answered_once_is_used_next_time`; answering checked in a real browser |

## UI overhaul (started 2026-11-27, founder's review)

| Screen | State |
|---|---|
| VIPs: made from the client, ink tag and ring, out of Settings | Done |
| Shortcuts (were "Saved views") as working Inbox filters: drafts, VIPs waiting, after-hours leads | Done |
| VIP handler is told (task and WhatsApp) and sees "VIPs waiting" | Done |
| Settings as an index of pages in four groups | Done |
| Clients list: search by name, phone or email; deal, who looks after them, last in touch; paged | Done |
| Deals: salesperson from the start, next step on each card, drag between stages, Mine, deal panel | Done |
| Tasks: Mine stays a list; Everyone is a board with a column per person, drag or menu to reassign | Done |
| Inventory: days on the lot, buyers asking, make filter and sorts, hold/sold from the row, car panel with buyers | Done |
| Calls: filters (missed, Ondra answered, put through), one row per waiting caller, call and mark done from the row, who rang back and how long it took, undo | Done |
| Today: time to call back (median, open hours, per person) and one "callers waiting" line | Done |
| Calls: call back through the dealer's line (rings you, press 1, dials them from the dealer's number), logged automatically, with answering-machine detection telling a person from their voicemail | Built against a mock; needs Twilio live |

## Voice backlog (parked 2026-11-27)

Kept here by founder decision so work can move on. In rough order of what a pilot dealer would notice first.

| Item | Why it matters | Needs |
|---|---|---|
| Prove the warm transfer on a real call ("talk to a manager") | The last unmet Step 5 acceptance check | Call 2 of the session in docs/VOICE.md: a second phone on Grace (manager) in Team |
| Find the missing 2 seconds per turn | Turns take 3.4-3.8 s; model and voice account for about 1.2 s. The call record now stores the end-of-turn wait and tool time | **Report ready:** `python -m ondra_voice.report` splits each call's wait into end of turn, model, voice, tools and unaccounted. Needs call 1 |
| Speech recognition mishearing ("I we can't know the price of a Honda CR V") | Wrong words in, wrong answers out | **Ready (2026-11-27):** other models listen on the same call (`VOICE_STT_SHADOW`) and are scored against a read-aloud script (`python -m ondra_voice.bakeoff`). Needs call 1 of the session in docs/VOICE.md |
| Hear the 2026-11-27 fixes on a call | Today-already-passed days, asking which of two times, naming three cars, no needless apology: tested, not heard | One call |
| A test that listens to how the voice reads prices | ElevenLabs Flash misread prices and only a manual check caught it | Part of the 5e voice test set |
| A call nobody answers must not vanish | Worker down: caller hears ringing, nothing is recorded | Hosting (a public URL for Twilio's fallback route) and a no-worker alert |
| Recording with consent; fixed message when a VIP's call isn't answered; did the owner pick up after a cold transfer | Plan §4.2 | LiveKit Egress, Twilio call status, counsel on recording consent |

## Waiting on the founders

| Item | Blocks | Status |
|---|---|---|
| Rotate the Anthropic, Voyage, LiveKit, ElevenLabs and Twilio keys (all were pasted in chat) and set them in the environment settings | Security | **After testing, before anything goes live** (founder decision) |
| Clerk Dashboard: turn on Multi-factor methods (Authenticator application, Backup codes; leave "Require" off), Invite-only (Restrictions), and decide GitHub and Google sign-in (recommend GitHub off) | Owners and admins can't set up two-step sign-in until Multi-factor is on | **Waiting** |
| Clerk: a paid plan before production (MFA needs it; the development instance caps an Organization at 5 members) | Clerk in production | Not started |
| Counsel: may a person reply after STOP when the customer writes in again (golden 009) | Step 6 opt-out handling | Open |
| Counsel: which states need AI disclosure up front (the setting exists) | Pilot launch | Open |
| Counsel: may we text back a missed call when the caller hasn't opted in to texts? Today we don't, so most first-time callers get a call-back task, not a text | Missed-call text-back reach | Open |
| Counsel: is a customer's own inbound text consent to a follow-up text a day later? Today it isn't, so most text follow-ups become tasks for a person | How much follow-ups do by text | Open |
| Counsel: should quiet hours also hold appointment reminders and late-night replies? Today they hold follow-ups only | Quiet hours scope | Open |
| Counsel: call recording consent (two-party states) | Keeping call recordings | Open |
| Counsel: may a person return a missed call through Ondra's line to someone who texted STOP? Today yes (a person taps it each time, returning their call) | Call-back through the dealer's line | Open |
| Twilio: the dealer's number as a Twilio number or a verified caller ID, and a public API URL for the call-back webhooks | Call-back through the dealer's line going live | Not started |
| Counsel: is a caller's recorded spoken yes on a call enough consent to text them the details they asked for? (Ondra records it today) | Texting details from calls | Open |
| A computer to run the stack for the acceptance call (or a host); your mobile in Settings > Team | First real call | Waiting |
| Meta Business verification, Tech Provider application | Live WhatsApp | Not started (weeks) |
| **A2P 10DLC registration for (707) 306-8599** (Twilio Console > Messaging > Regulatory compliance) | Any real text: details from calls, missed-call text-back, reminders | **Start now** (weeks) |
| Postmark account (also needed to email invites) | Live email, invite emails | Not started |
| Real conversations: mystery-shop dealers, pilot exports | Replacing the synthetic golden set | Not started |
| Each pilot dealer's CRM lead address, and a test lead confirmed arriving in that CRM | Leads reaching the CRM for real | Not started |
| Which DMS the first pilot dealers use, and their partner programme | A live DMS connection | Open (plan §17 Q4) |
| Choose a speech-to-text service for the owner's voice notes (recorded files, not live calls) | Real voice notes to the assistant | Open |
| Get `ondra_morning_briefing` and `ondra_alert` approved in each pilot dealer's WhatsApp Business account | Briefings and alerts outside the 24-hour window | Not started (needs the dealer's WhatsApp connected first) |
| Container host and managed Postgres | First staging deploy | **Decided and live (2026-11-27):** Fly.io (API, job worker, voice worker in San Jose) + Supabase (Oregon), see docs/DEPLOY.md. Live: https://useondra.com (marketing site, Cloudflare Pages), https://app.useondra.com and https://api.useondra.com (dashboard on Fly too: Cloudflare Workers deploys fail from the cloud session) |

## Known gaps (honest list)

- **Analytics:** (1) reply time covers messages, not calls (needs ring timing from the carrier); (2) the dollar value of deals is an estimate on the Deals board only, not on Today; (3) leads from before Step 9 count toward neither Ondra nor the team, and replies before 2026-11-27 have no person attached; (4) no exports or custom dates.

- **Owner's WhatsApp line:** (1) no real speech-to-text for voice notes; (2) nothing has been sent through real WhatsApp, and the two templates aren't approved anywhere; (3) the briefing has no approve buttons; (4) admins only, not managers (each admin switches it on for themselves).

- **Integrations, not proven or not built:** (1) no real CRM has received an ADF lead, and how each CRM wants the email (body or attachment, subject) is unverified; (2) scheduled feed fetching pins the checked address, but behind an HTTPS proxy needs the proxy to refuse private ranges, and can't use feeds that need a login; (3) no real DMS vendor adapter exists (partner programs); (4) the CSV repair-order upload is manual and replaces the last one; (5) XML feeds that put data in attributes only aren't read.

- **Learning loop:** rated replies export as redacted draft eval cases, but a person has to write each expectation before it joins the golden set, and the redaction is pattern-based. Still not built: automatic pattern-finding across draft edits. Prices inside a dealer's own answers aren't repeated by Ondra (founder decision).
- **Follow-ups by text mostly become tasks** until counsel says whether an inbound text is consent to a later follow-up; WhatsApp follow-ups after 24 hours need templates, which aren't built.
- **Alerts addressed to the owner now go to their WhatsApp** (Step 8). Alerts for managers and other teams are still records only.

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
- **Before any pilot: a call nobody answers must not vanish.** Proven on the test call: when the voice worker is down or fails, the caller hears ringing until Twilio gives up, and nothing is recorded (no missed-call record, task or text). Fix: a disaster-recovery route on the Twilio trunk that forwards to the dealer's main line or the owner's mobile (needs a public URL, so it comes with hosting), plus an alert when no `ondra-voice` worker is registered.
- **From the first real calls (2026-11-26):** found and fixed: the made-up-car check mistook the caller's own car for an invented one and handed off instead of booking; goodbye was said twice; first reply ~0.7 s slower while libraries loaded; failed steps left no trace (now on the call record). Speech recognition misheard "Honda CR-V" and "can we do Friday": it now gets the stock's makes and models as hints; the bake-off on real phone audio is still to do.
- **Voice, honest list:** (1) speech style rewritten 2026-11-27 (short sentences, two cars, two times; measured on three scripted calls in text mode, see DECISIONS) but heard on two real calls 2026-11-27 (founder: "the voice sounded really good"); it still sometimes mentions a handoff twice; turns still take 3.4-3.8 s and the call record now measures the end-of-turn wait and tool time to find out why; texts offered on a call go to the mock until Twilio SMS and A2P 10DLC are set up; (2) after a cold transfer to a VIP's owner we can't yet tell if they answered (needs Twilio call status); (3) nothing is recorded yet (LiveKit Egress, with consent); (4) no fixed message plays when a VIP's call isn't answered (plan §4.2); (5) speech recognition, voice and real latency are untested until a real call. Voice chosen 2026-11-26 by blind test: Cartesia Sonic 3.6 "Jacqueline" (the ElevenLabs Flash voice on the first calls misread prices); not yet heard on a real call.
- **Ondra's text replies see only the channel they're on:** a WhatsApp reply doesn't read the client's SMS history yet, though staff see one merged thread. Fold the client's other channels into the agent's context in Step 6.
- A channel a client opens after a person took them over starts with Ondra on; take over again, or fix in Step 6 routing.
- **The plan's receptionist-and-specialists voice design was dropped for one agent:** measured slower and it pretended to transfer callers. See DECISIONS.
- Docker Hub rate-limits image pulls from this build environment; local images are layered from the last good build.

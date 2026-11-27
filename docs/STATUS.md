# Status

The one place to see where Ondra is. Updated with every piece of work (see `CLAUDE.md`). Plan and acceptance criteria:
`BUILD_PLAN.md` §12. Why things are the way they are: `docs/DECISIONS.md`. Sequencing and founder lead times: `docs/ROADMAP.md`.

**Last updated:** 2026-11-27. **Now:** Step 6. Routing is built and editable. Follow-up sequences with approval and quiet hours work end to end in tests; their settings section is unverified in a browser. Step 5, Voice, is parked with a backlog (below).

## Build steps

| Step | What | Status |
|---|---|---|
| 1 | Foundations: monorepo, Docker Compose, Postgres with row-level security, auth and roles, dashboard shell, seed data | **Done** (accepted 2026-11-25) |
| 2 | Channel gateway and text agent | **Done** (2026-11-26), all 4 acceptance checks met |
| 3 | Inbox, clients, tasks | **Done** (2026-11-26), both acceptance checks met in a real browser |
| 4 | Booking | **Done** (2026-11-26), all acceptance checks met with the real model |
| 5 | Voice | **Parked with a backlog** (2026-11-27). Acceptance: real call books an appointment, met; latency measured and logged, met (2.7 s average, target 1 s not reached); warm transfer to a manager on a real call, **not yet proven** |
| 6 | Routing, follow-ups, learning loop | In progress: routing engine (6a), "Who gets what" screen (6b), follow-ups and quiet hours backend (6c) done and tested. **The Follow-ups settings section is written and type-checked but not yet run in a browser or through `review:ui`** (the local database stopped). Next: verify that screen, learning loop (6d), acceptance (6e) |
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
- **Voice agent** (`apps/voice`, see `docs/VOICE.md`): LiveKit Agents worker on the same tools as text, every spoken sentence checked before it's said, warm transfer, per-turn latency on the call record. Runs against the real model in text mode; registers with the LiveKit Cloud project. Not yet on a phone line.
- **Sign-in with Clerk** (switch `AUTH_PROVIDER=clerk`): Clerk handles sign-in, two-step sign-in and invitation emails; Ondra keeps roles, permissions and tenant isolation. Owners and admins must use two-step sign-in. Invite-only. Prestige Motors is linked to a Clerk Organization on the development instance. Proven in a real browser with Clerk test accounts: a salesperson signs in to the dashboard; an owner without two-step sign-in is held on the setup screen and gets no client data. Local sign-in remains for development and tests.
- **Calls (API, Step 5):** call records, routing before anyone speaks (VIP rings the owner, never the AI), missed-call text-back only with recorded consent (otherwise a call-back task), summaries after the call, calls in the Inbox thread and client timeline. No voice agent or phone line yet.
- **Booking:** appointment types from templates or custom, bays and loaners, availability (hours, notice, buffer, eligible staff, bays), the AI's booking tools, database-enforced no double-booking, reminders, the calendar, no-show tracking.
- **Dashboard** (`apps/web`) on real data (the Inbox shows one thread per client across text, WhatsApp, email and calls): sign-in, invites, Inbox (live), Tasks, Clients and client profile, Inventory, Calendar (live), Settings (including Booking), Team (search, role and status filters, 25 per page), and sidebar counts. Calls (call-backs first, Ondra's summaries and transcripts, VIP calls with no AI content) and phone threads in the Inbox are on real data. Today and Deals still show **example data** until Step 9 (analytics and pipeline).
- **Quality:** 166 Python tests, 22 golden conversations against the real model, browser acceptance runs, and `npm run review:ui` on 13 pages.

### Step 6 acceptance

| Check | Status | Evidence |
|---|---|---|
| Rules route test messages correctly across 10 scenarios | Met in tests; rules created, reordered, switched off and checked in a real browser | `apps/api/tests/test_routing.py`: 12 routing scenarios plus tenant isolation, each a real message through the webhook, job queue and Postgres (round-robin, keeping a customer's rep, service, complaint rule with alert, VIP over any rule, a named person per channel, AI kept out of a topic, capacity, nobody in, Lagos covering Dallas, drafts after hours, rule order, empty team) |
| STOP on SMS blocks all outbound to that contact | Met in tests | `test_stop_on_sms_blocks_all_outbound_on_every_channel`: after STOP by text, the lined-up follow-up is cancelled, consent is opted out on all four channels, a person's reply is refused on text and WhatsApp, a reminder is blocked, a later message gets no AI reply, and nothing leaves any channel |
| An unanswered question answered by the dealer is used by the AI on the next identical question | Not started (6d) | |

## Voice backlog (parked 2026-11-27)

Kept here by founder decision so work can move on. In rough order of what a pilot dealer would notice first.

| Item | Why it matters | Needs |
|---|---|---|
| Prove the warm transfer on a real call ("talk to a manager") | The last unmet Step 5 acceptance check | A call with a second phone as the manager |
| Find the missing 2 seconds per turn | Turns take 3.4-3.8 s; model and voice account for about 1.2 s. The call record now stores the end-of-turn wait and tool time | One real call, then tune the end-of-turn wait or the lookups from the numbers |
| Real texts from calls | Ondra says "it's on its way" and the text goes to the mock | Twilio Account SID and Auth Token, A2P 10DLC approval, `FEATURE_SMS=true`. Until then, consider not offering texts on calls |
| Speech recognition mishearing ("I we can't know the price of a Honda CR V") | Wrong words in, wrong answers out | The recognition model comparison (try `VOICE_STT_MODEL=assemblyai/assemblyai-stt-3-7-realtime-agent`) on recorded calls |
| Hear the 2026-11-27 fixes on a call | Today-already-passed days, asking which of two times, naming three cars, no needless apology: tested, not heard | One call |
| A test that listens to how the voice reads prices | ElevenLabs Flash misread prices and only a manual check caught it | Part of the 5e voice test set |
| Handoff mentioned twice; occasional "anything else I can help with" | Sounds scripted | Prompt work against the scripted calls |
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
| Counsel: is a caller's recorded spoken yes on a call enough consent to text them the details they asked for? (Ondra records it today) | Texting details from calls | Open |
| A computer to run the stack for the acceptance call (or a host); your mobile in Settings > Team | First real call | Waiting |
| Meta Business verification, Tech Provider application | Live WhatsApp | Not started (weeks) |
| **A2P 10DLC registration for (707) 306-8599** (Twilio Console > Messaging > Regulatory compliance) | Any real text: details from calls, missed-call text-back, reminders | **Start now** (weeks) |
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
- **Before any pilot: a call nobody answers must not vanish.** Proven on the test call: when the voice worker is down or fails, the caller hears ringing until Twilio gives up, and nothing is recorded (no missed-call record, task or text). Fix: a disaster-recovery route on the Twilio trunk that forwards to the dealer's main line or the owner's mobile (needs a public URL, so it comes with hosting), plus an alert when no `ondra-voice` worker is registered.
- **From the first real calls (2026-11-26):** found and fixed: the made-up-car check mistook the caller's own car for an invented one and handed off instead of booking; goodbye was said twice; first reply ~0.7 s slower while libraries loaded; failed steps left no trace (now on the call record). Speech recognition misheard "Honda CR-V" and "can we do Friday": it now gets the stock's makes and models as hints; the bake-off on real phone audio is still to do.
- **Voice, honest list:** (1) speech style rewritten 2026-11-27 (short sentences, two cars, two times; measured on three scripted calls in text mode, see DECISIONS) but heard on two real calls 2026-11-27 (founder: "the voice sounded really good"); it still sometimes mentions a handoff twice; turns still take 3.4-3.8 s and the call record now measures the end-of-turn wait and tool time to find out why; texts offered on a call go to the mock until Twilio SMS and A2P 10DLC are set up; (2) after a cold transfer to a VIP's owner we can't yet tell if they answered (needs Twilio call status); (3) nothing is recorded yet (LiveKit Egress, with consent); (4) no fixed message plays when a VIP's call isn't answered (plan §4.2); (5) speech recognition, voice and real latency are untested until a real call. Voice chosen 2026-11-26 by blind test: Cartesia Sonic 3.6 "Jacqueline" (the ElevenLabs Flash voice on the first calls misread prices); not yet heard on a real call.
- **Ondra's text replies see only the channel they're on:** a WhatsApp reply doesn't read the client's SMS history yet, though staff see one merged thread. Fold the client's other channels into the agent's context in Step 6.
- A channel a client opens after a person took them over starts with Ondra on; take over again, or fix in Step 6 routing.
- **The plan's receptionist-and-specialists voice design was dropped for one agent:** measured slower and it pretended to transfer callers. See DECISIONS.
- Docker Hub rate-limits image pulls from this build environment; local images are layered from the last good build.

# Ondra

AI agents that answer every call, WhatsApp, text and email a car dealership gets, qualify the buyer, book appointments, and hand the right conversations to the right person on the team.

> Ondra is a working name.

## What it does

- **Answers every channel, 24/7.** Phone (voice agent), WhatsApp, SMS and email, with Instagram DMs later. Dealers keep their existing numbers and addresses; Ondra sits behind them through call forwarding, the official WhatsApp Cloud API and email forwarding or OAuth.
- **Qualifies buyers.** Vehicle, budget, destination, timeline and payment method are captured into a client profile automatically.
- **Books appointments.** Showroom visits, test drives, video walkarounds and service appointments, using appointment types each dealer configures, against real staff and service-bay capacity. One calendar is the source of truth, so nothing is double-booked.
- **Routes work to people.** Rules decide who gets what: sales, service, logistics, the owner. Every handoff carries a short brief and a deadline.
- **Protects VIPs.** VIP clients and their managers never talk to the AI. Their calls ring the owner directly and their messages wait for a personal reply.
- **Follows up.** Drafts follow-ups and reminders for approval, and learns from questions it couldn't answer.
- **Keeps the owner informed on WhatsApp.** A morning briefing, voice notes turned into tasks, and one-tap approvals.
- **Web dashboard.** Revenue dashboard, unified inbox with call recordings and transcripts, calendar, client profiles, task board and settings.

## Who it's for

US dealerships first, with a strong fit for dealers whose buyers use WhatsApp: exporters selling to Africa and the Middle East, and dealers serving immigrant communities. The first pilot customer is an independent luxury dealer in Dallas that exports to Nigeria.

## How it's different

Competitors such as Numa and Flai focus on US franchised dealers over phone, text and email. Ondra is WhatsApp-first, works for dealers with no DMS at all, handles cross-border buyers and time zones, and treats VIP clients as a first-class feature.

## Building it

The full architecture, data model, agent design, integrations, compliance requirements and build order are in **[BUILD_PLAN.md](BUILD_PLAN.md)**.

To build with Claude Code, open this repo and say:

> Read BUILD_PLAN.md fully. Build the system it describes, one build step at a time, in order. Stop at the end of each step, run the tests, and show me what you built against that step's acceptance criteria before moving on.

`CLAUDE.md` gives Claude Code the same instructions automatically.

### Stack (planned)

| Part | Technology |
|---|---|
| Core API | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Voice agent | LiveKit Agents + LiveKit SIP, Twilio or Telnyx |
| Background jobs | Postgres-backed job queue |
| Web dashboard | Next.js, TypeScript, Tailwind |
| Database | Postgres with pgvector and row-level security |
| AI | Anthropic Claude |
| Channels | WhatsApp Cloud API, Twilio SMS, Postmark or Gmail/Microsoft 365 email |

### Repo layout (planned)

```
apps/api       FastAPI app: domain logic, webhooks, routing, agent orchestration
apps/voice     LiveKit voice agent worker
apps/worker    background jobs
apps/web       Next.js dashboard
packages/core  shared models, tools, policies, adapter interfaces and mocks
evals/         golden conversations and the eval runner
infra/         docker compose, later terraform
docs/          DECISIONS.md, security docs, runbooks
design/        UI concepts: landing page and dashboard prototypes (see design/README.md)
```

The UI direction is in [design/README.md](design/README.md). Open `design/mockups/landing.html` and `design/mockups/app.html` in a browser to see the landing page concept and the dashboard screens.

## Before you write code

See section 16 of BUILD_PLAN.md: accounts to create (Anthropic, Twilio or Telnyx, LiveKit, Postmark, Meta Business Manager), Meta business verification and Tech Provider application, SMS sender registration (A2P 10DLC), and the pilot dealer's data. Some of these take weeks, so start them now.

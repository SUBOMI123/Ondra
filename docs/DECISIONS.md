# Decisions

## 2026-11-25: Marketing site as its own static app (`apps/site`)

**Decision:** The landing page is a separate Next.js static export in `apps/site`, not part of `apps/web`.
**Why:** It can ship now, before the API or the dashboard exist. It hosts free on any static host, and a marketing deploy can't break the product.
**Alternatives:** A route in `apps/web` (couples marketing deploys to the app and needs the app scaffolded first). A plain HTML file (fastest, but the copy and components would be rewritten later anyway).

## 2026-11-25: The 3D walk-through is a section, not the entry gate

**Decision:** The page opens with a normal hero (headline, sample WhatsApp conversation, Book a demo). The walk-through comes straight after it, because it continues the hero's "fully staffed" line. It is 480vh long and lazy-loaded.
**Why:** The mockup put 900vh of scroll-driven 3D and 600KB of inline three.js in front of the value proposition and the call to action. Dealers mostly open links on their phones from WhatsApp, and they need to see what it is and how to book in the first screen. The walk-through is still the memorable part, so it stays.
**Alternatives:** Keep the mockup's full-screen intro (worse load time, CTA nine screens down, weak on mobile). Drop the 3D entirely (loses the concept that makes the page distinctive).

## 2026-11-25: `ondra-ui` skill is the basis for all UI work

**Decision:** UI rules live in a project skill at `.claude/skills/ondra-ui/` (SKILL.md plus references for tokens, marketing, dashboard, components, AI and VIP rendering, copy and review). `CLAUDE.md` points to it.
**Why:** One place that every Claude Code session loads for UI work, distilled from a review of anthropics/skills, impeccable, shadcn/ui, Radix, cmdk, sonner, vaul, Tailwind v4, Magic UI, Tremor, Recharts, Tabler, Storybook, daisyUI and Mantine.
**Alternatives:** A design doc in `docs/` (not loaded automatically), or adopting Impeccable as-is (generic, and depends on its own CLI).

## 2026-11-25: Component stack for apps/web

**Decision:** shadcn/ui on **Radix** (`init -b radix`, unified `radix-ui` package), Tabler icons, shadcn Chart on Recharts 3, sonner, cmdk, vaul (pinned, mobile only). No daisyUI, Mantine or Tremor components. Storybook later.
**Why:** cmdk and vaul sit on Radix Dialog; Tabler has the WhatsApp and Instagram marks lucide lacks; Tremor Raw is still on React 18 and Recharts 2. daisyUI and Mantine bring competing theme systems.
**Alternatives:** Base UI (shadcn's default since July 2026; reconsider if vaul, which is unmaintained, becomes a problem).

## 2026-11-25: The walk-through is a photographic scroll tour with robot agents (supersedes the three.js floor)

**Decision:** Replace the real-time three.js scene with five photoreal stills on a sticky stage (`apps/site/components/FloorTour.tsx`): entrance, reception and WhatsApp, bookings and service, handoffs and follow-ups, the owner's office. The agents are humanoid robots. Labels are pinned to coordinates in each photo.
**Why:** The goal is for it to feel real. Real-time 3D can't get there on a phone: photoreal cars and characters need licensed models of 20-50MB each and a GPU budget dealers' phones don't have, and procedural models look like toys. Stills give photographic quality at about 150KB per scene, and the page dropped three.js (about 700KB of JS). Robots read as AI agents at a glance and keep the closing line ("None of them are people") true.
**Alternatives:** Licensed glTF cars and robots in three.js (heavy, still not photographic). A Blender render sequence scrubbed frame by frame (smoothest camera moves, needs a 3D artist and licensed assets; worth it once there's budget). Mannequins (tried, rejected by the founder as not real enough).

## 2026-11-25: Hero image is AI-generated for now

**Decision:** `apps/site/public/hero-showroom.jpg` and the floor tour scenes in `apps/site/public/floor/` were generated with Figma's image generator (no badges, plates or people; art direction in the `ondra-ui` skill, `references/marketing.md`). They are placeholders.
**Why:** Stock photo hosts are blocked from the build environment, and the page needed real atmosphere.
**Alternatives:** Replace with the pilot dealer's own showroom photographed at dusk, once we have written permission.

## 2026-11-24: Showroom cars are four free Blend Swap models, two of them not licensed for commercial use

**Decision:** The 3D floor loads four Blend Swap models from the founder's Desktop (`build_scene.py --cars`, loader in `design/3d/floor/cars.py`): 1968 Mustang GT Fastback (CC0), Audi A8 2010 by 50Groszy (CC-BY-SA 3.0), BMW M4 F82 (CC-BY 3.0, marked Fan Art) and Lamborghini Urus 2019 (CC-BY-NC 3.0). Badges, logos, plates and lettering are removed; the grille shapes of the BMW, Audi and Urus remain. Paint is recoloured black, silver and bronze.
**Why:** The founder confirmed all four after being told which licences were a problem. This gives four recognisable cars now, without the $50-300 per model for licensed production assets.
**Risk (open):** Only the Mustang is clearly cleared for commercial use. The BMW's page says Fan Art may not be used commercially "under any circumstance", and the Urus is NonCommercial. The Audi's licence file allows commercial use with credit but the author's readme asks for none, and share-alike may reach our modified model. A marketing page is commercial use. (Superseded 2026-11-25: the founder decided to ship them, see below.) Credit if shipped: Audi A8 by 50Groszy, BMW M4 and Lamborghini Urus by their Blend Swap authors (#81957, #92440), 1968 Mustang GT Fastback (#82339, no credit required).
**Alternatives:** Mustang only in three colours (clean licence, one car shape). Licensed models from CGTrader, TurboSquid or BlenderKit.

## 2026-11-25: Rebrand to "Night Shift": dark, Ondra blue, Funnel type

**Decision:** The brand moves from paper, ink and amber with Archivo Expanded to a dark-first palette (night `#06080B`, Ondra blue `#2F6CF6`, VIP red), set in Funnel Display, Funnel Sans and JetBrains Mono (free, OFL, self-hosted via fontsource). Ondra blue is both the brand and the colour of anything the AI did; in the dashboard, primary actions are neutral so blue keeps that meaning. The hero uses the first frame of the 3D walk instead of the generated photo.
**Why:** The founder found the old look AI-template-like (it sat close to the "warm cream editorial" cliché) and wanted it techy, futuristic, friendly and marketable. Dark reads as an AI product and matches the night render. The founder rejected mint and asked for blue, since Numa owns violet. Funnel's notched letterforms keep it out of the Inter-on-black look that Numa and most AI startups share.
**Alternatives:** Spruce and mint (light), Chrome and signal yellow, and Night Shift with mint. All three were shown on the direction board. Inter or Geist (rejected as the category default). Mona Sans (kept in reserve).

## 2026-11-25: Night-sky direction with Inter, frosted pills and Motion (supersedes Night Shift / Funnel)

**Decision:** Inter Variable (cv01, ss03) at light weights; a blue-black void with a twilight-navy sky over the 3D floor; frosted-white pill buttons; periwinkle for the AI, coral for VIPs. Motion (`motion`, formerly Framer Motion) for product UI that plays out on scroll (inbox thread), a CSS blur-in on the hero headline, and an animated channel-flow diagram. The `frontend-design` skill now sets design direction; `ondra-ui` keeps tokens and product rules.
**Why:** The founder found Funnel and the saturated blue still "very AI", pointed to Numa (Inter regular at large size, frosted pills, navy night sky) and Linear, and asked for Framer-quality motion. Measured Numa directly: Inter 400 at 56px, -0.04em tracking, white 80% pill buttons with dark text.
**Alternatives:** Build in Framer via its connector (not connected yet; code keeps the 3D walk and ownership). Funnel Display (rejected by the founder).

## 2026-11-25: Champagne palette and product stories in the middle of the page

**Decision:** The hero and grounds move from navy to a warm "champagne night": espresso grounds, a sodium-amber glow off the floor, champagne pill buttons. The AI stays a cool periwinkle. The WhatsApp, VIP, owner-briefing and guardrails sections became short product stories that play once on scroll (`components/stories.tsx`, `useStory`): a buyer in Lagos answered while Dallas sleeps, a VIP call ringing past the AI, the morning briefing approved by voice note, and a draft whose price and delivery promise are held back and rewritten.
**Why:** The founder found the navy hero and white pills too close to Numa. Flai owns oxblood and crimson. Warm champagne is unclaimed, matches the 3D render's amber light, and reads as luxury dealership. The static text blocks felt flat next to the animated inbox and diagram.
**Alternatives:** Petrol (teal night; its buttons went back to rejected mint), Graphite chrome (too close to Linear). Compared as rendered heroes.

## 2026-11-25: The public site sells by department, not by WhatsApp or Nigeria

**Decision:** The homepage drops every country, city and export reference and stops leading with WhatsApp. It sells by job, like Numa and Flai: one inbox, Sales (an after-hours text thread that books a test drive from real stock), Service (a live service call booking a bay), VIPs, the owner's morning, guardrails. WhatsApp stays as one of four channels, in the briefing and in the FAQ. The demo form asks about a DMS instead of overseas buyers.
**Why:** The founder wants the site to read as a product for any US dealer. The old page said WhatsApp 51 times and Lagos 16, which read as a niche tool. Phone calls, the biggest channel for dealers, had no story at all.
**Alternatives:** Keep the cross-border section on the homepage. Rejected for the homepage. The export wedge is still where competitors are weakest and where the pilot is, so it lives in outreach and a later dedicated page (see `docs/marketing/positioning.md`).

## 2026-11-25: Logo is a wordmark with a speedometer o

**Decision:** "ondra" in Inter 500 outlines, with the o drawn as an open speedometer: its ends rest on the baseline, its top overshoots like a round letter, and its needle is the AI blue. One version everywhere. A thicker-dial version is used for the favicon. Files are in `design/brand/`.
**Why:** The founder chose the speedometer. It reads as automotive at a glance and stays readable as an o when it is drawn to the letters' metrics.
**Alternatives:** Handoff o (two halves passing), Always-on ring, Open door, Aisle, plain wordmark. A detailed gauge with ticks and numbers was rejected as too busy; the numbers can't be read below about 120 px.

## 2026-11-25: Ship the walk with all four cars

**Decision:** The walk frames ship with the BMW, Urus and Audi as well as the Mustang. The site footer credits all four models and their licences.
**Why:** The founder's call, made knowing the licence terms. The cars make the floor feel real, and swapping them means a full re-render.
**Risk (accepted):** The Urus (CC BY-NC) and BMW (author forbids commercial use) are used commercially against their licences, and the Audi's share-alike terms may reach our modified model. The likely consequence is a takedown request to the host, and then the frames have to be swapped quickly. Mitigation: ask both authors for permission. If either refuses, re-render with the Mustang or a licensed model (keep `cars.py` able to do that).

## 2026-11-25: Hosting is Cloudflare plus managed services, no VPS to start

**Decision:**
- Cloudflare runs DNS, the WAF, the marketing site (Pages), the dashboard (Workers via OpenNext, with Vercel as the fallback) and file storage (R2).
- A managed Postgres (Neon or Supabase) holds the data.
- A container host in a US region (Fly.io or Render) runs `apps/api` and `apps/worker`.
- LiveKit Cloud runs SIP and the voice agent.
- The demo form posts to Formspree, which emails hello@useondra.com.

Full detail is in `docs/ARCHITECTURE.md`.

**Why:** The founder prefers Cloudflare. It fits the static and edge parts well, but not long-running Python services, real-time audio, or Postgres with RLS and pgvector. Managed services keep backups, patching and uptime off a small team while we hold dealers' customer data and call recordings.

**Alternatives:**
- One VPS (Hetzner) with Docker Compose: cheapest, but we would run all the operations ourselves.
- AWS or GCP throughout: right for later compliance needs, too heavy now.
- Everything on Cloudflare: its Python Workers can't run our FastAPI stack, and D1 has no RLS or pgvector.

## 2026-11-25: Dashboard has light and dark themes, chosen per user

**Decision:** `apps/web` ships light, dark and "Device" (follows the OS, the default), selectable in the user menu and saved per user. The sidebar is dark in both themes. In light the primary action is an espresso pill; in dark it is champagne. AI blue marks only what Ondra did, and is never used for actions, selection or focus. The reference is `design/prototypes/system.html`; tokens are in the `ondra-ui` skill (`references/dashboard.md`).
**Why:** The founder wants both. A light canvas reads better in bright showrooms and on long shifts; dark matches the brand and evening use. The who-did-it column in threads is the signature, so blue has to keep one meaning.
**Alternatives:** Light only with a dark sidebar (simpler, but loses the brand's dark side). Dark only, matching the marketing site (harder to read in daylight).

## 2026-11-25: The dashboard is built on shadcn's dashboard template

**Decision:** `apps/web` starts from shadcn/ui's `dashboard-01` block (sidebar, metric cards, interactive area chart, sortable data table, row drawer) and its new-york-v4 components, on shadcn's neutral theme in light, dark and Device. Ondra's layer on top: the AI blue marks only Ondra's work (chart series, "Ondra" and "Draft for you" badges, briefs), red marks VIPs, and the speedometer wordmark sits in the sidebar. This replaces the custom design in `design/prototypes/system.html` (D0), which stays in the repo as a record.
**Why:** The founder didn't like the custom dashboard and wants the techy shadcn look. It also matches the planned component stack, so the approved screens are production code from day one.
**Alternatives:** Keep iterating on the custom system (rejected by the founder). Tremor or Mantine templates (off the planned stack).

## 2026-11-25: Step 1 foundations: how tenant isolation, auth and the schema work

**Tenant isolation.** Every tenant-scoped table has row-level security enabled and FORCED, with one policy: `tenant_id = app_current_tenant()`, which reads `app.tenant_id` set with `set_config(..., true)` (transaction-local) at the start of each request's transaction. With no tenant set, nothing is visible. The API connects as `ondra_app` (no superuser, no BYPASSRLS); migrations and the seed run as the owner. A test asserts every table with a `tenant_id` column has forced RLS, so a new table can't silently skip it. Removing RLS from one table makes 10 of 17 tests fail (checked).
*Why:* isolation enforced by the database survives a forgotten `WHERE`. *Alternatives:* filtering in the ORM only (one bug leaks data); a schema or database per tenant (heavier migrations, harder analytics).

**Signing in before the tenant is known.** One `SECURITY DEFINER` function, `auth_find_user(email)`, returns only what sign-in needs. User emails are unique across all tenants. Refresh tokens are `<tenant id>.<random>`, so refresh runs inside that tenant's RLS scope with no cross-tenant lookup.

**Auth.** Argon2 password hashes; 15-minute HS256 access tokens held in memory by the dashboard; 7-day refresh sessions stored as SHA-256 hashes, rotated on every use, sent as an httpOnly SameSite=Lax cookie scoped to `/auth`. The role is read from the database on every request, so deactivating a user or changing a role applies immediately. Wrong password and unknown email give the same answer and take the same time.
*Deferred:* MFA (BUILD_PLAN §10) lands with hardening in Step 10. Single sign-on later.

**Schema conventions.** Status fields are text with CHECK constraints instead of Postgres enums (adding a value is a one-line migration). `knowledge_docs.embedding` is a `vector` with no fixed dimension until the embedding model is chosen in Step 2, when an index is added. `tenant_id` defaults to the transaction's tenant, so inserts can't forget it.

**MinIO is opt-in for now.** Nothing in Step 1 stores files. Docker Hub's `minio/minio` repository no longer exists, so compose uses `quay.io/minio/minio` behind `--profile storage`. It becomes default when Step 2 starts storing attachments.

## 2026-11-26: Golden conversations start synthetic

**Decision:** The first 22 golden conversations (`evals/golden/`) are hand-written and marked `synthetic: true`, generated from `evals/build_golden.py` so they share inventory and policy fixtures. Each turn states what must and must not happen in a fixed vocabulary of checks (`evals/README.md`). VIP and opted-out cases assert the AI is never invoked: the policy layer stops them first. A schema test keeps every file valid and enforces that rule.
**Why:** There is no pilot dealer data yet, and Step 2 needs 20 scenarios to build against. Writing them messy (typos, two intents in one text, injection attempts) reduces, but does not remove, the risk of evals that only reflect our assumptions.
**Next:** Replace and extend with real conversations: mystery-shop local dealers after hours, then the pilot dealer's exports with names and numbers stripped. Two open items are flagged inside the scenarios: whether to disclose the AI up front or only when asked (015), and whether replying to a new inbound question after STOP is allowed (009, needs counsel).

## 2026-11-26: Step 2: channel gateway, policy layer and text agent

**Product rules live in code, before and after the model.** `ondra_core.agent.policy.evaluate_inbound` runs before any model call. STOP (and plain-language "stop texting me") opts the contact out on every channel and purpose. VIPs get no AI reply or draft, and the owner (or the VIP's handler) gets a high-urgency task plus an `alert.created` event. An opted-out contact who writes in gets nothing automated, and a person is told. A second gate, `may_send_outbound`, re-reads consent and VIP status after the model finishes, in case STOP arrived mid-turn. After the model, `detectors.review_reply` blocks final prices, discounts, date promises, trade-in values, financing guarantees, leaked instructions and cars the tools never returned. A blocked draft is rewritten once, with a mid-conversation system note; if it fails again, a safe "I've passed this to…" reply goes out and a person gets a task. With price policy `none`, the model never sees prices at all.
*Why:* a prompt is a request, not a guarantee. These rules must hold whatever the model does. Mutation-checked: removing the VIP rule fails 3 tests, and removing idempotency fails 1.
*Alternatives:* an LLM judge as the guard (slower and non-deterministic; it may be added later as a second layer for tone checks).

**Tenant from the receiving address.** Inbound webhooks arrive before a tenant is known. `channel_addresses` (RLS-scoped, unique per channel and address) maps the dealer's own number or email to the tenant, and is read through one `SECURITY DEFINER` function, `channel_find_tenant`. Revision 0002's table list is now frozen, so later tables get RLS in their own migration.

**Idempotency.** Messages are inserted with `ON CONFLICT DO NOTHING` on (tenant, provider, provider_message_id); a duplicate webhook stores nothing and runs nothing. Meta retries for up to 36 hours and Postmark 10 times, so this matters.

**Draft mode is dealer-wide.** It is `policies.draft_mode`, the default for the first week. `conversations.ai_mode` is a per-conversation override (`auto` follows the dealer, `draft` forces drafts, `off` disables the AI). New conversations start at `auto`.

**The AI turn runs after the webhook answers**, as a FastAPI background task. It is not yet on a durable queue: if the API restarts mid-turn, that one reply is lost (the inbound message is stored either way). It moves to the worker in Step 3, together with SLA timers. A burst of messages is answered once: a run that sees a newer inbound message skips, and the newest one's run answers all of them.

**Models.** Conversations use `claude-sonnet-5-5`, as in BUILD_PLAN.md §6.1. It runs with adaptive thinking at `low` effort for latency, `auto` tool choice (current models reject forced tool choice), server-side refusal fallback (`fallbacks: "default"`), and the stable system-prompt block marked for caching. The base URL is set explicitly, so a shell `ANTHROPIC_BASE_URL` can't redirect production traffic.

**Knowledge search is Postgres full-text for now**, OR-ing the query's words and ranking with `ts_rank`. Embeddings (pgvector) wait until an embedding provider is chosen. Anthropic has no embeddings API, so this needs a new vendor, which is a founder decision. The tool interface doesn't change when it lands.

**Provider details were checked against the official docs on 2026-11-26.** WhatsApp: `X-Hub-Signature-256`, the `hub.*` handshake, the webhook shape and v27.0 send. Twilio: the signature algorithm, verified against the docs' worked example in a test, the webhook params, and Advanced Opt-Out behaviour. Postmark: the inbound fields; it has no HMAC signatures, so Basic auth is used. Unconfirmed details are marked `TODO(verify)` in code:
- WhatsApp's HMAC and hex encoding, which the docs imply but don't state.
- Twilio API-key versus auth-token send auth, and its newer shared-key signing.
- Postmark In-Reply-To through custom headers.
- WhatsApp usernames: users who hide their phone number arrive with only a BSUID. That is stored as their WhatsApp identity for now.

**Opt back in.** START or UNSTOP re-subscribes every channel the STOP covered (Twilio: "YES" does not). `TODO(verify, counsel)`: per-channel rules.

## 2026-11-26: Ondra says it's an AI when asked

**Decision:** Ondra tells customers it's the dealership's AI assistant whenever they ask, and offers to get a person. It never says or implies it's human. It doesn't announce itself in every conversation by default. A per-dealer setting, `tenants.settings.ai_disclosure = "upfront"`, makes it say so in its first reply, for states that require that. The settings UI for this switch arrives with Step 6.
**Why:** It's the founder's call. Up-front disclosure on every text adds friction to the short after-hours replies that are the product's core.
**Risk to check with counsel before launch:** California's bot-disclosure law (the B.O.T. Act, SB 1001) requires disclosure, as we understand it, when a bot is used to encourage a sale to people in California, whether or not they ask. Other states are adding AI-disclosure rules. Check which states pilot dealers sell into, and turn on up-front disclosure there. TODO(verify, counsel).
**Alternatives:** always up front (safest legally, more friction); never (not an option).

## 2026-11-26: Out-of-stock requests always go to sales

**Decision:** When a customer wants a car the dealer doesn't have, Ondra says so plainly and offers what's in stock. It also always hands the request to sales at low urgency (reason `vehicle_request`), so they can try to find one.
**Why:** It's the founder's call. A buyer asking for a specific car is a lead, and dealers can source cars from other dealers or at auction.
**Watch:** low-urgency tasks could pile up. If they do, Step 6's routing rules can batch them into a daily list instead of one task each.

## 2026-11-26: Knowledge search uses Voyage AI embeddings

**Decision:** Knowledge answers are embedded with Voyage AI (`voyage-4` for the dealer's answers, the faster `voyage-4-lite` for customer questions; the voyage-4 series is documented as mutually compatible) at 1024 dimensions. They're stored in `knowledge_docs.embedding` with an HNSW cosine index, and `embedding_space` records which embedder made each vector, so the mock's vectors and Voyage's are never compared. Search returns the top 3 answers at or above a similarity of 0.38. Below that, the AI treats the question as unanswered and hands off. If embedding fails (outage, rate limit) or nothing is embedded yet, search falls back to Postgres full-text. Without a key, a deterministic local mock embedder keeps everything running.
**Why:** It's the founder's choice, and Anthropic points people to Voyage for embeddings. Word matching missed paraphrases and other languages. Measured on the seed answers: "¿abren los domingos?" matches Opening hours at 0.46, which keyword search can't do. Relevant matches scored 0.42 to 0.53, unrelated questions 0.10 to 0.33, hence 0.38. Re-measure when real dealer answers arrive.
**Operational:** without a payment method, a Voyage account is limited to 3 requests a minute (seen as 429s during setup), so production needs billing enabled. The seed survives an embedding failure, and `python -m ondra_api.services.knowledge` backfills later.
**Alternatives:** OpenAI or Cohere embeddings (another vendor with no advantage here); full-text only (fails on Spanish and paraphrase).

## 2026-11-26: Settings are real, and owners and admins manage the team

**Decision:** Settings now read from and save to the API. That covers:
- business name, time zone and opening hours, which the agent uses for "open now";
- the reply rules: draft mode, price sharing, handoff topics and AI disclosure;
- the dealer's channel addresses: connect, switch off, disconnect.

Anyone signed in can read Settings; only owners and admins (`settings:manage`) can change them, and other roles see a read-only page. Every change writes an `audit_log` row with before and after.

Team management (`users:manage`): invite, change role, deactivate or reactivate. The rules:
- Only an owner can create, change or deactivate an owner.
- Nobody changes their own role or access.
- A dealership keeps at least one active owner.
- Deactivating someone revokes their sessions at once.
- People are deactivated, never deleted, so the audit trail keeps pointing at them.

**Invites:** a one-time link (`<tenant>.<random>`, stored as a SHA-256 hash, valid 7 days) lets the new teammate set a password of 12 or more characters. Until outbound transactional email is set up, the link is shown once to the person who created the invite, to send themselves. The Settings page says so plainly.

**Channels are honest about their state.** A channel says "Test mode" when its provider isn't live (messages are simulated), "Live" when it is. Phone forwarding arrives with voice (Step 5). Real provider onboarding (Meta Embedded Signup, Twilio numbers) is Step 11.

**Why now, not Step 6:** the founder rejected a settings page that didn't save. A settings screen that looks editable but isn't is worse than none. Routing rules, quiet hours and the knowledge base answers stay in Step 6.

## 2026-11-26: How reply latency was brought under 5 seconds

**Measured first:** per-call timing showed the AI already ran its lookups in parallel. The time went into extra rounds: lookups, then `handoff`, then the reply, three model calls at about 1 to 2 s each.
**Changes:**
- The customer's record is preloaded into the prompt, which saves a lookup round.
- The prompt and the `handoff` tool description ask for the handoff to be made in the same round as the lookups when a person is clearly needed.
- If a response calls only `handoff` or `update_lead_fields` and includes the reply text, that text is checked and used without another model call. The model rarely does this today, but the path is tested and costs nothing.

**Result** over 100 model turns: median 3.2 s, p90 4.6 s, and one email reply at 5.6 s. Quality held: 110 of 110 conversations passed.
**Not done:** a faster model for the final reply-writing round. That would change the plan's model choice (§6.1), so it's the founder's call. Revisit if voice needs it.

## 2026-11-26: Background work runs on a job queue in Postgres

**Decision:** durable jobs live in a `jobs` table: RLS-scoped, claimed across tenants by the `SECURITY DEFINER` function `jobs_claim` with `FOR UPDATE SKIP LOCKED` and a 120 s lease. The worker is `python -m ondra_api.worker`, the API image with a different command, run as the `worker` compose service.
- **The AI turn is a job.** It's queued in the same transaction that stores the inbound message, so a stored message always has its turn queued.
- **Retries:** failed jobs retry with exponential backoff (10 s, 20 s, 40 s…) up to `max_attempts`, then stay `failed` with the error kept. A job stuck in `running` past its lease (a crashed worker) is claimed again.
- **Escalation:** every 60 s the worker sweeps for overdue tasks.

**Deadlines:** high urgency 15 min, normal 2 h, low 8 open hours (about one working day), counted only in the dealer's opening hours, so overnight leads don't escalate at 1 am. An overdue task escalates once: urgency becomes high, and it goes to a manager, or to the owner if a manager already had it. Both a `task.escalated` and an `alert.created` event are recorded.
**Why:** the plan calls for a worker (`apps/worker` in §13) but names no queue. Postgres needs no new infrastructure, and RLS covers jobs like any other dealer data. The worker lives in the API package because every job reuses API services; a separate `apps/worker` package would only re-export them.
**Alternatives:** Redis with RQ or Celery (new infrastructure to run and secure); a cloud queue (ties local dev to an account).
**Known limit:** if a worker crashes after the provider accepted a send but before the job is marked done, the retry can send that reply twice. Fix with an idempotency key per outbound message when real providers go live.

## 2026-11-26: Step 3 choices: inbox views, one send path, live updates

- **Inbox views come from data, not a status column.**
  - *Needs you:* a VIP whose last message was inbound, a waiting AI draft, an open task, or `waiting_staff`.
  - *Ondra handled:* the last word was Ondra's.
  - *With the team:* everything else.

  The reason is shown in words. Computing this keeps it from drifting out of sync with the facts.
- **One send path** (`services/outbound.deliver`) for Ondra, approved drafts and staff replies. It re-checks the opt-out and VIP gate right before sending, so no route can skip it. A staff reply replaces any waiting AI draft.
- **Draft edits are recorded** as `draft.edited` events (before and after) for the learning loop (§6.3a). Approving credits the approver on the message, and the author stays the AI.
- **Live updates** use Postgres NOTIFY from triggers (ids only), one listener per API process, and server-sent events per dealer. The dashboard reads the stream with `fetch`, so the token stays in a header, not the URL. Changes in a burst refresh once.
- **Effects never return values.** A `useEffect(() => el.scrollIntoView())` returned a Promise in newer Chromium, and React crashed calling it as cleanup. Every effect now has a block body, and `npm run review:ui` fails any that doesn't.
- **The seed has five example conversations,** one per state the Inbox shows (VIP waiting, draft, overdue handoff, handled by Ondra, opted out), so a fresh `docker compose up` can be demoed.

## 2026-11-26: Booking: Postgres refuses double-booking; slots are offered, not invented

- **No double-booking is enforced by the database.** `appointments` has an exclusion constraint: no two live appointments for the same person may overlap from start to `blocks_until` (end plus buffer). `appointment_resources` has the same rule per bay or loaner. Bookings run in a savepoint; the loser of a race gets `SlotTaken`. The test of five simultaneous bookings for one slot fails without the constraint, so it is what does the work. This needs Postgres's `btree_gist` extension, which ships with Postgres and is available on Neon, Supabase and RDS.
- **The AI books only what the calendar offered.** `check_availability` returns opaque slot IDs (type, start, person, resources). `book_appointment` takes only an ID, and the server re-checks hours, notice, eligibility and resource kinds before booking. A time the model invents is refused.
- **Availability** comes from `InternalCalendar` behind the `AvailabilityProvider` interface (§4.3). Slots are on a 30-minute grid inside the type's hours, or the dealer's hours if the type has none. The type sets duration, buffer, minimum notice and how far ahead. The slot goes to the free eligible person with the fewest appointments that day, and takes the first free resource of each required kind. Google/Microsoft calendars and DMS schedulers plug in behind the same interface. Resources are treated as capacity 1 for now.
- **Loaners** are held if one is free; otherwise the appointment notes that the service team will arrange transport.
- **Reminders:** jobs at 24 h and 2 h before (per type), only between 8 am and 8 pm dealer time. One that would fall earlier moves to 7 pm the evening before; one that would fall later moves to just before 8 pm. A reminder that would land in the past is skipped. Each job re-checks status, time and whether it was already sent, and sends through the one outbound path, so opt-outs block reminders too.
- **Seeded types** come from templates: test drive, showroom visit, trade-in appraisal, oil change, service and repairs, vehicle delivery. Service types use service hours (7 am to 6 pm weekdays, 8 am to 2 pm Saturday). Plus three bays and two loaners.

## 2026-11-26: Calls: routing is decided before anyone speaks; missed-call texts need recorded consent

- **`start_call` runs the moment a call arrives, before the AI says a word.** It finds the dealer from the dialled number (`channel_find_tenant('phone', ...)`), finds or creates the caller, and opens the call record. The provider's call ID is unique per dealer, so a retried webhook gives the same call, not a second one. Then it picks the route:
  - a VIP rings the owner, or the VIP's assigned person if they're active, and the AI never answers;
  - voice AI switched off for the dealer, or a conversation a person has taken over, rings the team;
  - otherwise the AI answers.
  The voice worker follows the route; it doesn't make the decision. Alternative rejected: let the voice agent check VIP status itself. That puts a product rule in a second place where it can drift.
- **A missed call is texted back only if the caller has recorded consent to texts.** That means the latest SMS transactional consent is `opted_in`, with no opt-out on any channel. Without it, no text: a `call.text_back_skipped` event and a call-back task for a person. "They just called us" is not recorded consent, and CLAUDE.md forbids automated texts without it. This means most first-time callers get no text-back. Counsel may decide a reply to a missed call is allowed (it's commonly argued as customer-initiated), and changing it is one function (`_has_text_consent`). Added to the founder list.
- **A missed VIP call** creates a high-urgency task for the owner and an owner alert. It never sends an automated text.
- **Summaries** come from the fast model after the call, as a job, and never for VIP calls. Recordings are kept only when the caller consented. Per-turn latency goes in `calls.metrics` for the latency report.

## 2026-11-26: Voice: LiveKit's own agent pattern, one agent, every sentence checked before it's spoken

- **Built the way LiveKit's examples build agents** (`examples/homepage/vehicle-service`, `warm-transfer`): a thin
  `Agent`, a per-call "desk" that holds the rules, LiveKit's model and tool loop, its turn detector, adaptive
  interruptions and preemptive generation. Alternative rejected: override `llm_node` to run our text orchestrator
  (`run_turn`). That checks a whole reply before sending, so the caller would hear nothing until the full reply was
  written, and it discards LiveKit's streaming and tool loop.
- **The tools are the text agent's own** (`TOOL_SPECS` registered as raw-schema LiveKit tools, run through
  `run_tool` on `DbToolBackend`), so a booking, handoff or price works the same on every channel. Each tool call
  opens its own short transaction; a call never holds one open.
- **Every spoken sentence passes the text checks first** (`ondra_voice.guard`, in `llm_node`). It holds text only
  until a sentence ends, which the voice needs anyway. A failing sentence is replaced with "one of our team needs to
  go over that with you", and a call-back task is created so that promise is true.
- **Prices are written as digits ($27,600), not words.** The price check reads digits; with prices in words it
  couldn't catch a made-up price on a call. The voice reads digits aloud. TODO(verify) how each voice reads them in
  the 5e bake-off.
- **One agent, not the plan's receptionist routing to sales and service (§4.2 step 4).** Measured on the real model:
  each switch was a full extra model round (about 2.5 s more silence), and the receptionist announced it as if
  transferring the caller ("You're being put through to our sales team now"). The plan's reason was letting
  callers change topic mid-call; one agent with all ten tools did that (car questions, then a service slot) with no
  switch. Revisit if the tool list grows past what one prompt handles well.
- **LiveKit quirk:** its Anthropic formatting sends a tool result that's a JSON array as content blocks, which the
  API rejects. List results are wrapped (`{"results": [...]}`).
- **Voice model: measured, not yet decided.** Time to first token on the same four-turn call: the plan's
  conversation model 1.3 to 3.5 s; the fast model 1.1 to 2.6 s. Both behaved correctly (listed prices only,
  discount refused and handed off). Neither meets the plan's under-1-second target, and a real call adds speech
  recognition and voice time. **Decided (founder, 2026-11-26): calls use the fast model** (`MODEL_FAST`;
  `VOICE_LLM_MODEL` overrides). Text keeps the plan's conversation model. Re-check with the 5e real-call measurements.

## 2026-11-26: Calls on screen: call-backs first, phone threads have no text box

- **The Calls screen leads with who to call back**, each saying why in words, including why no text went out
  ("No text sent: they opted out of texts"), so the consent rule is visible, not mysterious. The primary action is
  "Call them back" (the phone's dialler), plus "Mark as called back".
- **No Listen, Take the call or Play buttons until they work** (no dead ends). Listening in and taking over a live
  call need LiveKit room access from the browser; playback needs recording (Egress, with consent). Both are 5e or later.
- **A phone thread in the Inbox has no reply box:** a phone line can't send texts. It offers "Call them" instead.
- **A call counts as live for at most 2 hours.** If the voice worker dies mid-call, the record would otherwise say
  "on a call now" forever.
- **The Inbox orders by the latest message or call,** and a phone thread's preview is its latest call in words.

## 2026-11-26: The Inbox shows one thread per client, across channels

- **Storage stays one conversation per channel** (each channel has its own delivery rules: the WhatsApp 24-hour
  window, email threading, a phone line that can't text). **The Inbox shows one thread per client** on top: the
  list has one row per client with their most urgent reason (VIP waiting, then a draft, then an overdue task, a
  task, waiting for the team) and their latest activity on any channel; the thread merges messages and calls from
  every channel in time order, each labelled with its channel.
- **Replies go where the client last wrote** (never the phone line), with a channel picker when there's more than one.
- **Take over, hand back and assign apply to the client on every channel.** Someone handling Jordan by text must not
  find Ondra answering Jordan's WhatsApp. Alternative rejected: merging conversations in the database, which loses
  per-channel delivery state and would need a migration of every message.

## 2026-11-26: Clerk for sign-in; Ondra keeps roles, permissions and tenant isolation

- **Clerk proves who someone is** (sign-in, two-step sign-in, invitation emails, sessions). **Ondra decides what they
  may do**: roles, VIP visibility and every permission check stay in Ondra's database and API, and Postgres row-level
  security is unchanged. Alternative rejected: Clerk Organization roles as the source of truth. One wrong role in
  Clerk's dashboard could expose VIPs, and the rules would live in two places.
- **A dealership is a Clerk Organization** (`tenants.clerk_org_id`); a person is linked to their Clerk user
  (`users.clerk_user_id`) on their first sign-in after accepting an invitation, by their verified email.
- **The API verifies Clerk session tokens** (RS256, key from `CLERK_JWT_KEY` or Clerk's JWKS, `azp` checked against
  `CLERK_AUTHORIZED_PARTIES`, unfinished sessions refused) and maps the active Organization to a dealership through
  `tenant_for_clerk_org()`, a narrow SECURITY DEFINER lookup like the existing sign-in one.
- **Two-step sign-in for owners and admins only, enforced by Ondra.** Clerk's own setting requires it for every
  user. Ondra reads the token's `fva` claim: an owner or admin without a verified second factor gets 403
  (`mfa_required`) everywhere except `/me`, and the dashboard shows the setup screen. MFA needs a paid Clerk plan in
  production.
- **MFA means set up and used.** Found in the end-to-end test: Clerk's one-time email code for a new device also
  shows as a verified second factor in `fva` (an owner with no MFA set up got `fva: [0,0]` and walked in). So an
  owner or admin needs two-step sign-in set up on their Clerk account (`two_factor_enabled`, read from Clerk's API,
  cached a minute) and a second factor used in the session.
- **Invite-only.** Team invites are Clerk Organization invitations (Clerk sends the email); deactivating someone
  removes their Organization membership and Ondra refuses them at once. Ondra's own password sign-in is switched
  off when `AUTH_PROVIDER=clerk`, so nobody can skip Clerk's two-step sign-in with an old password.
- **Local sign-in stays** as the no-account mode for `docker compose up` and tests (CLAUDE.md: every external service
  has a mock). Clerk is loaded in the web app only when `NEXT_PUBLIC_AUTH_PROVIDER=clerk`.
- **Not yet:** Clerk webhooks (user deleted in Clerk's dashboard) need a public URL, so they come with hosting; until
  then Ondra checks membership on every request.

## 2026-11-26: Team is its own page, searched and paged on the server

- **Settings shows a summary of the team** (people by role, invitations waiting) with "Manage the team" and
  "Invite teammate". **The Team page (/settings/team) is where people are managed**: search by name, email or
  mobile (formatted numbers work: "(214) 555-0102" finds +12145550102), status tabs (active, invited,
  deactivated) with counts, a role filter, and 25 per page. The API does the searching, filtering and paging
  (`GET /users?q=&role=&status=&limit=&offset=`, with whole-team counts), so a 100-person dealership loads 25
  rows, not 100. Checked with 116 people.
- **Roles are Ondra's.** Clerk's own roles (admin, member) only mirror them for Clerk's screens: owner and admin are
  Clerk admins, everyone else a member. No custom roles in Clerk.

## 2026-11-26: Voice latency: no thinking, low effort, short slot names, a filler

First real booking call: 3.5 s average wait, 5 s worst; the voice started in 0.15 s, so the time was the model.
- **Claude Haiku 5.5 thinks by default at medium effort**, and the voice path (LiveKit's Anthropic plugin) never
  said otherwise. Measured on the booking conversation, back to back, 16 to 17 replies each, every booking right:
  default (thinking on, medium) median 1.32 s to first word, p90 1.95 s, 6 replies over 1.5 s; **thinking off at low
  effort median 0.61 s, p90 0.76 s, none over 1.5 s**. Now the voice default (`VOICE_THINKING=off`,
  `VOICE_EFFORT=low`; thinking off is allowed at effort high or below). Text replies keep adaptive thinking.
- **Short slot names on calls.** The calendar's slot ids are about 200 characters; writing one out before booking
  was most of the booking turn. The voice agent shows the model `slot1`, `slot2`... and maps them back: the booking
  turn went from about 1.85 s to 1.36 s.
- **A filler:** if the model calls a lookup or booking tool without saying anything, Ondra says "One moment."
- **Model response times vary by hour** (the same settings measured 0.6 s and 1.2 s median at different times), so
  the latency report from real calls is what counts. Next levers if it's still slow: a shorter prompt for calls, and
  ending the caller's turn sooner (endpointing).
- **Booking results say what the transport choice means** ("They leave their car with us and drive Loaner 1"),
  after Ondra said "a loaner while you wait" on a call.

## 2026-11-26: On calls, name the best two cars and text the rest (with the caller's yes)

- **Real calls:** four cars and prices read aloud were hard to follow, and the instruction "mention one or two"
  didn't hold twice. Now the stock lookup itself, on calls only, hands the model the best two (the cheapest, and
  the newest if different) plus how many it found, with a note to ask one narrowing question and offer the rest by
  text. Every price found still counts as real for the spoken checks.
- **`text_details`** (calls only) texts the cars from the last search to the number the caller is calling from.
  Only after they ask for a text or say yes to the offer: the code checks the caller's last words for a yes, and
  records it as consent (`consents`: source `voice_call`, the call id and their words), because CLAUDE.md forbids
  automated texts without recorded consent. The text goes through the one send path, so opt-outs and VIP status
  are re-checked. Counsel question: is a recorded spoken yes on a call enough consent for a one-off text the caller
  asked for (TCPA)? Real delivery from the dealer's number also needs A2P 10DLC registration.
- **Rejected:** keeping the caller on the line while they read the text. Someone with a phone at their ear can't
  read a text; it makes dead air. The call carries on by voice, and the text continues in the same Inbox thread.
- **Delivery-date check** no longer fires on "on" without a date after it ("Done, both are on their way to your
  phone" was replaced on a call); "ready on Friday", "by next week" still are.

## 2026-11-26: Call voice is Cartesia Sonic 3.6, "Jacqueline"

- **How it was chosen:** a blind test. Six voices read the same four Ondra lines (greeting, two cars with prices,
  a booking confirmation, the discount refusal), cut to phone quality (300-3400 Hz, 8 kHz, mu-law), labelled A-F
  at random. The founder liked Rime Coda "astra" and Cartesia Sonic 3.6 "Jacqueline", and picked Jacqueline.
- **Numbers matter more than tone:** speech recognition run over each sample found that ElevenLabs Flash v2.5 (the
  voice used on the first real calls) read "$25,100" as "twenty five hundred dollars" and "$21,400" as "twenty one
  nine four hundred", and ElevenLabs Turbo v2.5 dropped words from prices and mangled "Bay 1". A wrong spoken price
  breaks the price rule as surely as a made-up one. Cartesia, Rime, Inworld and Deepgram read them all right.
- **Speed was not the decider:** first audio of a reply was 0.4-1.2 s on the first sentence (a new connection)
  and 85-175 ms after that for all six; the waits on calls come from the model and lookups.
- **Alternatives:** Rime Coda "astra" (close second, fastest after the first sentence); keep ElevenLabs with text
  normalisation on (slower, and it already misread). Both stay one env change away (`VOICE_TTS_*`).
- **Still to do:** the spoken style of the instructions (short sentences, one fact each) is the bigger change to
  how human the call sounds; and a guard test for how each voice reads prices belongs in the 5e voice test set.

## 2026-11-27: Voice instructions rewritten for speech; what the model is handed is shaped for speech too

- **Why:** the founder found calls "very much AI". Three scripted calls against the real call model (text mode: a
  buyer, a service booking, a vague caller) showed it: 62-word replies, a car, mileage and price in one sentence,
  "Thanks for calling Prestige Motors" said mid-call after every handoff, the same thing said twice.
- **The rules** (`VOICE_RULES` in `apps/voice/src/ondra_voice/agents.py`) now say how to sound, with the reason for
  each: answer in the first words; one piece of information per sentence; a car is year, model and price, with
  mileage and trim only when asked; say each thing once; no call-centre phrases; at most two times offered;
  goodbye only when the caller is done. Prices stay exact and in digits (the spoken checks need them); only
  mileage may be rounded.
- **Measured on the same three calls, before and after:** average reply 21.7 -> 15 words, longest reply 62 -> 31-35,
  sentences over 18 words 9 -> 2, sentences replaced by the safe line 3 -> 0, mid-call goodbyes several -> 0. Two
  runs after; text mode, so no audio or timing.
- **Instructions alone weren't enough, so the data helps:** on calls the stock result's note says "year, model and
  price, nothing else"; staff come back as first names; slot names carry the time (below).
- **Bugs the test calls found, fixed:**
  - "Three works" (three o'clock) booked the third slot, 1 pm, because the model saw `slot1, slot2, slot3`.
    Slot names now carry the day and time (`fri-2pm`, `sat-9am`).
  - The caller's own budget or ask said back ("under $30,000" after "under thirty grand"; "about the $500" after
    "five hundred off") was replaced by the safe line: the check only knew amounts written in digits.
    `spoken_amounts` reads amounts as callers say them, for the customer's words only.
- **Not done:** rounding prices ("about 25 grand") was considered and rejected: a rounded price is a wrong price,
  and the checks compare exact amounts. Still imperfect after the rewrite: it sometimes tells the caller about
  the handoff both before and after doing it, and now and then says "is there anything else I can help with".

## 2026-11-27: After the first two calls on the new voice

- **"Thursday at 3" said on Thursday evening** got "Nothing's open Thursday afternoon". When the day asked for is
  today and nothing is left, `check_availability` now says it's today and already past, and gives next week's date
  to check if that's what they meant.
- **Best two only above three cars.** "We have three" followed by two names and an offer to text all three sounded
  odd; with short spoken descriptions three are easy to follow.
- **Two times offered, "yeah, that works":** Ondra picked the first. The rules now say to ask which. Also: no
  apology when simply asking the caller to repeat something.
- **Where the wait goes is now recorded per turn.** The call record had the model's first word and the voice's
  start, which added up to about 1.2 s of turns that took 3.4-3.8 s. It now also keeps `end_of_turn_ms` (how long
  LiveKit waited to be sure the caller had finished), `transcription_ms` and `tool_ms`, with averages in the
  summary. Nothing was tuned: the end-of-turn wait gets changed after it's measured on a call, not before.
- **The text on the call went to the mock.** Real texts need `FEATURE_SMS=true`, the Twilio Account SID and Auth
  Token (the adapter signs webhooks with it; the API key pair used for the phone line isn't enough), and A2P 10DLC
  registration, without which US carriers drop the messages.

## 2026-11-27: Routing engine (Step 6a)

- **Order of decisions:** VIP first (owner or the VIP's handler; a product rule in code, no dealer rule can
  reorder it), then the dealer's rules by priority (first match wins), then the topic's usual team. Within the
  team: someone on shift and under their limit, whoever was given work least recently. Rules live in
  `ondra_core.routing` as plain functions; `services/routing.py` loads rules and people and records every decision
  as a `routing.decided` event (which rule, who, why), so "why did this come to me" has an answer.
- **First match wins, not "all matching rules apply":** a dealer can read the list top to bottom and know what
  happens. Alternative (merge every matching rule's actions) is more flexible and much harder to predict.
- **A customer keeps one contact.** The first handoff assigns the conversation; later handoffs go to the same
  person if they're on the routed team and in. Not assigned on the first message: most messages the AI answers
  alone, and giving each one a rep would burn round-robin turns on "what time do you close".
- **Shifts are per person, in their own timezone** (`users.work_hours`, `users.timezone`; null means the
  dealership's hours), so Lagos staff can cover a Dallas night. Nobody in the team on shift: it queues for whoever
  is in next rather than bouncing to a manager, and the AI's prompt now says per team who is in ("sales: in now;
  service: nobody in until Mon 8:00 am"), because "shortly" was decided from dealership opening hours alone.
- **At capacity** (`users.max_open_tasks`): skipped while anyone else is free; if everyone is full the least
  loaded takes it. Work is never left unassigned because of a limit.
- **Topic** (sales, service, shipping, finance, complaint, other) is classified by the fast model before the AI
  runs, with thinking off and a 20-token cap: 8 of 8 on a spot check including a prompt-injection attempt and a
  Spanish message, 300 to 1,100 ms (most near 300). That is added to every text reply. Fallback when there's no
  key or the call fails: the words used. A handoff's topic comes from its reason first (a complaint is a complaint
  whatever team the model asked for).
- **Rules can set what the AI does** for what they match: reply, draft only, or stay out (a person gets a task and
  nothing is sent). They can't make the AI answer a VIP or an opted-out contact: those checks run first.
- **VIP re-alert:** a VIP's task still open after `settings.vip_realert_minutes` (default 10) raises the alert
  again, up to 3 times. The alert is an event until the owner's WhatsApp layer (Step 8) delivers it.

## 2026-11-27: "Who gets what" settings screen (Step 6b)

- **Its own page** (`/settings/routing`, linked from a summary in Settings), like Team: the rule list is a
  workspace, and Settings was already six sections long.
- **Rules read as sentences**, built from the form ("Complaints go to Managers, marked urgent."), numbered in the
  order they're checked. The form shows the sentence as you build it. Rules have no name field: the sentence is the
  name, and one less thing to fill in.
- **Two fixed lines frame the list:** VIPs first (crown, can't be changed) and "everything else goes to the usual
  team" last, so the dealer sees the whole decision, not only their own rules.
- **"Check a message"** runs a typed message through the same classifier and rules (`POST /routing/preview`) and
  says who would get it now, which rule decided, and what Ondra would do. Sends nothing, takes nobody's turn.
- **Reorder with Move up / Move down in the menu**, not drag and drop: works on a phone and by keyboard, and the
  list is short (limit 50).
- **Delete has Undo** (the rule is re-added and put back in its place) rather than a confirmation.
- **A person's hours, time zone and task limit** are in a sheet from the Team page ("Hours and workload"), also
  for yourself. Off by default: people follow the dealership's hours.
- **Found by the browser run, not the tests:** the Team list endpoint didn't return the new fields, so the sheet
  thought everyone had their own hours. Fixed and covered by a test.

## 2026-11-27: Follow-up sequences and quiet hours (Step 6c)

- **What starts one:** any reply (Ondra's or a person's) that goes out on text, WhatsApp or email. The customer's
  place in the first active sequence that covers the conversation's topic begins; each later reply restarts it.
  One follow-up stream per customer, on the channel they last wrote on, never one per channel.
- **What stops one:** the customer writes back on any channel (a draft waiting for approval is thrown away too),
  STOP, a person takes over, a booked appointment, the sequence switched off, or a person discarding the draft.
- **Checked again when each step is due, not when it was scheduled:** opted out, VIP, person handling, replied,
  booked, quiet hours, consent. A day is a long time; the state when the timer was set proves nothing.
- **Consent (CLAUDE.md: no automated texts without recorded consent):** a follow-up is the dealership writing
  first, so by text or WhatsApp it needs a recorded opt-in for that channel. Without one, a person gets a low-urgency
  task and nothing is sent. Most first-time texters have no recorded consent today, so most text follow-ups will
  become tasks until counsel says whether an inbound text is itself consent to a follow-up. Email needs no
  recorded opt-in (opt-outs still block it).
- **WhatsApp outside the 24-hour window** needs an approved template, which isn't built: it becomes a task.
- **VIPs and complaints are never enrolled.**
- **Who writes it:** per step, Ondra (one model call, no tools, from the conversation) or a fixed message with
  `{first_name}` and `{dealership}`. Ondra's is held to the reply checks with no price allowed at all, may answer
  SKIP when there's nothing useful to say, and is told not to claim a car is still available (it hasn't checked):
  the first real-model run said "the CR-V is still here". If its draft fails, the step's fixed text is used if
  there is one, else nothing is sent.
- **Approval is the default** per step, and forced while draft mode is on. An approved draft goes through the
  normal approve path; the next step is scheduled when it's actually sent.
- **Quiet hours** default to 9 pm to 8 am in the dealership's time and can be changed but not switched off. They
  hold back follow-ups only. Replies to a customer who just wrote aren't held back, and appointment reminders
  aren't either (they're about something the customer booked): both are questions for counsel, listed in STATUS.
  The customer's own time zone isn't known, so a Lagos buyer gets Dallas quiet hours.
- **Limits:** 50 routing rules, 20 sequences, 6 steps. Guards against runaway lists, not product limits; raise
  them when a real dealer hits one.

## 2026-11-27: The learning loop (Step 6d)

- **Unanswered questions.** When the AI hands off because it didn't know, the question is kept (the model's own
  search words, which are focused) with the customer's actual message saved alongside at that moment. The same
  question in other words is one line "asked 4 times": matched by embedding against open questions (0.80 for
  Voyage, 0.70 for the local mock), stricter than search, because merging two different questions hides one from
  the dealer. If embeddings are down, only exact matches merge.
- **Answering** turns the question into a knowledge doc and embeds it on the spot, so the next message can find it.
  "A person should always handle this" takes a question off the list for good (with Undo).
- **Who can answer:** owners, admins and managers (a new `knowledge:write` permission). Managers know the answers;
  making them ask an admin would leave the list unread. Anyone who can reply to customers can rate a reply.
- **Ratings:** good, wrong, or off in tone, one per reply (the latest wins), from the Inbox. Wrong and off-tone
  replies are listed under Corrections with what the customer said. No free-text note in the Inbox yet (the API
  takes one).
- **Corrections** also lists drafts a person changed before sending (recorded since Step 3), with "save what was
  sent as an answer". The plan asks for patterns across edits to be surfaced as suggestions; this shows each edit
  and leaves spotting the pattern to the dealer. Automatic pattern-finding is not built.
- **"Ratings feed the eval set" is not built.** Ratings are stored with the reply and the customer's message, which
  is what an eval case needs, but nothing exports them into `evals/` yet. Real conversations contain customer data,
  so that export needs a redaction step and a decision about where such cases live.
- **Seen in the real-model acceptance run:** the dealer's answer included a service price ("$450"); Ondra's reply
  used the answer but left the price out. The price rules only allow listed vehicle prices, so prices inside
  dealer answers aren't repeated today. Whether they should be is a product decision.

## 2026-11-27: Integrations (Step 7)

- **Leads to the dealer's CRM (ADF/XML email).** A sales lead is sent once, a minute after it qualifies (we know
  what they want and have a phone or email), so details from the same conversation go together. VIPs are never
  sent. The body is the XML and nothing else, plain text, from the dealership's own email address.
- **What "valid ADF" rests on.** The spec's site was unreachable from the build machine. Element names, attributes
  and child order come from a copy of the ADF 1.0 DTD read in full (github.com/carmelosantana/sendadf); the
  processing instruction and date format from that project's output and search snippets of the spec. Ondra builds
  to those rules and checks every lead against them before sending (`ondra_core.adf.problems`). No CRM vendor's
  documentation was read and no real CRM has received one. `TODO(verify)` per pilot dealer's CRM: body or
  attachment, subject line. "Send a test lead" in Settings exists for exactly that check.
- **A lead with no particular car** ("a 3-row SUV") is still sent: `year`, `make` and `model` are required by the
  DTD, so they're present and empty, with the description in the vehicle's comments. Make and model are filled only
  when the description names exactly one model the dealer stocks. Never a guess at a specific car.
- **Inventory import.** Headers are matched by meaning across vendor spellings; a row that can't be used is
  reported with its line and the reason, never guessed at. Cars match by VIN, then stock number. Every import is
  previewed before it's applied. "$0" means no price (the AI then says sales will confirm it).
- **Marking cars sold** only happens when the file is declared the whole lot (a scheduled feed always is), only
  for cars that came from an import (never hand-entered ones), and not at all when the file lists under half of
  what the feed had: a feed cut short mid-export would otherwise have the AI telling buyers the lot is empty.
- **Scheduled feed fetch** takes an https address on the standard port with no credentials in it, refuses private
  and internal addresses, follows no redirects and caps the download at 5 MB. **Known gap:** the host is resolved,
  checked, then connected to by name, so DNS rebinding isn't stopped. Close it at hosting with an egress proxy that
  refuses private ranges. Feed addresses that need a login aren't supported yet (credentials need the encryption
  key work in Step 10).
- **DMS.** One interface (`DmsAdapter`), two adapters: demo data and a repair-order CSV the dealer uploads. Real
  vendors need partner programs; none is built or claimed. The CSV adapter can't book (Ondra's own calendar does).
- **Repair-order privacy.** A customer hears only about repair orders under the phone number or email they're
  contacting from. An RO number alone finds nothing, and Ondra neither confirms nor denies someone else's.
- **No completion times or costs** from the DMS reach the AI at all, not even when the DMS has them: the product
  rule is that Ondra doesn't promise dates. It says the stage and the advisor's name; timing goes to service. The
  first real-model run handed off for timing when the customer hadn't asked; the prompt now says not to.
- **Health without colour.** Each integration says in words whether it's off, working, working with a warning,
  or not working, with an icon. Red stays for VIPs and overdue items.

## 2026-11-27: The owner's WhatsApp line (Step 8)

- **Who is "the owner" on WhatsApp:** an active user with the owner role whose mobile (Team) is the number
  writing in. WhatsApp only: it verifies the sender's number, and a text message's sender can be faked, so the same
  number by SMS is treated as a customer. Managers aren't included yet. The owner writes to the dealership's own
  WhatsApp number; a separate "assistant number" would simply be a second WhatsApp number on the dealership.
- **Not a customer.** The owner's messages never create a contact or a conversation. They live in
  `assistant_messages`, with what Ondra sent back.
- **The 24-hour rule** (Meta's docs, read 2026-11-27): free text and reply buttons only within 24 hours of the
  owner's last message; otherwise an approved template. Two templates are proposed, `ondra_morning_briefing` and
  `ondra_alert`; their wording and category are approved per WhatsApp Business account by Meta, so they're
  proposals until a dealer's account has them. The research's reading is that a daily summary fits "utility"; Meta
  re-categorises templates it judges to be marketing. WhatsApp also requires an opt-in before messaging anyone:
  the owner switching the briefing or alerts on is that, and it's in the audit log.
- **Alerts reach the owner through a database trigger**, not a call at each place that raises one: every
  `alert.created` event addressed to the owner queues its delivery in the same transaction. Six places raise
  alerts today; none had to change, and a seventh can't forget.
- **Briefing counts:** VIPs waiting = VIP clients with an open task; hot leads = other clients with an open
  high-urgency task; drafts = Ondra's drafts awaiting approval; overdue = open tasks past due; appointments =
  booked or confirmed, today in the dealership's time zone. The job lines up tomorrow's before sending today's, at
  the wall-clock time in the dealership's zone (so it stays at 7:30 across a clock change).
- **The assistant's tools:** find a client (tolerant of names spelled by ear), client details, who wanted
  something, add a note, update a deal, create a task, what's waiting, approve a draft. It has no tool that
  messages a customer. Approving a draft sends it through the one send path, with every check a dashboard
  approval gets.
- **From the real-model run:** replies were long, used markdown WhatsApp doesn't render, and one "corrected" an
  earlier reply because it could no longer see the tools it had used. The prompt now asks for one or two plain
  lines, and earlier replies carry a note of what was changed.
- **Voice notes: no real transcription yet.** The interface and a mock exist, and the WhatsApp adapter can
  download the audio (two requests, 16 MB cap, per Meta's docs). Which speech-to-text service turns a recorded
  file into text is a founder decision: the calls use LiveKit's live recognition, which isn't built for files.
- **Not built:** buttons on the briefing itself (a template with quick replies needs its own approval); the
  assistant for managers; a view of the assistant thread in the dashboard.

## 2026-11-27: Analytics (Step 9)

- **Every dashboard number is a count (or a median) of rows in `events`, and nothing else.** One table in
  `ondra_core.metrics` says which events count toward which number; the daily rollups, the period totals and the
  "what's behind this number" list all read that table, so they can't disagree. The test fixture is three days
  worked out by hand in the test's docstring.
- **New events at the moment things happen:** `lead.captured` (who captured it, the channel, after hours or not),
  `response.sent` (only the first answer to a waiting customer, with how long they waited and who answered),
  `follow_up.sent`, `deal.stage_changed`. Appointment and call events existed already and now carry the contact.
- **A day is the dealership's day.** A lead at 11:30 pm in Dallas is that night's, not tomorrow's in UTC.
- **Rollups are a cache** (`metric_days`, one row per dealership day). A finished day is computed once; today's
  is recomputed when it's more than five minutes old. Reply times are kept whole per day, not averaged, so a
  period's median is exact. Rollups are computed when the dashboard is read; there is no nightly job yet (the plan
  mentions one), because nothing needs the numbers when nobody is looking.
- **Median first reply** counts each time a customer wrote and was waiting, to the first message that went out to
  them, from Ondra or a person. It covers messages, not calls (a call's speed to answer is a different number).
- **Pipeline** is where each deal stands now, folded from every lead and stage event. There was no way to move a
  deal's stage, so `PATCH /deals/{id}` was added (it records the event). The Deals board still shows example data
  and isn't wired to it.
- **History before these events** gets backfilled events, dated when the thing happened and marked as such. Who
  captured an old lead isn't knowable, so those say "unknown" and count toward neither Ondra nor the team.
- **Charts** (dataviz and ondra-ui): one chart, first replies per day stacked by who answered. Ondra blue against
  a new neutral grey token for the team: checked for colour-blind separation and 3:1 on both surfaces. The
  validator's "reads grey" failure is deliberate: people are not a brand colour. Channels and stages are bar lists
  in one ink; red is never a series. Comparisons with the period before are muted text with an arrow.
- **Not built:** value of deals in play (deals carry no reliable value yet); per-salesperson breakdowns; exports;
  a custom date range.

## 2026-11-27: Closing the gaps after Step 9

- **Deals board on real deals.** `GET /deals` gives the sales board; moving a card records `deal.stage_changed`,
  which is what the Today pipeline counts. Lost asks why (four reasons), with Undo. A card's value is an estimate:
  the listed price of the car in stock they named, else their budget, else blank, never a guess. VIP deals only
  for people who can see VIPs. The service board was dropped: it was example data with no real model behind it.
- **Calls offer texts only when the dealer's texting is live.** The rules, the stock search's hint and the
  `text_details` tool all change when the dealer's SMS is the mock. `VOICE_TEXT_ON_MOCK=1` allows it on purpose
  for local runs and tests. Checked on a real-model call: asked to text, Ondra said it can't from this line and
  offered a follow-up from sales.
- **A handoff is said once.** When Ondra has already spoken in the reply that hands off (with or without lead
  details), LiveKit's follow-up reply is cancelled. Real-model calls before: "I'll pass that to sales ... Sales will
  call you back"; after: one sentence, twice in a row.
- **Rated replies become draft eval cases** (`python -m ondra_api.services.eval_export --tenant <id>`), redacted
  (names, phones, emails, VINs, street addresses), into `evals/candidates/`, which git ignores and the eval runner
  doesn't read. A person writes the expectation and checks the redaction before moving one into `evals/golden/`.
  Redaction is pattern-based and will miss some things; the human review is the real safeguard.
- **A note when rating a reply wrong or off in tone**, asked inline in the Inbox (skippable).
- **Per-person first replies** on Today (owners, admins, managers only): each `response.sent` by a person now
  carries who sent it. Replies before this change have no person and aren't counted per person.
- **The owner's assistant conversation** is readable in Settings, by the owner only.
- **Feed fetch connects to the address it checked** (the Host header and TLS name stay the real ones), which
  closes DNS rebinding when there's no proxy. Behind an HTTPS proxy the proxy resolves the name, so production still
  needs an egress proxy that refuses private ranges.
- **Left open, on purpose:** reply time for calls (Ondra answers every call it takes at once; "speed to answer" for
  people needs ring timing from the carrier); a dollar value on Today (deal values aren't events, and every number
  on Today must trace to events; the estimate lives on the Deals board); prices inside a dealer's own answers
  (a product decision for the founder).

## 2026-11-27: VIPs look like a status, not an alarm

- **The VIP mark is ink, not red.** A small outlined "VIP" tag beside the name and an ink ring around the avatar,
  in place of the red crown. Founder: the crown wasn't professional. A VIP is a standing arrangement, not an emergency,
  so it shouldn't share a colour with things that are late. Red is now `--overdue` only (overdue tasks and replies).
- **"VIP", not "Verified".** Verified implies Ondra checked who someone is; it hasn't. VIP says what it means here:
  a person always handles them.
- **Made a VIP on the client, not in Settings.** Owners and managers get "Make VIP" on the client's profile, with the
  effects spelled out and a choice of who looks after them. The Clients list has an All / VIPs toggle for them.
- **Becoming a VIP takes effect at once:** drafts Ondra had queued for them are deleted and any follow-up is
  cancelled, so nothing AI-written reaches them after the switch. Recorded as `contact.vip_changed` and in the
  audit log. Alternative considered: let queued drafts through for approval. Rejected: the product rule is no AI
  content for VIPs at all, and a person approving a draft by habit would break it.

## 2026-11-27: Saved views are fixed Inbox filters, not user-made views

- **Three views, defined in code** (`apps/web/lib/saved-views.ts`): Drafts to approve, VIPs waiting (owners and
  managers only), After-hours leads. Each opens `/inbox?filter=…`; the sidebar count and the Inbox filter use the
  same test, so the number is always what opens. The old links went nowhere, and the Open / Share / Delete menu and
  "More" did nothing; both are gone.
- **A view replaces the Inbox tabs while it's on**, with its name, count and Clear. Two filters stacked (a tab and a
  view) would make "why isn't Kevin here?" a puzzle.
- **After-hours lead** = a lead captured while the dealership was closed (the `after_hours` flag on `lead.captured`)
  in the last 7 days. Older ones have been dealt with or belong to the pipeline, not the Inbox.
- **Not built: making your own views.** Nobody has asked for it, and three good ones beat a builder nobody uses.
  Revisit if dealers ask for "my leads" or "Spanish speakers".
- The seed gains an after-hours conversation (a buyer in Lagos at 2 am Dallas time) so the view isn't empty in demos.

## 2026-11-27: Settings is an index of pages, not one long form

- **Decision:** `/settings` lists every setting as a row in four groups (your dealership, your team, Ondra, you).
  Each row says in plain words what's set now ("Open today 9 am to 7 pm, Chicago time") and calls out anything
  waiting on someone ("1 invited, not joined", "2 questions to answer"). Each row opens its own page with a back link.
- **Why:** the old page was ten sections in one scroll, with forms, summaries and links to other pages mixed
  together and a scroll-spy to keep track. The founder found it hard to follow. Most visits are "change one
  thing" or "is anything wrong?", and an index answers both without scrolling.
- **Rows a role can't open are left out** (a 403 from the row's API hides it), and "You" (the WhatsApp
  assistant) shows to owners only. A salesperson sees eight rows, not eleven dead ends.
- **No Notifications row.** It was planned, but there is no notification setting to put behind it. The Account,
  Billing and Notifications items in the account menu did nothing, so they're gone. Add them when they exist.
- **Fixed along the way:** the seed stored handoff rules as short keys ("discount") while the form offered phrases
  ("A discount or final price"), so each rule showed twice. The seed now uses the phrases, and the form maps old
  keys to the phrase they mean.
- **Alternatives:** a left-hand section menu with one form per page (like Linear). Rejected for now: with eleven
  pages, a status line per row is worth more than a menu that's always visible.

## 2026-11-27: The person looking after a VIP is told, and "Saved views" are called Shortcuts

- **Decision:** choosing someone to look after a VIP gives them a task ("You now look after Robert (VIP)") with a
  brief on what changes for them, and a WhatsApp alert to their own mobile. Before this, nothing told them: a
  salesperson found out when the VIP's call rang through.
- **The alert goes to them or nobody.** Ordinary alerts fall back to every owner when a handler has no mobile; this
  one doesn't, because the owners didn't ask to be told who they just picked. Instead the task says "add your mobile,
  or their calls ring the owner instead". Choosing yourself, or re-saving the same person, tells nobody anything.
- **"VIPs waiting" shows to anyone who looks after a VIP,** not only owners and managers. The Inbox list already
  holds only the VIPs a person may see, so for a salesperson it counts their own.
- **"Saved views" is now "Shortcuts".** Nobody saves them: they're three fixed filters. The template's name invited
  "who saved this?". Code names follow (`lib/shortcuts.ts`, `nav-shortcuts.tsx`).

## 2026-11-27: The Clients list answers "where do they stand?", newest contact first

- **One contact line, not two columns.** The old list showed the email twice (in "Best way to reach" and in
  "Email"). Now each client shows one way to reach them: their preferred channel's number or address.
- **Search by anything you know.** A name, an email, or a phone number typed any way ("(214) 555-1003",
  "555-1003" and "2145551003" all match +12145551003): the API strips the punctuation and matches digits, from 3
  digits up. VIPs a person may not see stay invisible to search, by number too (tested).
- **Each row carries the latest deal** (car, stage, budget), **who looks after them** (the deal's salesperson,
  else the VIP's handler, else whoever has the conversation, else whoever has an open task about them) and
  **when you were last in touch** (the latest sent or received message, drafts excluded).
- **Last in touch first, by default.** The client you're looking for is usually one you just spoke to. "By name,
  A to Z" is one click away.
- **Paged by the API, 50 at a time,** instead of loading 200 and stopping. A dealership has thousands of clients.
- **Not built:** filtering by stage or salesperson (the Deals board does that), bulk actions, and exporting.
  Opt-outs aren't shown in the list yet; they're on the profile.

## 2026-11-27: Deals have a salesperson from the start, and open in a side panel

- **Ondra gives every deal it opens a salesperson:** whoever has the conversation, else the next in turn under the
  dealer's routing rules (the same `route()` the Inbox uses, so dealer rules and shifts apply). Before, deals Ondra
  opened belonged to nobody, so "Mine" would have been empty for everyone. Older deals without one fall back to
  whoever has the conversation or an open task, and a manager can hand any deal to someone from its panel
  (audited as `deal.owner`). VIP deals are never auto-assigned: their handler has them.
- **Each card says what the deal needs next:** a booked visit beats a task; an overdue task is red (red is for
  overdue only). Plus who has it and when you were last in touch.
- **Drag between stages,** with the card moving at once and Undo in the toast. Six columns don't fit beside the
  sidebar, so while dragging, "Won" and "Lost" drop targets appear at the bottom of the screen (the pattern
  Pipedrive and HubSpot use). Dropping on Lost asks why, because the reason is what the owner learns from. The card's
  menu still moves it, and is the keyboard and touch way to do it: HTML drag and drop doesn't work on phones.
- **"Mine" and "Everyone".** Salespeople start on Mine; owners and managers on Everyone.
- **The deal panel** (`/deals?deal=…`, a sheet over the board, so you keep your place): call, message, profile;
  stage and salesperson; what they want (car in stock with price, budget, paying by, trade-in, timing, delivery);
  what's next; the last six messages; how the deal has moved and who moved it. A VIP's panel shows nothing Ondra wrote.
- **Follow-ups the same day:** handing a deal to someone now gives them a task and a WhatsApp note to their own
  mobile (never the owners instead); what the buyer wants (car, budget, paying by, trade-in, timing) can be corrected
  from the panel, sending only what changed and audited as `deal.edit`; dragging moved to `@dnd-kit/core` (already a
  dependency from the dashboard template), so a phone can press-and-hold to drag and the board still scrolls under a
  finger; migration 0018 gives older deals the salesperson who has the conversation or an open task.

## 2026-11-27: Every time on screen is the dealership's time

- **Decision:** the dashboard formats every time in the dealership's time zone (from `/me`, set once in
  `lib/time.ts` before anything renders), not the reader's. When the reader's zone differs, the header says
  "Times in Chicago time".
- **Why:** an owner checking in from Lagos saw that Aisha wrote at 8:10 am when she wrote at 2:10 am Dallas time,
  which hides the fact that she wrote after hours. "Today", "overdue" and the calendar's day all follow the
  dealership's calendar too.
- **Alternatives:** the reader's own zone (what browsers do by default; wrong for a business with opening hours),
  or both zones on every time (noisy). The greeting on Today still follows the reader's clock: it's about them.

## 2026-11-27: Tasks for everyone is a board by person; your own stay a list

- **Mine stays a list** grouped Overdue, Today, Later: one person working down their to-dos wants order, not columns.
- **Everyone is a board, one column per person who takes work** (owners, managers, sales, service, operations;
  admins set things up and don't take tasks), busiest-with-overdue first, plus "Nobody yet" when something is
  unassigned. Each column header says how much is open and how much is overdue (red, which means overdue). It
  answers the manager's question: whose work is slipping, and who's free.
- **Drag a task to someone to give it to them** (press and hold on a phone), or use its "Give to" menu, which is
  the keyboard way. Undo in the toast. The same drag library as the Deals board.
- **VIP tasks carry the VIP tag** in both views, and never Ondra's mark (a VIP surface shows nothing AI-blue).
- **Not built:** notifying someone a task was given to them (it lands in their list and the sidebar count),
  workload limits, and filtering the board by team.

## 2026-11-27: Inventory answers "what's sitting, and who wants what"

- **Days on the lot** count from when the car first came in (`created_at`: the first import, or when it was
  entered). Over 60 days in stock is set in weight, not colour: red means overdue only. Sort "Longest on the lot" is
  the default, because that's the question a manager brings to this page; "Most asked about" is one click away.
- **"Asked about"** counts open sales deals that name the car: by stock number when the buyer gave one, else by
  model (and year and make when they said them). "Lexus RX 350" with no year matches every RX 350, and the car's
  panel shows what they actually asked for. No guessing from free text beyond that; conversations that never
  became a deal don't count.
- **Holds belong to people:** anyone who sells can hold a car, for a named buyer ("Hold for Aisha" from the car's
  panel) or not, and release it. Marking sold, or un-selling, is a manager's or owner's call because it takes the car
  away from Ondra's answers. A hold placed in Ondra survives the next inventory file until someone releases it, or
  the file says it sold. Every change is audited (`vehicle.status`).
- **Photos only when the feed sends them.** No stock images, and no placeholder column when no car has a photo:
  forty identical icons are clutter.
- **Not built:** price changes from the list, aging alerts to the owner, and matching buyers from conversations that
  haven't become deals.

## 2026-11-27: A call-back is per caller, and it's the same thing as the call-back task

- **One row per waiting caller.** Someone who rings three times before anyone rings back is one row ("Rang 3 times
  since 11:26 am"), one task ("Call Carmen back (called 3 times)", raised to high urgency), and one "sorry we missed
  you" text: a second text inside two hours is skipped and recorded as "texted recently". A VIP ringing again still
  alerts the owner every time.
- **Marking a call called back and finishing the "Call X back" task are one action**, whichever screen it's done
  from: "Spoke to them" on Calls finishes the task, and ticking the task on Tasks clears the caller from the
  call-back list. The link is the task's rule source and its brief, not a new column. Undo puts the calls and the
  task back together.
- **Two outcomes, not one:** "Spoke to them" (done) and "No answer, left a message" (noted with who and when; they
  stay on the list). A dealer's real call-back often reaches voicemail, and marking that "done" would lose the lead.
- **Every row says who's on it and what's happened:** "For Daniel to call back" (the task's assignee), "Daniel left a
  message at 12:21 pm", and once done, "Called back by Daniel 35 minutes later": the time to call back is what a
  manager checks.
- **Calling is a `tel:` link that shows the number.** On a phone it dials; at a desk the number is right there to
  dial from the desk phone. Calling out through Ondra's own line (so the caller sees the dealer's number and the
  call is logged) needs Twilio outbound and is not built.
- **Filters:** All, Missed, Ondra answered, Put through (to staff or the owner), with `?show=` in the URL.
- **Not built:** click-to-call through the dealer's line, logging call-backs automatically from that call, and a
  time-to-call-back figure on Today.

## 2026-11-27: Time to call back, on Today

- **What it measures:** from a missed caller's first ring to the team's first try at ringing them back, as a median
  over the period, with the per-person split for owners and managers. A voicemail counts as the try: how fast the
  team picks up the phone is theirs; whether the customer answers isn't. Someone who rang three times is one wait,
  timed from their first ring.
- **Open hours only.** A call missed at 11 pm and returned at 9:10 am waited 10 minutes, not 10 hours
  (`sla.business_seconds`). Clock time is kept on the event too (`clock_seconds`) if we ever want to show it.
- **Recorded as an event** (`callback.first_try`), like every other number on Today, so "See what's behind this"
  lists each call-back. Undo marks the event undone and drops that day's cached numbers, so an undone call-back
  doesn't count.
- **The waiting callers are one line under "Needs someone"** ("2 callers waiting for a call back, 1 overdue. Longest:
  Jordan, since yesterday"), and their tasks no longer also appear one by one as overdue or urgent tasks.
- **Not counted:** callers still waiting (they're in the line above, not in the median, so a team that never calls
  anyone back doesn't get a good median from it: the count of missed calls sits beside it), and call-backs made
  before 2026-11-27 (no event was recorded then).

## 2026-11-27: Calling back goes through the dealership's line (a "bridge" call)

- **How:** "Call Carmen back" makes Ondra ring the salesperson's own mobile (their number on Team). They pick up,
  hear "Call back Carmen Ortiz from Ondra. Press 1 to connect", press 1, and Twilio dials Carmen with the number she
  originally rang as caller ID. Two call legs on Twilio per call-back.
- **Why press 1:** if the salesperson's phone goes to their own voicemail, the voicemail "answers" leg 1. Without a
  key press, Ondra would dial the customer into the salesperson's voicemail. No key, nobody is called.
- **Why the dealer's number, not the salesperson's:** customers keep one number for the dealership, the call is
  logged, and a salesperson's private number doesn't walk out the door with the customer.
- **The result logs itself:** connected for 60 s or more counts as "spoke to them" (marked called back, task
  finished, counted on Today). Under 60 s is most likely their voicemail: a try, and they stay on the list. Busy or
  no answer: a try. Twilio can't tell a short real conversation from a voicemail without answering-machine detection
  (which delays the connect by a few seconds); "Spoke to them" by hand still works for that case.
- **Consent:** a person taps this each time, to return a call the customer made, so it isn't an automated
  outbound call. It's allowed even if they texted STOP (that withdrew consent to texts, not to a returned call).
  This is a reading of the rule, not legal advice; confirm with counsel before launch.
- **"Call from your own phone"** stays in the menu for when the line can't be used; it isn't logged.
- **Mock:** with FEATURE_CALL_BRIDGE off, the mock records the call, and with MOCK_BRIDGE_AUTOPLAY plays it out
  through the real webhooks locally. Checked against Twilio's docs 2026-11-27 (see services/bridge.py).
- **Not built:** recording (needs the consent notice), answering-machine detection, verifying the dealer's own number
  as a caller ID from Ondra (done once in Twilio for now), and a salesperson's choice of which phone to ring.

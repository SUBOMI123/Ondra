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

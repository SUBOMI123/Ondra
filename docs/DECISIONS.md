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

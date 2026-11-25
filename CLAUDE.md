# Instructions for Claude Code

This repo builds **Ondra**, a multi-tenant AI platform for car dealerships. The complete specification is in `BUILD_PLAN.md`. Read it fully before writing any code.

## How to work

- Follow the build order in BUILD_PLAN.md section 12, one step at a time. Finish a step, make its acceptance criteria pass, then stop and summarise what you built. Don't start the next step until asked.
- Check the official docs before writing any third-party integration (WhatsApp Cloud API, Twilio, Telnyx, LiveKit, Postmark, Anthropic, any DMS). If you can't verify an API detail, put it behind an interface with a mock and mark it `TODO(verify)`.
- Every external service has a mock. The whole system must run locally with `docker compose up` and no real accounts.
- Every table holding dealer data has `tenant_id`, and every query is tenant-scoped. Enforce it with Postgres row-level security and prove it with tests.
- Tests are part of done: unit tests for domain logic, integration tests for adapters against mocks, and conversation evals for the agent.
- Record non-obvious decisions in `docs/DECISIONS.md` (date, decision, why, alternatives).
- Never commit secrets. Use `.env` (gitignored) and keep `.env.example` complete and documented.
- Ask before adding infrastructure that isn't in the plan.
- When building `apps/web`, use `design/README.md` and the prototypes in `design/mockups/` as the reference for screens, layout, copy and colours.
- For any UI work (apps/site, apps/web, components, charts, copy, reviews), use the `ondra-ui` skill in `.claude/skills/ondra-ui/`. It holds the tokens, component stack and design rules.

## Product rules that must never break

- VIP contacts never get an AI reply, draft or voice answer. Their calls ring the owner directly.
- Opt-outs (for example STOP on SMS) block all outbound messages to that contact on every channel.
- No automated outbound calls or texts without recorded consent.
- The AI never commits to final prices, discounts or delivery dates unless the dealer's policy allows it.
- Dealers keep their existing phone numbers, WhatsApp number and email addresses.

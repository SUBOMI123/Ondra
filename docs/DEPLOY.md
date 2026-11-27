# Deploying Ondra (staging)

Set up 2026-11-27. Where each part runs and why: `docs/ARCHITECTURE.md`.

| Part | Where | Name |
|---|---|---|
| API + job worker | Fly.io, San Jose (`sjc`), one image, two process groups | `ondra-api-staging` (`infra/fly/api.toml`), https://api.useondra.com |
| Voice worker | Fly.io, `sjc`, 2 GB | `ondra-voice-staging` (`infra/fly/voice.toml`) |
| Database | Supabase, us-west-2 (Oregon), Free plan | project `Ondra` (`sbesiusjfltienbbieyv`) |
| Dashboard | Fly.io, `sjc`, 512 MB, sleeps when idle | `ondra-web-staging` (`infra/fly/web.toml`), https://app.useondra.com |
| Phone | Twilio number (707) 306-8599 to LiveKit Cloud SIP, dispatch to `ondra-voice` | `infra/telephony/connect_line.py` |

`sjc` because Fly's Seattle region is deprecated (no new machines) and San Jose is the nearest open region to the
Oregon database: the voice worker makes several database lookups per turn.

## First-time setup (done for staging)

1. `fly apps create ondra-api-staging --org personal` and `ondra-voice-staging`.
2. Database: `uv run python infra/deploy/supabase_bootstrap.py --project <ref> --fly-app ondra-api-staging
   --fly-app ondra-voice-staging`. It installs the extensions and creates `ondra_owner` (owns the tables, BYPASSRLS)
   and `ondra_app` (what the apps connect as: no BYPASSRLS), with generated passwords sent straight to Fly secrets.
   Needs a Supabase personal access token (`sbp_...`, Account > Access Tokens), not a project's anon or
   service_role key.
3. Secrets on both apps (`fly secrets import --stage`): `JWT_SECRET`, `MOCK_WEBHOOK_SECRET` (generated; the API
   refuses to start on an https site with the development defaults), `SEED_PASSWORD` (API only: the demo users'
   password; the seed refuses the development one there), and the provider keys: `ANTHROPIC_API_KEY`,
   `VOYAGE_API_KEY`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `ELEVEN_API_KEY`, `VOICE_TTS_PROVIDER`,
   `LIVEKIT_SIP_OUTBOUND_TRUNK`, `DEALER_PHONE`.

## Each deploy

From the repo root:

```
fly deploy . -c infra/fly/api.toml --dockerfile apps/api/Dockerfile      # runs migrations first (release_command)
fly deploy . -c infra/fly/voice.toml --dockerfile apps/voice/Dockerfile --ha=false
fly deploy apps/web -c $PWD/infra/fly/web.toml --build-arg NEXT_PUBLIC_API_URL=https://api.useondra.com --ha=false
```

DNS (Cloudflare, zone useondra.com): `api` and `app` are A + AAAA records to each Fly app's addresses, **DNS only**
(grey cloud), so Fly can issue and renew their certificates (`fly certs add <host> -a <app>`).

**The dashboard on Cloudflare Workers instead:** `apps/web/wrangler.jsonc` and `npm run deploy:cf` are ready
(OpenNext build, 1.5 MB compressed). From Ondra's cloud build session the deploy fails at the static-asset upload:
the session's proxy swaps wrangler's short-lived upload token for the saved API token (401). From any normal machine
(`npx wrangler login`, then the script) it should work; then point `app` at the Worker and retire the Fly app.

From Ondra's cloud build sessions, `docker build` can't get through the session's network proxy, so build and
push with `infra/deploy/sandbox_build.py`, then `fly deploy ... --image <the printed tag>`. It also pulls official base images through mirror.gcr.io, since the
session often hits Docker Hub's anonymous rate limit.

## Limits to know

- **Fly:** a card is on the account (2026-11-27). Four machines: API (high availability off), job worker, voice
  worker, dashboard (sleeps when idle).
- **Supabase Free:** no backups, 500 MB, pauses after a week without activity. Staging only; Pro before any real
  dealer data.
- **LiveKit Build:** 1,000 agent minutes a month, then calls stop. Ship before a pilot.

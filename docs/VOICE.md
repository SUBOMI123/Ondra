# Voice

How Ondra answers the phone (BUILD_PLAN.md §4.2, §6.4). Status and acceptance: `docs/STATUS.md`. Why it's built
this way: `docs/DECISIONS.md` (2026-11-26, voice).

## The path of a call

1. The dealer's number forwards to Ondra's Twilio number (dealers keep their number). Twilio's SIP trunk sends the
   call to LiveKit, and a LiveKit **dispatch rule** puts the caller in a room and dispatches the agent named
   `ondra-voice` (`room_config.agents[].agent_name`).
2. `apps/voice` (`ondra_voice.worker`) gets the job and calls `start_call` before anyone speaks. That decides:
   - **VIP:** cold transfer to the owner (or the VIP's person). The AI never speaks.
   - **Voice AI off, or a person took over the conversation:** cold transfer to the team.
   - **Otherwise:** Ondra answers with a fixed greeting (instant, carries the dealer's disclosures), then the model.
3. On the call, Ondra uses the same tools as text (inventory, knowledge, booking, handoff), plus
   `transfer_to_person` (warm transfer: Ondra briefs the person first) and `end_call`.
4. **Every sentence is checked before it's spoken** (`ondra_voice.guard`): the same checks as text replies. A
   failing sentence is replaced with a safe line, and a call-back task is created so that line is true.
5. When the call ends: transcript, per-turn latency and outcome go on the call record, and the summary job runs.
   A missed call gets a text-back only with recorded consent (`services/calls.py`).

## Run it

- Tests (no LiveKit, no audio, scripted model): `uv run pytest apps/voice`.
- Against LiveKit Cloud: set `LIVEKIT_*` in `.env`, then `docker compose -f infra/docker-compose.yml --profile voice up`,
  or from the repo: `cd apps/voice && uv run python -m ondra_voice dev`. The worker logs `registered worker` with
  `agent_name: ondra-voice` when it's connected.

## Models

Set in `.env` (see `.env.example`): `VOICE_STT_MODEL` (LiveKit Inference speech to text), `VOICE_LLM_MODEL`
(blank: `MODEL_FAST`), `VOICE_TTS_PROVIDER` / `VOICE_TTS_MODEL` / `VOICE_TTS_VOICE` (LiveKit Inference, or
ElevenLabs with `ELEVEN_API_KEY`). The default voice is Cartesia Sonic 3.6, "Jacqueline", chosen in a blind
test (see DECISIONS). Turn detection is LiveKit's turn detector, with adaptive interruptions and
preemptive generation.

## Connecting a real number

`infra/telephony/connect_line.py` sets up both sides, and is safe to run again:

```
uv run python infra/telephony/connect_line.py --number +17073068599 --sip-uri sip:<project>.sip.livekit.cloud
```

- Twilio: an Elastic SIP trunk with call transfer on, origination to LiveKit, a credential LiveKit uses to call
  out (transfers), and the number on the trunk. Not a TwiML Bin: LiveKit documents that route as supporting neither
  transfers nor outbound calls, and VIP calls and warm transfers need both.
- LiveKit: an inbound trunk for the number, a dispatch rule (one room per caller, agent `ondra-voice`), and an
  outbound trunk to Twilio. It writes `LIVEKIT_SIP_OUTBOUND_TRUNK` and `DEALER_PHONE` to `.env`.
- The SIP URI is on LiveKit Cloud's Project settings page (or `lk project list --json`: the ProjectId without `p_`).

Verified 2026-11-26: a test call to (707) 306-8599 reached LiveKit, which created the caller's room and dispatched
the `ondra-voice` worker. In the cloud build container the job then failed joining the room (that network blocks
LiveKit's media servers), as expected.

## Where the worker runs for a real call

Not in Ondra's cloud build container: a call's audio flows over WebRTC, which that container's network doesn't
carry, and the worker needs the database. For the acceptance call, run the stack on a computer with a normal
connection: `docker compose -f infra/docker-compose.yml --profile voice up` with the `.env` above. Before a pilot,
the API, database and worker need a host (founder decision in `docs/STATUS.md`).

Each person's mobile (Settings > Team, or their own via `PATCH /me`) is where Ondra rings to put a call through:
the owner's for VIP calls, a salesperson's for a warm transfer.

## The Step 5e session: two calls, on a computer with a normal connection

The worker can't carry call audio from Ondra's cloud build container (verified 2026-11-27: it registers with
LiveKit, but no media flows there, and every real call so far ran on the founder's Mac). Everything below is ready;
it needs about 20 minutes and two phones.

**Before the calls**

1. Pull the branch and start the stack with the `.env` used for the first calls:
   `docker compose -f infra/docker-compose.yml --profile voice up` (or the API, web app and
   `cd apps/voice && uv run python -m ondra_voice dev` by hand).
2. Turn on the speech-to-text bake-off for these calls, in `.env`:
   `VOICE_STT_SHADOW=assemblyai/assemblyai-stt-3-7-realtime-agent,deepgram/nova-2-phonecall`. The live model stays
   `deepgram/nova-3`; the others only listen.
3. Settings > Team: put the second phone's number on **Grace Thompson** (the manager). "Talk to a manager" rings
   whoever routing assigns for managers, and only if they have a phone.
4. Your own mobile must not be a seeded client's number, or Ondra greets you as that client (fine, just know it).

**Call 1: the bake-off and the latency report** (dial (707) 306-8599)

Read `apps/voice/src/ondra_voice/script.txt` aloud, one line per turn, letting Ondra answer in between. Book the
Saturday test drive when it offers. Then, with the stack still running:

- `cd apps/voice && uv run python -m ondra_voice.bakeoff`: each model's error rate on your read script and the key
  terms it heard (CR-V, Okonkwo, the prices, "Saturday at ten"). Key terms decide it: they are what the agent must
  hear right.
- `uv run python -m ondra_voice.report`: per turn, how long the caller waited and where it went (end of turn,
  model, voice, tools, and the unaccounted rest). This finds the missing ~2 s.

**Call 2: the warm transfer** (Step 5's last acceptance check)

Call again and say you'd like to talk to a manager about a price. Ondra should say it's putting you through, the
second phone should ring, and on answering both phones should be connected. Afterwards Calls shows it as put
through to Grace, with Ondra's summary.

**After:** paste the two printouts back into the session. The winning model becomes `VOICE_STT_MODEL`, and the
latency numbers decide the next change (end-of-turn wait, prompt length, or tools).

## Still to do (Step 5e, needs a host with a public URL)

- Whether a cold-transferred call was answered (Twilio call status), so an unanswered VIP alerts the owner.
- A call nobody answers must not vanish: Twilio's fallback route to the dealer's line, and an alert when no worker
  is registered.
- Call-backs through the dealer's line (built against a mock): Twilio must reach the API's webhooks.
- Recording (LiveKit Egress) once counsel answers on recording consent. Today nothing is recorded.

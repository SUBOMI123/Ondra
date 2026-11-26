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
ElevenLabs with `ELEVEN_API_KEY`). Turn detection is LiveKit's turn detector, with adaptive interruptions and
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

## Still to do (Step 5e)

- Whether a cold-transferred call was answered (Twilio call status), so an unanswered VIP alerts the owner.
- Recording (LiveKit Egress) when the dealer has consent set up. Today nothing is recorded.
- Speech-to-text bake-off on phone-quality, accented audio; the voice; a real latency report.

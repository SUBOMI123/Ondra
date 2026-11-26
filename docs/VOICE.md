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

## Still to do (Step 5e)

- Twilio number, Elastic SIP trunk to LiveKit, LiveKit inbound trunk and dispatch rule; an outbound trunk
  (`LIVEKIT_SIP_OUTBOUND_TRUNK`) for warm transfers. Steps to be written from LiveKit's and Twilio's docs when it's set up.
- Whether a cold-transferred call was answered (Twilio call status), so an unanswered VIP alerts the owner.
- Recording (LiveKit Egress) when the dealer has consent set up. Today nothing is recorded.
- Speech-to-text bake-off on phone-quality, accented audio; the voice; a real latency report.

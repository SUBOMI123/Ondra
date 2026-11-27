"""Speech-to-text bake-off on real phone audio (Step 5e).

How it works: during a real call, the caller's audio is also sent to the models in VOICE_STT_SHADOW (comma-separated
LiveKit Inference ids, e.g. "assemblyai/assemblyai-stt-3-7-realtime-agent,deepgram/nova-2-phonecall"). Only the live
model (VOICE_STT_MODEL) drives the conversation; the others just listen. Each one's final transcripts are stored on
the call record (metrics.stt_shadow), next to what the live model heard (the caller's turns in the transcript).

Then the caller reads `script.txt` (in this folder), a dealer call full of the words phone audio mangles: makes and
models, trims, prices, names from Lagos and Dallas, a VIN fragment. `python -m ondra_voice.bakeoff` scores every
model on the latest call (or `--call <id>`):

    word error rate   against the script, after normalising case and punctuation and dropping numbers, which models
                      write as digits or words and the script can't predict (prices are scored as key terms instead)
    key terms heard   each term with its accepted spellings ("CR-V", "crv", "cr v"); this is what decides whether the
                      agent answers the right question

All models get the same hints (the dealer's name and the makes and models in stock) as the live one does.

Checked against the installed livekit-agents source (1.9): rtc.AudioStream.from_participant(participant=,
track_source=, sample_rate=); inference.STT(model=, language=, extra_kwargs=).stream() with push_frame / end_input /
async iteration of SpeechEvent (FINAL_TRANSCRIPT, alternatives[0].text); keyterm hints go under "keyterm" for
Deepgram, "keyterms_prompt" for AssemblyAI and "keywords" for OpenAI models (inference/stt.py).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("ondra.voice.bakeoff")

SCRIPT = Path(__file__).with_name("script.txt")

# term -> spellings that count as heard. Lowercased; matched as whole phrases after normalising.
TERMS: dict[str, list[str]] = {
    "Prestige Motors": ["prestige motors"],
    "Honda CR-V": ["cr-v", "crv", "cr v", "c r v"],
    "Toyota Highlander": ["highlander"],
    "XLE": ["xle", "x l e"],
    "Lexus RX 350": ["rx 350", "rx350", "rx three fifty", "r x 350"],
    "Ford F-150": ["f-150", "f150", "f 150", "f one fifty"],
    "Adebayo": ["adebayo"],
    "Okonkwo": ["okonkwo"],
    "Chidinma": ["chidinma"],
    "Lagos": ["lagos"],
    "$25,100": ["25,100", "25100", "25 100", "twenty five thousand one hundred", "twenty-five thousand one hundred"],
    "$31,000": ["31,000", "31000", "31 thousand", "thirty one thousand", "thirty-one thousand"],
    "Saturday at 10": ["saturday at 10", "saturday at ten", "saturday 10", "saturday ten"],
    "trade-in": ["trade-in", "trade in", "tradein"],
    "financing": ["financing", "finance"],
    "oil change": ["oil change"],
}

KEYTERM_KEY = {"deepgram/": "keyterm", "assemblyai/": "keyterms_prompt", "openai/": "keywords"}


def shadow_models() -> list[str]:
    return [m.strip() for m in os.getenv("VOICE_STT_SHADOW", "").split(",") if m.strip()]


def _hints(model: str, vocabulary: list[str]) -> dict:
    """The same hints the live model gets, in the form each provider takes them."""
    for prefix, key in KEYTERM_KEY.items():
        if model.startswith(prefix) and vocabulary:
            return {key: vocabulary[:100]}
    return {}


@dataclass
class Shadow:
    """Listens to the caller with extra models. `heard` maps model -> final transcripts in order."""

    models: list[str]
    vocabulary: list[str]
    heard: dict[str, list[str]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    _task: asyncio.Task | None = None

    def start(self, participant) -> None:
        if self.models:
            self._task = asyncio.create_task(self._run(participant))

    async def _run(self, participant) -> None:
        from livekit import rtc
        from livekit.agents import inference, stt

        streams = {}
        for m in self.models:
            try:
                extra = _hints(m, self.vocabulary)
                streams[m] = inference.STT(model=m, language="en", **({"extra_kwargs": extra} if extra else {})).stream()
                self.heard[m] = []
            except Exception as e:  # noqa: BLE001 - a model the gateway doesn't know: note it, keep the others
                self.errors[m] = str(e)[:200]

        async def collect(m: str, s) -> None:
            try:
                async for ev in s:
                    if ev.type == stt.SpeechEventType.FINAL_TRANSCRIPT and ev.alternatives and ev.alternatives[0].text.strip():
                        self.heard[m].append(ev.alternatives[0].text.strip())
            except Exception as e:  # noqa: BLE001 - one listening model failing must never touch the call
                self.errors[m] = str(e)[:200]

        readers = [asyncio.create_task(collect(m, s)) for m, s in streams.items()]
        audio = rtc.AudioStream.from_participant(participant=participant, track_source=rtc.TrackSource.SOURCE_MICROPHONE,
                                                 sample_rate=16000)
        try:
            async for ev in audio:
                for s in streams.values():
                    s.push_frame(ev.frame)
        finally:
            for s in streams.values():
                with contextlib.suppress(Exception):
                    s.end_input()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(asyncio.gather(*readers), timeout=5)
            with contextlib.suppress(Exception):
                await audio.aclose()

    async def stop(self) -> dict:
        """End listening and return what each model heard, for the call record."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
        return {"models": self.heard, **({"errors": self.errors} if self.errors else {})}


# --- scoring -----------------------------------------------------------------------------------------------------

_NUMBER_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
    "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "oh",
}


def normalise(text: str) -> str:
    t = text.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9$,'\- ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def words(text: str) -> list[str]:
    """Words for the error rate: no punctuation, no numbers (digits or number words)."""
    out = []
    for w in re.sub(r"[^a-z0-9' ]+", " ", normalise(text).replace("-", " ")).split():
        if w.strip("'") and not any(ch.isdigit() for ch in w) and w not in _NUMBER_WORDS:
            out.append(w.strip("'"))
    return out


def wer(reference: list[str], hypothesis: list[str]) -> float:
    """Word error rate: (substitutions + deletions + insertions) / words in the reference."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    prev = list(range(len(hypothesis) + 1))
    for i, r in enumerate(reference, 1):
        cur = [i] + [0] * len(hypothesis)
        for j, h in enumerate(hypothesis, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(reference)


def terms_heard(text: str, terms: dict[str, list[str]] = TERMS) -> tuple[list[str], list[str]]:
    """Which key terms the transcript contains (by any accepted spelling), and which it missed."""
    t = f" {normalise(text)} "
    t_loose = f" {t.replace('-', ' ').replace(',', '')} "
    heard, missed = [], []
    for term, spellings in terms.items():
        ok = any(f" {s} " in t or f" {s.replace('-', ' ').replace(',', '')} " in t_loose for s in spellings)
        (heard if ok else missed).append(term)
    return heard, missed


def score(script: str, transcripts: dict[str, str]) -> list[dict]:
    """One row per model, best first: error rate against the script and key terms heard."""
    ref = words(script)
    expected = [t for t in TERMS if terms_heard(script)[0].count(t)]
    rows = []
    for model, text in transcripts.items():
        heard, _ = terms_heard(text)
        got = [t for t in expected if t in heard]
        rows.append({"model": model, "wer": round(wer(ref, words(text)), 3), "terms": f"{len(got)}/{len(expected)}",
                     "missed": [t for t in expected if t not in got], "words": len(words(text))})
    return sorted(rows, key=lambda r: (-int(r["terms"].split("/")[0]), r["wer"]))


# --- report --------------------------------------------------------------------------------------------------------

async def _load(call_id: str | None) -> tuple[str, dict[str, str]]:
    from ondra_api.db import no_tenant_session
    from sqlalchemy import text

    async with no_tenant_session() as db:  # reads across dealers on purpose: a developer tool, run by hand
        q = ("SELECT id, transcript, metrics FROM calls WHERE metrics ? 'stt_shadow' "
             + ("AND id = :id " if call_id else "") + "ORDER BY started_at DESC LIMIT 1")
        row = (await db.execute(text(q), {"id": call_id} if call_id else {})).first()
    if row is None:
        raise SystemExit("No call with shadow transcripts yet. Set VOICE_STT_SHADOW and make a call.")
    live = os.getenv("VOICE_STT_MODEL", "deepgram/nova-3")
    out = {f"{live} (live)": " ".join(t["text"] for t in (row.transcript or []) if t.get("who") == "caller")}
    for m, texts in ((row.metrics or {}).get("stt_shadow", {}).get("models") or {}).items():
        out[m] = " ".join(texts)
    return str(row.id), out


def main() -> None:
    p = argparse.ArgumentParser(description="Score speech-to-text models on a real call against the read-aloud script.")
    p.add_argument("--call", help="call id (default: the latest call with shadow transcripts)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    call_id, transcripts = asyncio.run(_load(a.call))
    rows = score(SCRIPT.read_text(), transcripts)
    if a.json:
        print(json.dumps({"call": call_id, "rows": rows}, indent=2))
        return
    print(f"Call {call_id}. Lower error rate is better; key terms are what the agent must hear right.\n")
    print(f"{'model':52} {'error rate':>10} {'key terms':>10}  missed")
    for r in rows:
        print(f"{r['model']:52} {r['wer']:>10.1%} {r['terms']:>10}  {', '.join(r['missed']) or '-'}")


if __name__ == "__main__":
    main()

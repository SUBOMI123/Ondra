"""The speech-to-text bake-off: shadow models hear the same caller audio, and are scored against the script."""

import asyncio
from types import SimpleNamespace

from livekit import rtc
from livekit.agents import inference, stt
from ondra_voice import bakeoff
from ondra_voice.bakeoff import SCRIPT, Shadow, score, terms_heard, wer, words


def test_word_error_rate_counts_substitutions_deletions_and_insertions():
    assert wer(["a", "b", "c", "d"], ["a", "b", "c", "d"]) == 0
    assert wer(["a", "b", "c", "d"], ["a", "x", "c"]) == 0.5  # one substituted, one dropped
    assert wer(["a", "b"], ["a", "b", "c", "d"]) == 1.0  # two inserted


def test_numbers_are_left_to_the_key_terms_and_spellings_count():
    assert words("It's $25,100, twenty five thousand.") == ["it's"]
    heard, missed = terms_heard("I want the CRV for 25100 and the F150, Saturday at 10")
    assert {"Honda CR-V", "$25,100", "Ford F-150", "Saturday at 10"} <= set(heard) and "Okonkwo" in missed


def test_the_script_names_every_term_and_a_mangled_transcript_scores_worse():
    s = SCRIPT.read_text()
    assert terms_heard(s)[1] == []
    bad = s.replace("Honda CR-V", "hunger series").replace("Okonkwo", "O'Connor")
    rows = score(s, {"good": s, "bad": bad})
    assert [r["model"] for r in rows] == ["good", "bad"]
    assert rows[1]["missed"] == ["Honda CR-V", "Okonkwo"] and rows[1]["wer"] > 0


def test_shadow_models_parse_from_the_environment(monkeypatch):
    monkeypatch.setenv("VOICE_STT_SHADOW", " assemblyai/u3-rt-pro, deepgram/nova-2-phonecall ,")
    assert bakeoff.shadow_models() == ["assemblyai/u3-rt-pro", "deepgram/nova-2-phonecall"]
    assert bakeoff._hints("deepgram/nova-2-phonecall", ["Honda CR-V"]) == {"keyterm": ["Honda CR-V"]}
    assert bakeoff._hints("assemblyai/u3-rt-pro", ["Honda CR-V"]) == {"keyterms_prompt": ["Honda CR-V"]}
    assert bakeoff._hints("cartesia/ink-2", ["Honda CR-V"]) == {}


class FakeStream:
    """Each frame pushed becomes one final transcript, '<model> frame <n>'."""

    def __init__(self, model):
        self.model, self.q, self.n = model, asyncio.Queue(), 0

    def push_frame(self, frame):
        self.n += 1
        alt = SimpleNamespace(text=f"{self.model} frame {self.n}")
        self.q.put_nowait(SimpleNamespace(type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[alt]))

    def end_input(self):
        self.q.put_nowait(None)

    def __aiter__(self):
        return self

    async def __anext__(self):
        ev = await self.q.get()
        if ev is None:
            raise StopAsyncIteration
        return ev


async def test_every_shadow_model_hears_the_same_frames_and_a_broken_one_is_noted(monkeypatch):
    hints = {}

    def fake_stt(model, language, extra_kwargs=None):
        if model == "nobody/unknown":
            raise ValueError("unknown model")
        hints[model] = extra_kwargs
        return SimpleNamespace(stream=lambda: FakeStream(model))

    class FakeAudio:
        def __init__(self):
            self.frames = [SimpleNamespace(frame=object()) for _ in range(3)]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.frames:
                await asyncio.sleep(3600)  # the call goes on until it's stopped
            return self.frames.pop(0)

        async def aclose(self):
            pass

    monkeypatch.setattr(inference, "STT", fake_stt)
    monkeypatch.setattr(rtc.AudioStream, "from_participant", classmethod(lambda cls, **kw: FakeAudio()))
    sh = Shadow(["deepgram/nova-2-phonecall", "assemblyai/u3-rt-pro", "nobody/unknown"], ["Honda CR-V"])
    sh.start(participant=object())
    await asyncio.sleep(0.05)
    out = await sh.stop()
    assert out["models"]["deepgram/nova-2-phonecall"] == [f"deepgram/nova-2-phonecall frame {i}" for i in (1, 2, 3)]
    assert len(out["models"]["assemblyai/u3-rt-pro"]) == 3
    assert "nobody/unknown" in out["errors"]
    assert hints["deepgram/nova-2-phonecall"] == {"keyterm": ["Honda CR-V"]}


def test_the_latency_report_finds_time_no_stage_owns():
    from ondra_voice.report import breakdown

    b = breakdown({"avg_ms": 3500, "p90_ms": 4100, "turns": 9, "avg_end_of_turn_ms": 700, "avg_llm_ttft_ms": 900,
                   "avg_tts_ttfb_ms": 300, "avg_tool_ms": None})
    assert b["unaccounted"] == 1600 and b["turns"] == 9

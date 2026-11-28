"""Turning a voice note into text, behind one interface (BUILD_PLAN.md §4.4: owner voice notes -> transcribe).

`MockTranscriber` is the default everywhere a real one isn't configured: it returns the transcript a test or the
mock channel attached, so the whole flow runs locally with no account.
"""

from __future__ import annotations

from typing import Protocol


class TranscriptionError(Exception):
    """The audio couldn't be turned into text. The owner is told, in words, and nothing is guessed."""


class Transcriber(Protocol):
    provider: str

    async def transcribe(self, audio: bytes, mime_type: str, *, hint: str | None = None) -> str: ...


class MockTranscriber:
    provider = "mock"

    async def transcribe(self, audio: bytes, mime_type: str, *, hint: str | None = None) -> str:
        if not hint:
            raise TranscriptionError("no transcript attached to this mock voice note")
        return hint

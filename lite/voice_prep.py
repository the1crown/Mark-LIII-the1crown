"""Phase-2 hooks for push-to-talk and text-to-speech.

Nothing here starts audio, polls a mic, or calls a model. The chat UI can
import these stubs and wire real STT/TTS later (reuse core/stt.py, core/tts.py,
or providers/stt_whisper.py + providers/tts_piper.py from the full app).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class VoiceHooks:
    """Optional callbacks the UI may set when voice is enabled in settings."""
    on_ptt_start: Optional[Callable[[], None]] = None
    on_ptt_stop: Optional[Callable[[], str]] = None   # returns transcript
    speak: Optional[Callable[[str], None]] = None


_hooks = VoiceHooks()


def get_hooks() -> VoiceHooks:
    return _hooks


def set_hooks(**kwargs) -> VoiceHooks:
    for k, v in kwargs.items():
        if hasattr(_hooks, k):
            setattr(_hooks, k, v)
    return _hooks


def push_to_talk_ready(settings: dict) -> bool:
    """True only when the user enabled PTT *and* a stop-hook is wired."""
    return bool(settings.get("push_to_talk_enabled")) and _hooks.on_ptt_stop is not None


def tts_ready(settings: dict) -> bool:
    return bool(settings.get("tts_enabled")) and _hooks.speak is not None


def maybe_speak(settings: dict, text: str) -> None:
    if tts_ready(settings) and text and _hooks.speak:
        try:
            _hooks.speak(text)
        except Exception:
            pass

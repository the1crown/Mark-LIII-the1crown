"""Natural Danish neural TTS via Microsoft Edge (no API key)."""
from __future__ import annotations

import asyncio
import re

# Male butler voice by default; Christel is the female alternative.
DEFAULT_VOICE = "da-DK-JeppeNeural"
ALT_VOICE = "da-DK-ChristelNeural"

_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    text = _TAG.sub("", text or "")
    text = " ".join(text.split())
    # Edge TTS is happier with shorter clauses; keep enough for natural prosody.
    return text[:1200]


def synthesize(text: str, voice: str | None = None) -> bytes:
    """Return MP3 bytes. Raises on failure."""
    cleaned = _clean(text)
    if not cleaned:
        return b""
    voice = voice or DEFAULT_VOICE

    async def _run() -> bytes:
        import edge_tts
        comm = edge_tts.Communicate(cleaned, voice=voice, rate="+0%", pitch="+0Hz")
        buf = bytearray()
        async for chunk in comm.stream():
            if chunk.get("type") == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # Already inside an event loop (unlikely here) — use a fresh loop.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()

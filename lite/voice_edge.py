"""Natural Danish neural TTS via Microsoft Edge (no API key).

Streams MP3 chunks as Edge produces them so the browser can start
playing before the full utterance is ready.
"""
from __future__ import annotations

import asyncio
import hashlib
import queue
import re
import threading
from collections import OrderedDict
from typing import Iterator

DEFAULT_VOICE = "da-DK-JeppeNeural"
ALT_VOICE = "da-DK-ChristelNeural"

_TAG = re.compile(r"<[^>]+>")
_SENT = re.compile(r"(?<=[.!?…])\s+")

_MAX_SPEAK_CHARS = 220
_MAX_SENTENCES = 2

_cache_lock = threading.Lock()
_cache: OrderedDict[str, bytes] = OrderedDict()
_CACHE_MAX = 24


def _clean(text: str) -> str:
    text = _TAG.sub("", text or "")
    return " ".join(text.split())


def speakable(text: str) -> str:
    """Shorten text for TTS — full reply stays in the chat UI."""
    text = _clean(text)
    if not text:
        return ""
    parts = _SENT.split(text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.append(p if p[-1] in ".!?…" else p + ".")
        joined = " ".join(out)
        if len(out) >= _MAX_SENTENCES or len(joined) >= _MAX_SPEAK_CHARS:
            return joined[:_MAX_SPEAK_CHARS].rstrip()
    return text[:_MAX_SPEAK_CHARS].rstrip()


def _cache_key(text: str, voice: str) -> str:
    return hashlib.sha1(f"{voice}\n{text}".encode("utf-8")).hexdigest()


def _cache_get(key: str) -> bytes | None:
    with _cache_lock:
        val = _cache.get(key)
        if val is not None:
            _cache.move_to_end(key)
        return val


def _cache_put(key: str, data: bytes) -> None:
    if not data:
        return
    with _cache_lock:
        _cache[key] = data
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


async def _edge_chunks(text: str, voice: str):
    import edge_tts
    comm = edge_tts.Communicate(text, voice=voice, rate="+10%", pitch="+0Hz")
    async for chunk in comm.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            yield chunk["data"]


def iter_mp3(text: str, voice: str | None = None) -> Iterator[bytes]:
    """Yield MP3 bytes as soon as Edge produces them (live stream)."""
    cleaned = speakable(text)
    if not cleaned:
        return
    voice = voice or DEFAULT_VOICE
    key = _cache_key(cleaned, voice)
    cached = _cache_get(key)
    if cached:
        yield cached
        return

    q: queue.Queue[bytes | None] = queue.Queue()
    buf = bytearray()
    err: list[BaseException] = []

    def _worker() -> None:
        try:
            async def _run() -> None:
                async for c in _edge_chunks(cleaned, voice):
                    q.put(c)

            try:
                asyncio.run(_run())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(_run())
                finally:
                    loop.close()
        except BaseException as e:
            err.append(e)
        finally:
            q.put(None)

    threading.Thread(target=_worker, daemon=True, name="edge-tts").start()
    while True:
        item = q.get()
        if item is None:
            break
        buf.extend(item)
        yield item
    if err:
        raise err[0]
    _cache_put(key, bytes(buf))


def synthesize(text: str, voice: str | None = None) -> bytes:
    return b"".join(iter_mp3(text, voice=voice))


def warmup(voice: str | None = None) -> None:
    try:
        synthesize("Klar.", voice=voice)
    except Exception:
        pass

"""Thin chat backends: Ollama (local) and OpenAI (cloud). Idle = zero network."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from .router import Route


@dataclass
class ChatResult:
    content: str
    model: str
    backend: str
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    tokens_estimated: bool
    error: str | None = None


def _estimate_tokens(text: str) -> int:
    # Rough EN/DA heuristic (~4 chars/token). Marked estimated in the UI.
    return max(1, (len(text) + 3) // 4) if text else 0


def chat(route: Route, messages: list[dict[str, str]],
         max_tokens: int = 180, timeout: int = 120) -> ChatResult:
    t0 = time.perf_counter()
    try:
        if route.backend in ("openai", "mistral"):
            return _openai_compat(route, messages, max_tokens, timeout, t0)
        return _ollama(route, messages, max_tokens, timeout, t0)
    except requests.exceptions.ConnectionError:
        return ChatResult(
            content="", model=route.model, backend=route.backend,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            prompt_tokens=None, completion_tokens=None, tokens_estimated=True,
            error=f"Cannot reach {route.backend} at {route.base_url}",
        )
    except Exception as e:
        return ChatResult(
            content="", model=route.model, backend=route.backend,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            prompt_tokens=None, completion_tokens=None, tokens_estimated=True,
            error=str(e),
        )


def _ollama(route: Route, messages: list[dict[str, str]],
            max_tokens: int, timeout: int, t0: float) -> ChatResult:
    payload: dict[str, Any] = {
        "model": route.model,
        "messages": messages,
        "stream": False,
        "keep_alive": -1,  # keep model hot — cold loads feel multi-second
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.3,
            "num_ctx": 2048,  # smaller context = faster on CPU
        },
    }
    resp = requests.post(f"{route.base_url}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    msg = data.get("message") or {}
    content = (msg.get("content") or "").strip()
    prompt_t = data.get("prompt_eval_count")
    comp_t = data.get("eval_count")
    estimated = prompt_t is None or comp_t is None
    if estimated:
        prompt_t = _estimate_tokens("".join(m.get("content", "") for m in messages))
        comp_t = _estimate_tokens(content)
    return ChatResult(
        content=content,
        model=data.get("model") or route.model,
        backend="ollama",
        latency_ms=int((time.perf_counter() - t0) * 1000),
        prompt_tokens=int(prompt_t) if prompt_t is not None else None,
        completion_tokens=int(comp_t) if comp_t is not None else None,
        tokens_estimated=estimated,
    )


def _openai_compat(route: Route, messages: list[dict[str, str]],
                   max_tokens: int, timeout: int, t0: float) -> ChatResult:
    """OpenAI + Mistral (and similar) share /chat/completions."""
    headers = {
        "Authorization": f"Bearer {route.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": route.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    resp = requests.post(
        f"{route.base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    content = ((choice.get("message") or {}).get("content") or "").strip()
    usage = data.get("usage") or {}
    prompt_t = usage.get("prompt_tokens")
    comp_t = usage.get("completion_tokens")
    estimated = prompt_t is None or comp_t is None
    if estimated:
        prompt_t = _estimate_tokens("".join(m.get("content", "") for m in messages))
        comp_t = _estimate_tokens(content)
    return ChatResult(
        content=content,
        model=data.get("model") or route.model,
        backend=route.backend,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        prompt_tokens=int(prompt_t) if prompt_t is not None else None,
        completion_tokens=int(comp_t) if comp_t is not None else None,
        tokens_estimated=estimated,
    )


def ping_ollama(base_url: str, timeout: float = 3.0) -> bool:
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False

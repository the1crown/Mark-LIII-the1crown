"""Fixed model-selection rules — no extra AI call.

Cloud is never chosen automatically. The user enables cloud and picks the
provider in settings (or the chat toolbar). Local Ollama is the default.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Route:
    backend: str          # "ollama" | "openai"
    model: str
    base_url: str
    api_key: str
    reason: str


def choose_route(settings: dict[str, Any], secrets: dict[str, str],
                 force_backend: str | None = None) -> Route:
    """Pick backend from explicit user settings only.

    force_backend: optional one-shot override from the UI ("ollama" / "openai").
    """
    want = (force_backend or "").strip().lower()
    cloud_on = bool(settings.get("cloud_enabled"))
    provider = str(settings.get("cloud_provider") or "openai").strip().lower()

    use_cloud = want == "openai" or (want != "ollama" and cloud_on and provider == "openai")

    if use_cloud:
        key = (secrets.get("OPENAI_API_KEY") or "").strip()
        if not key and want == "openai":
            # Explicit cloud choice without a key → fall back with a clear reason.
            return Route(
                backend="ollama",
                model=str(settings.get("local_model") or "qwen2.5:3b"),
                base_url=str(settings.get("ollama_url") or "http://127.0.0.1:11434"),
                api_key="",
                reason="cloud requested but OPENAI_API_KEY missing → local",
            )
        if key:
            return Route(
                backend="openai",
                model=str(settings.get("cloud_model") or "gpt-4o-mini"),
                base_url=str(settings.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/"),
                api_key=key,
                reason="manual cloud (OpenAI)",
            )

    return Route(
        backend="ollama",
        model=str(settings.get("local_model") or "qwen2.5:3b"),
        base_url=str(settings.get("ollama_url") or "http://127.0.0.1:11434").rstrip("/"),
        api_key="",
        reason="local default (Ollama)",
    )

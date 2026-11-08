"""Fixed model-selection rules — no extra AI call.

Cloud is never chosen automatically. The user enables cloud and picks the
provider in settings (or the chat toolbar). Local Ollama is the default.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Route:
    backend: str          # "ollama" | "openai" | "mistral"
    model: str
    base_url: str
    api_key: str
    reason: str


def _local(settings: dict[str, Any], reason: str) -> Route:
    return Route(
        backend="ollama",
        model=str(settings.get("local_model") or "qwen2.5:3b"),
        base_url=str(settings.get("ollama_url") or "http://127.0.0.1:11434").rstrip("/"),
        api_key="",
        reason=reason,
    )


def choose_route(settings: dict[str, Any], secrets: dict[str, str],
                 force_backend: str | None = None) -> Route:
    """Pick backend from explicit user settings only.

    force_backend: optional override ("ollama" / "openai" / "mistral" / "auto").
    """
    want = (force_backend or "").strip().lower()
    if want in ("", "auto"):
        want = ""

    cloud_on = bool(settings.get("cloud_enabled"))
    provider = str(settings.get("cloud_provider") or "openai").strip().lower()

    # Explicit force wins; else cloud only when manually enabled.
    if want == "ollama":
        return _local(settings, "forced local (Ollama)")

    target = want if want in ("openai", "mistral") else (provider if cloud_on else "")

    if target == "openai":
        key = (secrets.get("OPENAI_API_KEY") or "").strip()
        if not key:
            return _local(settings, "OpenAI requested but OPENAI_API_KEY missing → local")
        return Route(
            backend="openai",
            model=str(settings.get("cloud_model") or "gpt-4o-mini"),
            base_url=str(settings.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/"),
            api_key=key,
            reason="manual cloud (OpenAI)",
        )

    if target == "mistral":
        key = (secrets.get("MISTRAL_API_KEY") or "").strip()
        if not key:
            return _local(settings, "Mistral requested but MISTRAL_API_KEY missing → local")
        return Route(
            backend="mistral",
            model=str(settings.get("mistral_model") or "mistral-small-latest"),
            base_url=str(settings.get("mistral_base_url") or "https://api.mistral.ai/v1").rstrip("/"),
            api_key=key,
            reason="manual cloud (Mistral)",
        )

    return _local(settings, "local default (Ollama)")

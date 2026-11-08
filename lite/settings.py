"""Local settings + secrets outside source code.

Non-secret prefs → config/lite_settings.json
Secrets → .env (never committed; see .env.example)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).resolve().parent.parent

SETTINGS_PATH = ROOT / "config" / "lite_settings.json"
ENV_PATH = ROOT / ".env"

# Defaults tuned for Intel i7-8565U / 16 GB: small Q4 local model, tight caps.
DEFAULTS: dict[str, Any] = {
    "assistant_name": "JARVIS",
    "cloud_enabled": False,
    "cloud_provider": "openai",  # openai | mistral — only when cloud_enabled
    "local_model": "qwen2.5:3b",
    "cloud_model": "gpt-4o-mini",
    "mistral_model": "mistral-small-latest",
    "mistral_document_model": "mistral-small-latest",
    "mistral_ocr_model": "mistral-ocr-latest",
    "ollama_url": "http://127.0.0.1:11434",
    "openai_base_url": "https://api.openai.com/v1",
    "mistral_base_url": "https://api.mistral.ai/v1",
    "max_output_tokens": 180,
    "max_history_turns": 6,
    "max_context_chars": 6000,
    "system_prompt": (
        "You are a concise desktop assistant. Answer in few sentences. "
        "Prefer Danish if the user writes Danish. Do not invent tool results."
    ),
    # Voice: browser mic + Edge neural TTS (no cloud key).
    "push_to_talk_enabled": True,
    "tts_enabled": True,
    "tts_voice": "da-DK-JeppeNeural",  # or da-DK-ChristelNeural
}

SECRET_KEYS = ("OPENAI_API_KEY", "MISTRAL_API_KEY")


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def load_env() -> dict[str, str]:
    """Merge process env over .env file. Does not invent missing keys."""
    file_vals = _parse_env_file(ENV_PATH)
    merged = dict(file_vals)
    for k in SECRET_KEYS:
        if os.environ.get(k):
            merged[k] = os.environ[k]
    return merged


def get_secret(name: str) -> str:
    return (load_env().get(name) or "").strip()


def load_settings() -> dict[str, Any]:
    data = dict(DEFAULTS)
    if SETTINGS_PATH.is_file():
        try:
            stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                data.update({k: stored[k] for k in DEFAULTS if k in stored})
        except (OSError, json.JSONDecodeError):
            pass
    return data


def save_settings(updates: dict[str, Any]) -> dict[str, Any]:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = load_settings()
    for k, v in updates.items():
        if k in DEFAULTS:
            data[k] = v
    SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def truncate_text(text: str, max_chars: int) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    keep = max(0, max_chars - 20)
    return text[:keep] + "\n…[truncated]"

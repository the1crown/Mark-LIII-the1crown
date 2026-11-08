"""Conversation session: short history, no idle polling, no agent loops."""
from __future__ import annotations

from typing import Any

from . import providers, router, settings as S
from .tools import registry


class Session:
    def __init__(self) -> None:
        self.settings = S.load_settings()
        self.secrets = S.load_env()
        self.history: list[dict[str, str]] = []
        self.last_meta: dict[str, Any] = {}
        self.force_backend: str | None = None

    def reload(self) -> None:
        self.settings = S.load_settings()
        self.secrets = S.load_env()

    def clear(self) -> None:
        self.history.clear()
        self.last_meta = {}

    def _build_messages(self, user_text: str) -> list[dict[str, str]]:
        max_turns = int(self.settings.get("max_history_turns") or 6)
        max_chars = int(self.settings.get("max_context_chars") or 6000)
        system = str(self.settings.get("system_prompt") or "")
        tool_hint = registry.system_hint()
        if tool_hint:
            system = f"{system}\n\n{tool_hint}".strip()

        msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
        # Keep only the last N user/assistant pairs.
        tail = self.history[-(max_turns * 2):]
        for m in tail:
            msgs.append({"role": m["role"], "content": S.truncate_text(m["content"], max_chars // 4)})
        msgs.append({"role": "user", "content": S.truncate_text(user_text, max_chars // 2)})

        # Soft budget on total context size.
        total = sum(len(m["content"]) for m in msgs)
        while total > max_chars and len(msgs) > 2:
            # Drop oldest non-system message.
            dropped = msgs.pop(1)
            total -= len(dropped["content"])
        return msgs

    def ask(self, user_text: str) -> str:
        """One user turn → one model call. No background work afterwards."""
        user_text = (user_text or "").strip()
        if not user_text:
            return ""

        # Local tool shortcut (no model): /tool name args…
        if user_text.startswith("/"):
            out = registry.try_slash(user_text, confirm_ui=True)
            if out is not None:
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": out})
                self.last_meta = {
                    "model": "tool",
                    "backend": "local",
                    "latency_ms": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "tokens_estimated": False,
                    "route_reason": "slash command",
                }
                return out

        self.reload()
        route = router.choose_route(self.settings, self.secrets, self.force_backend)
        messages = self._build_messages(user_text)
        max_out = int(self.settings.get("max_output_tokens") or 180)
        result = providers.chat(route, messages, max_tokens=max_out)

        if result.error:
            reply = f"Error: {result.error}"
        else:
            reply = result.content or "(empty reply)"

        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        # Trim stored history.
        max_turns = int(self.settings.get("max_history_turns") or 6)
        self.history = self.history[-(max_turns * 2):]

        self.last_meta = {
            "model": result.model,
            "backend": result.backend,
            "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "tokens_estimated": result.tokens_estimated,
            "route_reason": route.reason,
        }
        return reply

    def format_meta(self) -> str:
        m = self.last_meta
        if not m:
            return ""
        est = " ~est" if m.get("tokens_estimated") else ""
        pt = m.get("prompt_tokens")
        ct = m.get("completion_tokens")
        tok = f"in={pt} out={ct}{est}" if pt is not None else f"tokens n/a{est}"
        return (
            f"{m.get('backend')}:{m.get('model')} · {tok} · "
            f"{m.get('latency_ms')} ms · {m.get('route_reason')}"
        )

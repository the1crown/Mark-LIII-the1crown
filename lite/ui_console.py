"""Console chat fallback when Tk is unavailable (e.g. headless CI)."""
from __future__ import annotations

from .session import Session


def run() -> None:
    session = Session()
    name = session.settings.get("assistant_name") or "JARVIS"
    print(f"{name} lite console. /help for tools, :quit to exit, :clear to reset.")
    print("Default backend: local Ollama. Enable cloud in config/lite_settings.json + .env")
    while True:
        try:
            line = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in (":quit", ":exit", "quit", "exit"):
            break
        if line == ":clear":
            session.clear()
            print("(cleared)")
            continue
        if line.startswith(":backend "):
            b = line.split(None, 1)[1].strip().lower()
            session.force_backend = None if b == "auto" else b
            print(f"backend={session.force_backend or 'auto'}")
            continue
        reply = session.ask(line)
        print(f"Assistant> {reply}")
        meta = session.format_meta()
        if meta:
            print(f"[{meta}]")
    print("Bye — no background tasks left running.")

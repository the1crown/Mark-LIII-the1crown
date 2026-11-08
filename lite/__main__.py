"""Entry: python -m lite"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="JARVIS lite text chat (Ollama + optional OpenAI)")
    p.add_argument("--console", action="store_true", help="Force console UI")
    p.add_argument("--check", action="store_true", help="Sanity-check imports and exit")
    args = p.parse_args(argv)

    if args.check:
        from . import providers, router, session, settings, voice_prep  # noqa: F401
        from .tools import registry  # noqa: F401
        print("lite OK")
        return 0

    if not args.console:
        try:
            from .ui_tk import run
            run()
            return 0
        except Exception as e:
            print(f"Tk UI unavailable ({e}); falling back to console.", file=sys.stderr)

    from .ui_console import run
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

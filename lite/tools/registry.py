"""Bounded computer tools. Mutations require explicit user confirmation."""
from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]

# UI may replace this with a dialog; default is stdin (console).
_confirm_fn: Callable[[str], bool] | None = None


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    mutating: bool
    run: Callable[[str], str]


def set_confirm(fn: Callable[[str], bool] | None) -> None:
    global _confirm_fn
    _confirm_fn = fn


def _confirm(prompt: str) -> bool:
    if _confirm_fn is not None:
        try:
            return bool(_confirm_fn(prompt))
        except Exception:
            return False
    try:
        ans = input(f"{prompt} [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def tool_time(_: str) -> str:
    # Prefer Copenhagen for this user; fall back to UTC label if zoneinfo missing.
    try:
        now = datetime.now(ZoneInfo("Europe/Copenhagen"))
        label = "Europe/Copenhagen"
    except Exception:
        now = datetime.now(timezone.utc)
        label = "UTC"
    return f"{now.strftime('%Y-%m-%d %H:%M:%S')} ({label})"


def tool_sysinfo(_: str) -> str:
    return (
        f"OS={platform.system()} {platform.release()} | "
        f"machine={platform.machine()} | python={platform.python_version()}"
    )


def tool_list_dir(args: str) -> str:
    raw = (args or ".").strip() or "."
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    # Stay inside the project or cwd tree — no arbitrary traversal helpers.
    try:
        path.relative_to(ROOT)
        allowed = True
    except ValueError:
        try:
            path.relative_to(Path.cwd().resolve())
            allowed = True
        except ValueError:
            allowed = False
    if not allowed:
        return "Refused: path is outside the project and current working directory."
    if not path.exists():
        return f"Not found: {path}"
    if not path.is_dir():
        return f"Not a directory: {path}"
    names = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())[:80]
    return f"{path}\n" + ("\n".join(names) if names else "(empty)")


def tool_read_file(args: str) -> str:
    parts = (args or "").strip().split(maxsplit=1)
    if not parts:
        return "Usage: /read <path> [max_chars]"
    path = Path(parts[0]).expanduser()
    max_chars = 4000
    if len(parts) > 1:
        try:
            max_chars = max(200, min(20000, int(parts[1])))
        except ValueError:
            pass
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        try:
            path.relative_to(Path.cwd().resolve())
        except ValueError:
            return "Refused: path is outside the project and current working directory."
    if not path.is_file():
        return f"Not a file: {path}"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"Read failed: {e}"
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…[truncated]"
    return text


def tool_write_note(args: str) -> str:
    text = (args or "").strip()
    if not text:
        return "Usage: /note <text>"
    out_dir = ROOT / "config" / "lite_notes"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "notes.txt"
    if not _confirm(f"Append note to {path}?"):
        return "Cancelled — nothing written."
    with path.open("a", encoding="utf-8") as f:
        f.write(datetime.now().isoformat(timespec="seconds") + " — " + text + "\n")
    return f"Appended to {path}"


def tool_disk(_: str) -> str:
    usage = shutil.disk_usage(str(ROOT))
    gb = 1024 ** 3
    return f"disk free={usage.free / gb:.1f} GB / total={usage.total / gb:.1f} GB (project volume)"


TOOLS: dict[str, Tool] = {
    "time": Tool("time", "Current local time", False, tool_time),
    "sys": Tool("sys", "Brief system info", False, tool_sysinfo),
    "ls": Tool("ls", "List a directory under project/cwd", False, tool_list_dir),
    "read": Tool("read", "Read a text file excerpt under project/cwd", False, tool_read_file),
    "note": Tool("note", "Append a note (asks for confirmation)", True, tool_write_note),
    "disk": Tool("disk", "Disk free space", False, tool_disk),
}


def system_hint() -> str:
    lines = ["Slash tools (no model):"]
    for t in TOOLS.values():
        flag = " [needs confirm]" if t.mutating else ""
        lines.append(f"  /{t.name} — {t.description}{flag}")
    return "\n".join(lines)


def try_slash(text: str, confirm_ui: bool = True) -> str | None:
    raw = text.strip()
    if not raw.startswith("/"):
        return None
    body = raw[1:].strip()
    if not body:
        return "Available: " + ", ".join(f"/{n}" for n in TOOLS)
    name, _, args = body.partition(" ")
    name = name.lower()
    if name in ("help", "?"):
        return system_hint()
    tool = TOOLS.get(name)
    if not tool:
        return f"Unknown tool /{name}. Try /help"
    try:
        return tool.run(args)
    except Exception as e:
        return f"Tool /{name} failed: {e}"

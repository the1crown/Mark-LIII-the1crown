"""Simple Tk chat UI. No timers, no background LLM calls."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import settings as S
from .session import Session
from .tools import registry
from .voice_prep import maybe_speak


class ChatApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.session = Session()
        name = self.session.settings.get("assistant_name") or "JARVIS"
        self.title(f"{name} — lite chat")
        self.geometry("720x520")
        self.minsize(480, 360)

        self._busy = False
        registry.set_confirm(lambda prompt: messagebox.askyesno("Confirm", prompt))
        self._build()
        self._refresh_status("Ready — local Ollama by default. No idle network use.")

    def _build(self) -> None:
        top = ttk.Frame(self, padding=6)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Backend").pack(side=tk.LEFT)
        self.backend_var = tk.StringVar(value="auto")
        backend = ttk.Combobox(
            top, textvariable=self.backend_var, width=10, state="readonly",
            values=("auto", "ollama", "openai", "mistral"),
        )
        backend.pack(side=tk.LEFT, padx=(4, 12))
        backend.bind("<<ComboboxSelected>>", self._on_backend)

        self.cloud_var = tk.BooleanVar(value=bool(self.session.settings.get("cloud_enabled")))
        ttk.Checkbutton(
            top, text="Cloud enabled", variable=self.cloud_var, command=self._toggle_cloud,
        ).pack(side=tk.LEFT)

        ttk.Button(top, text="Clear", command=self._clear).pack(side=tk.RIGHT)
        ttk.Button(top, text="Settings", command=self._edit_settings).pack(side=tk.RIGHT, padx=4)

        self.meta = ttk.Label(self, text="", foreground="#555")
        self.meta.pack(fill=tk.X, padx=8)

        self.log = tk.Text(self, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 10))
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        bottom = ttk.Frame(self, padding=6)
        bottom.pack(fill=tk.X)
        self.entry = ttk.Entry(bottom)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", lambda _e: self._send())
        ttk.Button(bottom, text="Send", command=self._send).pack(side=tk.LEFT, padx=(6, 0))
        # Phase-2: PTT button placeholder (disabled until voice hooks are wired).
        self.ptt_btn = ttk.Button(bottom, text="PTT", state=tk.DISABLED)
        self.ptt_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.status = ttk.Label(self, text="", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

        self.entry.focus_set()

    def _on_backend(self, _event=None) -> None:
        v = self.backend_var.get()
        self.session.force_backend = None if v == "auto" else v
        self._refresh_status(f"Backend override: {v}")

    def _toggle_cloud(self) -> None:
        S.save_settings({"cloud_enabled": bool(self.cloud_var.get())})
        self.session.reload()
        state = "ON" if self.cloud_var.get() else "OFF"
        self._refresh_status(f"Cloud {state} (manual). Keys stay in .env")

    def _clear(self) -> None:
        self.session.clear()
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.meta.configure(text="")
        self._refresh_status("History cleared.")

    def _edit_settings(self) -> None:
        s = self.session.settings
        win = tk.Toplevel(self)
        win.title("Lite settings")
        win.grab_set()
        fields = [
            ("local_model", "Local model"),
            ("cloud_model", "Cloud model"),
            ("ollama_url", "Ollama URL"),
            ("openai_base_url", "OpenAI base URL"),
            ("max_output_tokens", "Max output tokens"),
            ("max_history_turns", "Max history turns"),
        ]
        vars_: dict[str, tk.StringVar] = {}
        for i, (key, label) in enumerate(fields):
            ttk.Label(win, text=label).grid(row=i, column=0, sticky=tk.W, padx=6, pady=3)
            var = tk.StringVar(value=str(s.get(key, "")))
            vars_[key] = var
            ttk.Entry(win, textvariable=var, width=42).grid(row=i, column=1, padx=6, pady=3)

        def save() -> None:
            updates = {}
            for key, var in vars_.items():
                raw = var.get().strip()
                if key.startswith("max_"):
                    try:
                        updates[key] = int(raw)
                    except ValueError:
                        messagebox.showerror("Settings", f"{key} must be an integer")
                        return
                else:
                    updates[key] = raw
            S.save_settings(updates)
            self.session.reload()
            win.destroy()
            self._refresh_status("Settings saved to config/lite_settings.json")

        ttk.Button(win, text="Save", command=save).grid(row=len(fields), column=1, sticky=tk.E, padx=6, pady=8)

    def _append(self, who: str, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"{who}: {text}\n\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _refresh_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _send(self) -> None:
        if self._busy:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, tk.END)
        self._append("You", text)

        # Slash tools stay on the UI thread (confirmation dialogs need it).
        if text.startswith("/"):
            reply = self.session.ask(text)
            self._done(reply, self.session.format_meta())
            return

        self._busy = True
        self._refresh_status("Thinking…")

        def work() -> None:
            reply = self.session.ask(text)
            meta = self.session.format_meta()
            self.after(0, lambda: self._done(reply, meta))

        threading.Thread(target=work, daemon=True, name="lite-chat").start()

    def _done(self, reply: str, meta: str) -> None:
        self._busy = False
        self._append("Assistant", reply)
        self.meta.configure(text=meta)
        self._refresh_status("Idle — no background AI calls.")
        maybe_speak(self.session.settings, reply)


def run() -> None:
    app = ChatApp()
    app.mainloop()

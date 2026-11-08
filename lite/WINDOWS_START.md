# Windows start — JARVIS lite (text chat)

For an Intel i7-8565U / 16 GB machine. Local-first, low token use, no idle AI calls.

## 1. Install Python 3.11+

From https://www.python.org/downloads/ — tick **Add python.exe to PATH**.

## 2. Install Ollama

1. Download from https://ollama.com/download and install.
2. Open PowerShell and pull a small model that fits this PC:

```powershell
ollama pull qwen2.5:3b
```

(`phi3:mini` or `llama3.2:3b` also work. Prefer 3B Q4-class models.)

## 3. Project setup

```powershell
cd path\to\Mark-LIII-the1crown
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install requests
copy .env.example .env
```

Edit `.env` only if you want cloud (OpenAI). Leave the key empty for local-only.

## 4. Run the lite chat

```powershell
python -m lite
```

Use `--console` if the window UI fails:

```powershell
python -m lite --console
```

## 5. Cloud (optional, manual)

1. Put `OPENAI_API_KEY=sk-...` in `.env`.
2. In the UI tick **Cloud enabled**, or set `"cloud_enabled": true` in `config/lite_settings.json`.
3. Pick backend **openai** in the toolbar (or leave **auto** once cloud is enabled).

Cloud is never chosen automatically without that switch.

## Notes

- Settings (non-secret): `config/lite_settings.json`
- Secrets: `.env` only
- Status line shows model, tokens, latency (`~est` = estimated)
- Slash tools: `/help` — mutating tools ask for confirmation
- Push-to-talk / TTS: hooks in `lite/voice_prep.py` (next phase; off by default)
- Full voice HUD remains `python main.py` / the existing app

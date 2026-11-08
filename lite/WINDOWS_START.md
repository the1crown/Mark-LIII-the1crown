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

## 4. Run the lite chat (tale)

Double-click `start-lite.bat`, or:

```powershell
python -m lite --web
```

Open **Chrome or Edge**: http://127.0.0.1:7860  
Allow the microphone → press **Tryk for at tale** (or hold Space) → hear the reply.  
Leave **Oplæs svar** and **Bliv ved med at lytte** checked for a continuous talk loop.

Desktop window:

```powershell
python -m lite
```

Console fallback:

```powershell
python -m lite --console
```

## 5. Voice (browser)

On http://127.0.0.1:7860 use **Tale** (mic) and tick **Oplæs**.
Uses the browser Web Speech API (Chrome/Edge) — no API key required.

## 6. Cloud (optional, manual)

1. Copy `.env.example` → `.env` and set `OPENAI_API_KEY` and/or `MISTRAL_API_KEY`.
2. Set `"cloud_enabled": true` and `"cloud_provider": "openai"` or `"mistral"` in `config/lite_settings.json`.
3. Or force backend in the Tk toolbar / `:backend mistral` in console.

Cloud is never chosen automatically without that switch.

## Notes

- Settings (non-secret): `config/lite_settings.json`
- Secrets: `.env` only
- Status line shows model, tokens, latency (`~est` = estimated)
- Slash tools: `/help` — mutating tools ask for confirmation
- Push-to-talk / TTS: hooks in `lite/voice_prep.py` (next phase; off by default)
- Full voice HUD remains `python main.py` / the existing app

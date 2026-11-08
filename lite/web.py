"""Jarvis-style localhost HUD with model-colored themes. No idle AI calls."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .session import Session

HOST = "127.0.0.1"
PORT = 7860
_session = Session()
_lock = threading.Lock()

_HTML = r"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>J.A.R.V.I.S.</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Share+Tech+Mono&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg0: #03080f;
    --bg1: #07101c;
    --text: #d7f3ff;
    --muted: #6f93a8;
    --accent: #1ec8ff;
    --accent-dim: rgba(30,200,255,.18);
    --hot: #ff3b4a;
    --ring: var(--accent);
  }
  /* Model themes — whole HUD retints */
  body.theme-ollama {
    --accent: #3dd68c;
    --accent-dim: rgba(61,214,140,.18);
    --text: #d9ffe8;
    --muted: #6fa88a;
  }
  body.theme-mistral {
    --accent: #ff8a3d;
    --accent-dim: rgba(255,138,61,.18);
    --text: #ffe8d7;
    --muted: #a88a6f;
  }
  body.theme-openai {
    --accent: #6ea8ff;
    --accent-dim: rgba(110,168,255,.18);
    --text: #e0eaff;
    --muted: #7a8fad;
  }
  body.theme-local, body.theme-tool {
    --accent: #b08cff;
    --accent-dim: rgba(176,140,255,.18);
    --text: #eee6ff;
    --muted: #8f7aad;
  }

  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0;
    color: var(--text);
    font-family: "Share Tech Mono", ui-monospace, monospace;
    background:
      radial-gradient(ellipse 80% 55% at 50% 0%, var(--accent-dim), transparent 55%),
      linear-gradient(180deg, var(--bg1), var(--bg0));
    display: grid;
    grid-template-rows: auto 1fr auto;
    overflow: hidden;
    transition: background .45s ease, color .45s ease;
  }
  body::before {
    content: "";
    position: fixed; inset: 0; pointer-events: none; opacity: .08;
    background: repeating-linear-gradient(
      0deg, transparent, transparent 2px, rgba(255,255,255,.04) 3px
    );
  }

  .top {
    display: flex; align-items: center; gap: 16px;
    padding: 14px 20px;
    border-bottom: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
  }
  .brand {
    font-family: Orbitron, sans-serif;
    font-weight: 700;
    font-size: clamp(22px, 4vw, 34px);
    letter-spacing: .18em;
    color: var(--accent);
    text-shadow: 0 0 18px color-mix(in srgb, var(--accent) 55%, transparent);
    margin: 0;
  }
  .brand small {
    display: block;
    font-size: 10px;
    letter-spacing: .35em;
    color: var(--muted);
    font-weight: 500;
    margin-top: 2px;
  }
  .chip {
    margin-left: auto;
    border: 1px solid color-mix(in srgb, var(--accent) 50%, transparent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--accent);
    padding: 6px 12px;
    font-size: 12px;
    letter-spacing: .08em;
    text-transform: uppercase;
    transition: border-color .35s, background .35s, color .35s;
  }
  #status { color: var(--muted); font-size: 12px; letter-spacing: .06em; }

  .stage {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(220px, 320px);
    gap: 12px;
    padding: 12px 16px;
    min-height: 0;
  }
  @media (max-width: 820px) {
    .stage { grid-template-columns: 1fr; }
    .orb-wrap { display: none; }
  }

  #log {
    overflow: auto;
    padding: 8px 4px 8px 0;
    display: flex; flex-direction: column; gap: 10px;
    mask-image: linear-gradient(180deg, transparent, #000 12px, #000 calc(100% - 12px), transparent);
  }
  .msg {
    max-width: 720px;
    white-space: pre-wrap;
    border: 1px solid color-mix(in srgb, var(--accent) 25%, transparent);
    background: color-mix(in srgb, var(--accent) 7%, #050b14);
    padding: 10px 12px;
    line-height: 1.45;
  }
  .msg.you {
    align-self: flex-end;
    border-color: color-mix(in srgb, var(--accent) 55%, transparent);
  }
  .msg.bot { align-self: flex-start; }
  .msg .who {
    font-family: Orbitron, sans-serif;
    font-size: 10px;
    letter-spacing: .16em;
    color: var(--accent);
    margin-bottom: 4px;
  }
  .meta { font-size: 11px; color: var(--muted); margin-top: 6px; }

  .orb-wrap {
    display: grid; place-items: center;
    border: 1px solid color-mix(in srgb, var(--accent) 28%, transparent);
    background: radial-gradient(circle at 50% 45%, var(--accent-dim), transparent 60%);
  }
  .orb {
    width: min(240px, 70%);
    aspect-ratio: 1;
    border-radius: 50%;
    border: 2px solid var(--accent);
    box-shadow:
      0 0 0 8px color-mix(in srgb, var(--accent) 10%, transparent),
      0 0 40px color-mix(in srgb, var(--accent) 35%, transparent) inset;
    position: relative;
    transition: border-color .35s, box-shadow .35s;
  }
  .orb::before, .orb::after {
    content: "";
    position: absolute; inset: 12%;
    border-radius: 50%;
    border: 1px dashed color-mix(in srgb, var(--accent) 55%, transparent);
    animation: spin 18s linear infinite;
  }
  .orb::after { inset: 24%; animation-direction: reverse; animation-duration: 12s; }
  .orb.listening {
    animation: pulse 1.1s ease-in-out infinite;
  }
  .orb.thinking .core { animation: blink 0.7s steps(2) infinite; }
  .orb.speaking {
    box-shadow:
      0 0 0 10px color-mix(in srgb, var(--accent) 16%, transparent),
      0 0 55px color-mix(in srgb, var(--accent) 55%, transparent) inset;
  }
  .core {
    position: absolute; inset: 38%;
    border-radius: 50%;
    background: var(--accent);
    opacity: .85;
    filter: blur(1px);
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.04); opacity: .85; }
  }
  @keyframes blink { 50% { opacity: .25; } }

  .dock {
    padding: 14px 16px 16px;
    border-top: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
    display: flex; flex-direction: column; gap: 10px;
    background: color-mix(in srgb, var(--bg0) 80%, transparent);
  }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  input[type=text] {
    flex: 1; min-width: 160px;
    background: #050b14;
    border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
    color: var(--text);
    border-radius: 0;
    padding: 10px 12px;
    font: inherit;
  }
  input[type=text]:focus { outline: 1px solid var(--accent); }
  button {
    background: color-mix(in srgb, var(--accent) 18%, #071018);
    color: var(--accent);
    border: 1px solid var(--accent);
    border-radius: 0;
    padding: 10px 14px;
    cursor: pointer;
    font: inherit;
    letter-spacing: .08em;
    text-transform: uppercase;
  }
  button:disabled { opacity: .45; cursor: wait; }
  #talk {
    width: 100%; height: 64px; font-size: 16px;
    font-family: Orbitron, sans-serif; letter-spacing: .14em;
  }
  #talk.hot {
    background: color-mix(in srgb, var(--hot) 25%, #14060a);
    border-color: var(--hot); color: #ffd0d4;
  }
  label.chk { font-size: 12px; color: var(--muted); display: flex; gap: 6px; align-items: center; }
  .hint { font-size: 11px; color: var(--muted); text-align: center; letter-spacing: .04em; }
  .legend { display: flex; gap: 10px; flex-wrap: wrap; font-size: 10px; color: var(--muted); }
  .legend i {
    display: inline-block; width: 8px; height: 8px; margin-right: 4px;
    vertical-align: middle;
  }
  .legend .l-ollama { background: #3dd68c; }
  .legend .l-mistral { background: #ff8a3d; }
  .legend .l-openai { background: #6ea8ff; }
  .legend .l-local { background: #b08cff; }
</style>
</head>
<body class="theme-mistral">
  <header class="top">
    <h1 class="brand">JARVIS<small>JUST A RATHER VERY INTELLIGENT SYSTEM</small></h1>
    <div id="status">STANDBY</div>
    <div class="chip" id="modelChip">MODEL · —</div>
  </header>

  <main class="stage">
    <div id="log" aria-live="polite"></div>
    <aside class="orb-wrap" aria-hidden="true">
      <div class="orb" id="orb"><div class="core"></div></div>
    </aside>
  </main>

  <div class="dock">
    <button id="talk" type="button">Engage voice</button>
    <div class="row">
      <label class="chk"><input type="checkbox" id="tts" checked/> Speak replies</label>
      <label class="chk"><input type="checkbox" id="cont" checked/> Keep listening</label>
      <div class="legend">
        <span><i class="l-ollama"></i>Ollama</span>
        <span><i class="l-mistral"></i>Mistral</span>
        <span><i class="l-openai"></i>OpenAI</span>
        <span><i class="l-local"></i>Tool/local</span>
      </div>
    </div>
    <form id="f" class="row">
      <input id="q" type="text" autocomplete="off" placeholder="Type a command…"/>
      <button id="go" type="submit">Send</button>
    </form>
    <div class="hint">Hold Space to talk · allow microphone · HUD color follows active model</div>
  </div>

<script>
const log = document.getElementById('log');
const f = document.getElementById('f');
const q = document.getElementById('q');
const go = document.getElementById('go');
const talk = document.getElementById('talk');
const ttsOn = document.getElementById('tts');
const contOn = document.getElementById('cont');
const statusEl = document.getElementById('status');
const modelChip = document.getElementById('modelChip');
const orb = document.getElementById('orb');
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizing = false;
let busy = false;
let rec = null;

function setStatus(t) { statusEl.textContent = t; }

function applyTheme(backend, model) {
  const b = (backend || 'mistral').toLowerCase();
  document.body.className = 'theme-' + (
    b === 'ollama' ? 'ollama' :
    b === 'mistral' ? 'mistral' :
    b === 'openai' ? 'openai' :
    (b === 'local' || b === 'tool') ? 'local' : 'mistral'
  );
  modelChip.textContent = 'MODEL · ' + ((model || b || '—') + '').toUpperCase();
}

function setOrb(mode) {
  orb.classList.remove('listening', 'thinking', 'speaking');
  if (mode) orb.classList.add(mode);
}

function add(role, text, meta) {
  const d = document.createElement('div');
  d.className = 'msg ' + (role === 'you' ? 'you' : 'bot');
  const who = document.createElement('div');
  who.className = 'who';
  who.textContent = role === 'you' ? 'SIR' : 'JARVIS';
  d.appendChild(who);
  d.appendChild(document.createTextNode(text));
  if (meta) {
    const m = document.createElement('div');
    m.className = 'meta';
    m.textContent = meta;
    d.appendChild(m);
  }
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function speak(text) {
  return new Promise((resolve) => {
    if (!ttsOn.checked || !window.speechSynthesis || !text) { resolve(); return; }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'da-DK';
    u.rate = 1.02;
    u.onend = () => resolve();
    u.onerror = () => resolve();
    setStatus('SPEAKING');
    setOrb('speaking');
    window.speechSynthesis.speak(u);
  });
}

function startListen() {
  if (!rec || recognizing || busy) return;
  recognizing = true;
  talk.classList.add('hot');
  talk.textContent = 'Listening…';
  setStatus('LISTENING');
  setOrb('listening');
  try { rec.start(); } catch (e) {
    recognizing = false;
    talk.classList.remove('hot');
    talk.textContent = 'Engage voice';
    setStatus('STANDBY');
    setOrb(null);
  }
}

function stopListen() {
  if (!rec || !recognizing) return;
  try { rec.stop(); } catch (e) {}
}

async function sendText(text, fromVoice) {
  text = (text || '').trim();
  if (!text || busy) return;
  busy = true;
  talk.disabled = true;
  go.disabled = true;
  add('you', text);
  setStatus('THINKING');
  setOrb('thinking');
  let reply = '';
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await r.json();
    reply = data.reply || data.error || '(empty)';
    const info = data.info || {};
    applyTheme(info.backend, info.model);
    add('bot', reply, data.meta || '');
    await speak(reply);
  } catch (err) {
    add('bot', 'Link failure: ' + err);
  } finally {
    busy = false;
    talk.disabled = false;
    go.disabled = false;
    talk.classList.remove('hot');
    talk.textContent = 'Engage voice';
    setStatus('STANDBY');
    setOrb(null);
    if (fromVoice && contOn.checked && ttsOn.checked) {
      setTimeout(startListen, 280);
    } else {
      q.focus();
    }
  }
}

f.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = q.value.trim();
  q.value = '';
  await sendText(text, false);
});

talk.addEventListener('click', () => {
  if (busy) return;
  if (recognizing) stopListen();
  else startListen();
});

window.addEventListener('keydown', (e) => {
  if (e.code !== 'Space' || e.repeat) return;
  if (document.activeElement === q) return;
  e.preventDefault();
  if (busy) return;
  if (!recognizing) startListen();
});
window.addEventListener('keyup', (e) => {
  if (e.code !== 'Space') return;
  if (document.activeElement === q) return;
  if (recognizing) stopListen();
});

fetch('/api/health').then(r => r.json()).then(h => {
  const provider = (h.preferred || (h.cloud_keys && h.cloud_keys.mistral ? 'mistral' : 'ollama'));
  applyTheme(provider, h.model || provider);
}).catch(() => {});

if (SR) {
  rec = new SR();
  rec.lang = 'da-DK';
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  let finalText = '';
  rec.onstart = () => { finalText = ''; };
  rec.onresult = (ev) => {
    let interim = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finalText += t;
      else interim += t;
    }
    q.value = (finalText || interim).trim();
  };
  rec.onerror = () => {
    recognizing = false;
    talk.classList.remove('hot');
    talk.textContent = 'Engage voice';
    setStatus('STANDBY');
    setOrb(null);
  };
  rec.onend = () => {
    recognizing = false;
    talk.classList.remove('hot');
    talk.textContent = 'Engage voice';
    const t = (finalText || q.value || '').trim();
    q.value = '';
    if (t) sendText(t, true);
    else { setStatus('STANDBY'); setOrb(null); }
  };
  add('bot', 'Systems online. Hold Space or press Engage voice — I am standing by.');
} else {
  talk.disabled = true;
  talk.textContent = 'Voice needs Chrome/Edge';
  setStatus('NO MIC API');
  add('bot', 'Voice API unavailable. Type instead — Chrome or Edge recommended.');
}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[lite-web] {args[0]}" if args else f"[lite-web] {fmt}")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = _HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/health":
            _session.reload()
            s = _session.settings
            preferred = "mistral" if (
                s.get("cloud_enabled") and str(s.get("cloud_provider") or "") == "mistral"
                and (_session.secrets.get("MISTRAL_API_KEY") or "").strip()
            ) else (
                "openai" if (
                    s.get("cloud_enabled") and str(s.get("cloud_provider") or "") == "openai"
                    and (_session.secrets.get("OPENAI_API_KEY") or "").strip()
                ) else "ollama"
            )
            model = {
                "mistral": s.get("mistral_model"),
                "openai": s.get("cloud_model"),
                "ollama": s.get("local_model"),
            }.get(preferred, s.get("local_model"))
            self._json(200, {
                "ok": True, "host": HOST, "port": PORT,
                "voice": "browser-web-speech",
                "preferred": preferred,
                "model": model,
                "cloud_keys": {
                    "openai": bool((_session.secrets.get("OPENAI_API_KEY") or "").strip()),
                    "mistral": bool((_session.secrets.get("MISTRAL_API_KEY") or "").strip()),
                },
            })
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/chat":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        msg = str(data.get("message") or "").strip()
        if not msg:
            self._json(400, {"error": "empty message"})
            return
        with _lock:
            _session.reload()
            reply = _session.ask(msg)
            meta = _session.format_meta()
            info = dict(_session.last_meta or {})
        self._json(200, {"reply": reply, "meta": meta, "info": info})


def run(host: str = HOST, port: int = PORT) -> None:
    global HOST, PORT
    HOST, PORT = host, port
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"JARVIS lite web: http://{host}:{port}")
    print("HUD color follows model (ollama/mistral/openai). Ctrl+C stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()

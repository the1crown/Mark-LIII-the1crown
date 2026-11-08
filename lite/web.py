"""Minimal localhost web chat with talk-first voice loop. No idle AI calls."""
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

_HTML = """<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>JARVIS lite</title>
<style>
  :root { --bg:#0f1419; --panel:#1a222c; --text:#e7ecf1; --muted:#8b98a5; --accent:#3d8bfd; --hot:#c44; --ok:#2f9e44; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.45 "Segoe UI", system-ui, sans-serif; background:var(--bg); color:var(--text); height:100vh; display:flex; flex-direction:column; }
  header { padding:12px 16px; background:var(--panel); border-bottom:1px solid #243040; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; font-weight:600; }
  header span, #status { color:var(--muted); font-size:12px; }
  #status { margin-left:auto; }
  #log { flex:1; overflow:auto; padding:16px; display:flex; flex-direction:column; gap:10px; }
  .msg { max-width:720px; white-space:pre-wrap; }
  .msg.you { align-self:flex-end; background:#243447; padding:10px 12px; border-radius:12px 12px 4px 12px; }
  .msg.bot { align-self:flex-start; background:var(--panel); padding:10px 12px; border-radius:12px 12px 12px 4px; }
  .meta { font-size:11px; color:var(--muted); margin-top:4px; }
  .dock { padding:16px; background:var(--panel); border-top:1px solid #243040; display:flex; flex-direction:column; gap:10px; }
  .row { display:flex; gap:8px; align-items:center; }
  input[type=text] { flex:1; background:#0f1419; border:1px solid #314155; color:var(--text); border-radius:8px; padding:10px 12px; }
  button { background:var(--accent); color:#fff; border:0; border-radius:8px; padding:10px 14px; cursor:pointer; font-weight:600; }
  button:disabled { opacity:.5; cursor:wait; }
  #talk {
    width:100%; height:72px; font-size:20px; border-radius:14px; background:#2a3544;
  }
  #talk.hot { background:var(--hot); }
  #talk.busy { background:#3a4555; }
  label.chk { font-size:12px; color:var(--muted); display:flex; gap:6px; align-items:center; white-space:nowrap; }
  .hint { font-size:12px; color:var(--muted); text-align:center; }
</style>
</head>
<body>
<header>
  <h1>JARVIS lite</h1>
  <span>Tal med systemet · Chrome/Edge · mellemrum = tale</span>
  <div id="status">Klar</div>
</header>
<div id="log"></div>
<div class="dock">
  <button id="talk" type="button">🎤 Tryk for at tale</button>
  <div class="row">
    <label class="chk"><input type="checkbox" id="tts" checked/> Oplæs svar</label>
    <label class="chk"><input type="checkbox" id="cont" checked/> Bliv ved med at lytte</label>
  </div>
  <form id="f" class="row">
    <input id="q" type="text" autocomplete="off" placeholder="Eller skriv her…"/>
    <button id="go" type="submit">Send</button>
  </form>
  <div class="hint">Tillad mikrofon når browseren spørger. Ingen AI-kald mens du er stille.</div>
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
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizing = false;
let busy = false;
let rec = null;

function setStatus(t) { statusEl.textContent = t; }

function add(role, text, meta) {
  const d = document.createElement('div');
  d.className = 'msg ' + (role === 'you' ? 'you' : 'bot');
  d.textContent = text;
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
    u.rate = 1.05;
    u.onend = () => resolve();
    u.onerror = () => resolve();
    setStatus('Taler…');
    window.speechSynthesis.speak(u);
  });
}

function startListen() {
  if (!rec || recognizing || busy) return;
  recognizing = true;
  talk.classList.add('hot');
  talk.textContent = '● Lytter… (klik for at stoppe)';
  setStatus('Lytter…');
  try { rec.start(); } catch (e) {
    recognizing = false;
    talk.classList.remove('hot');
    talk.textContent = '🎤 Tryk for at tale';
    setStatus('Klar');
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
  talk.classList.add('busy');
  talk.disabled = true;
  go.disabled = true;
  add('you', text);
  setStatus('Tænker…');
  let reply = '';
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await r.json();
    reply = data.reply || data.error || '(tom)';
    add('bot', reply, data.meta || '');
    await speak(reply);
  } catch (err) {
    add('bot', 'Netværksfejl: ' + err);
  } finally {
    busy = false;
    talk.disabled = false;
    talk.classList.remove('busy');
    go.disabled = false;
    talk.textContent = '🎤 Tryk for at tale';
    setStatus('Klar');
    if (fromVoice && contOn.checked && ttsOn.checked) {
      setTimeout(startListen, 250);
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
    talk.textContent = '🎤 Tryk for at tale';
    setStatus('Klar');
  };
  rec.onend = () => {
    recognizing = false;
    talk.classList.remove('hot');
    talk.textContent = '🎤 Tryk for at tale';
    const t = (finalText || q.value || '').trim();
    q.value = '';
    if (t) sendText(t, true);
    else setStatus('Klar');
  };
  add('bot', 'Hej — tryk på knappen eller hold mellemrum nede, og tal. Jeg svarer højt.');
} else {
  talk.disabled = true;
  talk.textContent = 'Tale kræver Chrome eller Edge';
  setStatus('Ingen mikrofon-API');
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
            # refresh secrets each health check so .env edits apply without full restart
            _session.reload()
            self._json(200, {
                "ok": True, "host": HOST, "port": PORT,
                "voice": "browser-web-speech",
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
        self._json(200, {"reply": reply, "meta": meta})


def run(host: str = HOST, port: int = PORT) -> None:
    global HOST, PORT
    HOST, PORT = host, port
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"JARVIS lite web: http://{host}:{port}")
    print("Tale: tryk knap / hold mellemrum. Oplæsning i browser. Ctrl+C stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()

"""Minimal localhost web chat with browser mic/TTS. No idle AI calls."""
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
  :root { --bg:#0f1419; --panel:#1a222c; --text:#e7ecf1; --muted:#8b98a5; --accent:#3d8bfd; --hot:#c44; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.45 "Segoe UI", system-ui, sans-serif; background:var(--bg); color:var(--text); height:100vh; display:flex; flex-direction:column; }
  header { padding:12px 16px; background:var(--panel); border-bottom:1px solid #243040; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; font-weight:600; letter-spacing:.02em; }
  header span { color:var(--muted); font-size:12px; }
  #log { flex:1; overflow:auto; padding:16px; display:flex; flex-direction:column; gap:10px; }
  .msg { max-width:720px; white-space:pre-wrap; }
  .msg.you { align-self:flex-end; background:#243447; padding:10px 12px; border-radius:12px 12px 4px 12px; }
  .msg.bot { align-self:flex-start; background:var(--panel); padding:10px 12px; border-radius:12px 12px 12px 4px; }
  .meta { font-size:11px; color:var(--muted); margin-top:4px; }
  form { display:flex; gap:8px; padding:12px; background:var(--panel); border-top:1px solid #243040; align-items:center; }
  input[type=text] { flex:1; background:#0f1419; border:1px solid #314155; color:var(--text); border-radius:8px; padding:10px 12px; }
  button { background:var(--accent); color:#fff; border:0; border-radius:8px; padding:10px 14px; cursor:pointer; font-weight:600; }
  button:disabled { opacity:.5; cursor:wait; }
  button.ptt { background:#2a3544; min-width:88px; }
  button.ptt.hot { background:var(--hot); }
  label.chk { font-size:12px; color:var(--muted); display:flex; gap:6px; align-items:center; white-space:nowrap; }
</style>
</head>
<body>
<header>
  <h1>JARVIS lite</h1>
  <span>http://127.0.0.1:7860 · tale via browser · ingen idle-kald</span>
  <label class="chk"><input type="checkbox" id="tts" checked/> Oplæs</label>
</header>
<div id="log"></div>
<form id="f">
  <button class="ptt" type="button" id="ptt" title="Hold inde / klik for at tale">🎤 Tale</button>
  <input id="q" type="text" autocomplete="off" placeholder="Skriv her… eller brug Tale (/help)" autofocus/>
  <button id="go" type="submit">Send</button>
</form>
<script>
const log = document.getElementById('log');
const f = document.getElementById('f');
const q = document.getElementById('q');
const go = document.getElementById('go');
const ptt = document.getElementById('ptt');
const ttsOn = document.getElementById('tts');
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizing = false;
let rec = null;

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
  if (!ttsOn.checked || !window.speechSynthesis || !text) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'da-DK';
  u.rate = 1.05;
  window.speechSynthesis.speak(u);
}

async function sendText(text) {
  text = (text || '').trim();
  if (!text) return;
  add('you', text);
  go.disabled = true;
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await r.json();
    const reply = data.reply || data.error || '(tom)';
    add('bot', reply, data.meta || '');
    speak(reply);
  } catch (err) {
    add('bot', 'Netværksfejl: ' + err);
  } finally {
    go.disabled = false;
    q.focus();
  }
}

f.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = q.value.trim();
  q.value = '';
  await sendText(text);
});

if (SR) {
  rec = new SR();
  rec.lang = 'da-DK';
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  rec.onresult = (ev) => {
    const t = ev.results[0][0].transcript;
    q.value = t;
    sendText(t);
  };
  rec.onerror = () => { recognizing = false; ptt.classList.remove('hot'); ptt.textContent = '🎤 Tale'; };
  rec.onend = () => { recognizing = false; ptt.classList.remove('hot'); ptt.textContent = '🎤 Tale'; };
  ptt.addEventListener('click', () => {
    if (recognizing) { rec.stop(); return; }
    recognizing = true;
    ptt.classList.add('hot');
    ptt.textContent = '● …';
    try { rec.start(); } catch (e) { recognizing = false; ptt.classList.remove('hot'); }
  });
} else {
  ptt.disabled = true;
  ptt.title = 'Tale understøttes ikke i denne browser (prøv Chrome/Edge)';
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
    print("Tale/oplæsning: browser Web Speech API (Chrome/Edge). Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()

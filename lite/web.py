"""Minimal localhost web chat. No background polling — only talks to the model on Send."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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
  :root { --bg:#0f1419; --panel:#1a222c; --text:#e7ecf1; --muted:#8b98a5; --accent:#3d8bfd; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.45 "Segoe UI", system-ui, sans-serif; background:var(--bg); color:var(--text); height:100vh; display:flex; flex-direction:column; }
  header { padding:12px 16px; background:var(--panel); border-bottom:1px solid #243040; display:flex; gap:12px; align-items:center; }
  header h1 { font-size:16px; margin:0; font-weight:600; letter-spacing:.02em; }
  header span { color:var(--muted); font-size:12px; }
  #log { flex:1; overflow:auto; padding:16px; display:flex; flex-direction:column; gap:10px; }
  .msg { max-width:720px; white-space:pre-wrap; }
  .msg.you { align-self:flex-end; background:#243447; padding:10px 12px; border-radius:12px 12px 4px 12px; }
  .msg.bot { align-self:flex-start; background:var(--panel); padding:10px 12px; border-radius:12px 12px 12px 4px; }
  .meta { font-size:11px; color:var(--muted); margin-top:4px; }
  form { display:flex; gap:8px; padding:12px; background:var(--panel); border-top:1px solid #243040; }
  input { flex:1; background:#0f1419; border:1px solid #314155; color:var(--text); border-radius:8px; padding:10px 12px; }
  button { background:var(--accent); color:#fff; border:0; border-radius:8px; padding:10px 16px; cursor:pointer; font-weight:600; }
  button:disabled { opacity:.5; cursor:wait; }
</style>
</head>
<body>
<header>
  <h1>JARVIS lite</h1>
  <span>http://127.0.0.1:7860 · lokal Ollama · ingen idle-kald</span>
</header>
<div id="log"></div>
<form id="f">
  <input id="q" autocomplete="off" placeholder="Skriv her… (/help for værktøjer)" autofocus/>
  <button id="go" type="submit">Send</button>
</form>
<script>
const log = document.getElementById('log');
const f = document.getElementById('f');
const q = document.getElementById('q');
const go = document.getElementById('go');
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
f.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = q.value.trim();
  if (!text) return;
  q.value = '';
  add('you', text);
  go.disabled = true;
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await r.json();
    add('bot', data.reply || data.error || '(tom)', data.meta || '');
  } catch (err) {
    add('bot', 'Netværksfejl: ' + err);
  } finally {
    go.disabled = false;
    q.focus();
  }
});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
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
            self._json(200, {"ok": True, "host": HOST, "port": PORT})
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
            reply = _session.ask(msg)
            meta = _session.format_meta()
        self._json(200, {"reply": reply, "meta": meta})


def run(host: str = HOST, port: int = PORT) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"JARVIS lite web: http://{host}:{port}")
    print("Ctrl+C to stop. No idle AI calls.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()

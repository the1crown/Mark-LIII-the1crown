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
    margin-left: 0;
    border: 1px solid color-mix(in srgb, var(--accent) 50%, transparent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    color: var(--accent);
    padding: 6px 12px;
    font-size: 12px;
    letter-spacing: .08em;
    text-transform: uppercase;
    transition: border-color .35s, background .35s, color .35s;
  }
  .backend {
    margin-left: auto;
    display: flex; align-items: center; gap: 8px;
    color: var(--muted); font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  }
  .backend select {
    background: #050b14; color: var(--accent);
    border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
    padding: 6px 8px; font: inherit; letter-spacing: .04em;
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
  .heard {
    padding: 8px 20px; font-size: 13px; letter-spacing: .04em;
    color: var(--accent);
    border-bottom: 1px solid color-mix(in srgb, var(--accent) 25%, transparent);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
    min-height: 34px;
  }
  .heard[hidden] { display: none; }
</style>
</head>
<body class="theme-mistral">
  <header class="top">
    <h1 class="brand">JARVIS<small>JUST A RATHER VERY INTELLIGENT SYSTEM</small></h1>
    <div id="status">STANDBY</div>
    <label class="backend">
      Motor
      <select id="backend">
        <option value="ollama">Lokal (Ollama)</option>
        <option value="mistral">Cloud (Mistral)</option>
        <option value="openai">Cloud (OpenAI)</option>
      </select>
    </label>
    <div class="chip" id="modelChip">MODEL · —</div>
  </header>
  <div id="diag" class="heard">Tjekker system…</div>
  <div id="heard" class="heard" hidden></div>

  <main class="stage">
    <div id="log" aria-live="polite"></div>
    <aside class="orb-wrap" aria-hidden="true">
      <div class="orb" id="orb"><div class="core"></div></div>
    </aside>
  </main>

  <div class="dock">
    <button id="talk" type="button">Start samtale</button>
    <div class="row">
      <label class="chk"><input type="checkbox" id="tts" checked/> Oplæs svar</label>
      <div class="legend">
        <span><i class="l-ollama"></i>Ollama</span>
        <span><i class="l-mistral"></i>Mistral</span>
        <span><i class="l-openai"></i>OpenAI</span>
        <span><i class="l-local"></i>Tool/local</span>
      </div>
    </div>
    <form id="f" class="row">
      <input id="q" type="text" autocomplete="off" placeholder="Eller skriv her midt i samtalen…"/>
      <button id="go" type="submit">Send</button>
    </form>
    <div class="hint">Samtale-mode: lyt → svar → lyt igen. Esc afbryder. Farve følger model.</div>
  </div>

<script>
const log = document.getElementById('log');
const f = document.getElementById('f');
const q = document.getElementById('q');
const go = document.getElementById('go');
const talk = document.getElementById('talk');
const ttsOn = document.getElementById('tts');
const statusEl = document.getElementById('status');
const modelChip = document.getElementById('modelChip');
const orb = document.getElementById('orb');
const heardEl = document.getElementById('heard');
const diagEl = document.getElementById('diag');
const backendSel = document.getElementById('backend');
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

let conversation = false;  // continuous talk loop
let recognizing = false;
let busy = false;
let rec = null;
let finalText = '';
let listenTimer = null;
let micStream = null;
let audioPlayer = null;
let ttsVoice = 'da-DK-JeppeNeural';
let forceBackend = 'ollama';

backendSel.addEventListener('change', () => {
  forceBackend = backendSel.value;
  const label = forceBackend === 'ollama' ? 'OLLAMA' : forceBackend.toUpperCase();
  applyTheme(forceBackend, label);
  setStatus('MOTOR · ' + label);
});

function setStatus(t) { statusEl.textContent = t; }

function applyTheme(backend, model) {
  const b = (backend || 'mistral').toLowerCase();
  const theme =
    b === 'ollama' ? 'ollama' :
    b === 'mistral' ? 'mistral' :
    b === 'openai' ? 'openai' :
    (b === 'local' || b === 'tool') ? 'local' : 'mistral';
  document.body.className = 'theme-' + theme;
  modelChip.textContent = 'MODEL · ' + ((model || b || '—') + '').toUpperCase();
}

function setOrb(mode) {
  orb.classList.remove('listening', 'thinking', 'speaking');
  if (mode) orb.classList.add(mode);
}

function updateTalkBtn() {
  if (!SR) {
    talk.disabled = true;
    talk.textContent = 'Tale kræver Chrome/Edge';
    return;
  }
  talk.disabled = false;
  if (conversation) {
    talk.classList.add('hot');
    talk.textContent = busy || recognizing ? 'Samtale aktiv · stop' : 'Stop samtale';
  } else {
    talk.classList.remove('hot');
    talk.textContent = 'Start samtale';
  }
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

function setHeard(text) {
  if (!text) { heardEl.hidden = true; heardEl.textContent = ''; return; }
  heardEl.hidden = false;
  heardEl.textContent = 'Hører: ' + text;
}

function cancelSpeech() {
  if (audioPlayer) {
    try { audioPlayer.pause(); audioPlayer.src = ''; } catch (e) {}
    audioPlayer = null;
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

function speakBrowser(text) {
  return new Promise((resolve) => {
    if (!window.speechSynthesis || !text) { resolve(); return; }
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'da-DK';
    u.rate = 1.0;
    u.onend = () => resolve();
    u.onerror = () => resolve();
    window.speechSynthesis.speak(u);
  });
}

async function speak(text) {
  if (!ttsOn.checked || !text) return;
  cancelSpeech();
  setStatus('SPEAKING');
  setOrb('speaking');
  try {
    const r = await fetch('/api/tts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text, voice: ttsVoice })
    });
    if (!r.ok) throw new Error('tts ' + r.status);
    const buf = await r.arrayBuffer();
    const blob = new Blob([buf], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    await new Promise((resolve, reject) => {
      const a = new Audio(url);
      audioPlayer = a;
      a.onended = () => { URL.revokeObjectURL(url); resolve(); };
      a.onerror = () => { URL.revokeObjectURL(url); reject(new Error('audio')); };
      a.play().catch(reject);
    });
  } catch (e) {
    // Fallback — still better than silence if Edge TTS is offline
    await speakBrowser(text);
  }
}

async function ensureMic() {
  if (micStream) return true;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    add('bot', 'Ingen mikrofon-adgang i denne browser.');
    return false;
  }
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });
    // Keep the track alive so Chrome grants SpeechRecognition reliably.
    return true;
  } catch (e) {
    add('bot', 'Mikrofon nægtet. Tillad mic for http://127.0.0.1:7860 i browseren, og prøv igen.');
    return false;
  }
}

function scheduleListen(delay) {
  clearTimeout(listenTimer);
  if (!conversation) return;
  listenTimer = setTimeout(() => startListen(), delay || 200);
}

function startListen() {
  if (!rec || !conversation || recognizing || busy) return;
  finalText = '';
  recognizing = true;
  updateTalkBtn();
  setStatus('LISTENING');
  setOrb('listening');
  try { rec.start(); }
  catch (e) {
    recognizing = false;
    // Chrome throws if started too soon — retry briefly while conversation is on
    scheduleListen(400);
  }
}

function stopListen() {
  if (!rec || !recognizing) return;
  try { rec.stop(); } catch (e) {}
}

function stopConversation() {
  conversation = false;
  clearTimeout(listenTimer);
  cancelSpeech();
  stopListen();
  recognizing = false;
  busy = false;
  go.disabled = false;
  setStatus('STANDBY');
  setOrb(null);
  updateTalkBtn();
}

async function startConversation() {
  if (!rec) return;
  const ok = await ensureMic();
  if (!ok) return;
  conversation = true;
  updateTalkBtn();
  add('bot', 'Samtale startet. Tal nu — du skal se «Hører: …» mens jeg lytter. Sig stop eller Esc for at afslutte.');
  startListen();
}

async function sendText(text, fromVoice) {
  text = (text || '').trim();
  if (!text || busy) return;

  // Voice command to end conversation
  const low = text.toLowerCase();
  if (fromVoice && /^(stop|stop samtale|afslut|farvel|godnat)\b/.test(low)) {
    add('you', text);
    add('bot', 'Samtale afsluttet. Klar når du er.');
    stopConversation();
    if (ttsOn.checked) await speak('Samtale afsluttet.');
    return;
  }

  busy = true;
  go.disabled = true;
  updateTalkBtn();
  add('you', text);
  setStatus('THINKING');
  setOrb('thinking');
  let reply = '';
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text, backend: forceBackend})
    });
    const data = await r.json();
    reply = data.reply || data.error || '(empty)';
    const info = data.info || {};
    applyTheme(info.backend, info.model);
    add('bot', reply, data.meta || '');
    await speak(reply);
  } catch (err) {
    add('bot', 'Forbindelsesfejl: ' + err);
  } finally {
    busy = false;
    go.disabled = false;
    updateTalkBtn();
    if (conversation) {
      setStatus('LISTENING');
      scheduleListen(280);
    } else {
      setStatus('STANDBY');
      setOrb(null);
      q.focus();
    }
  }
}

f.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = q.value.trim();
  q.value = '';
  // Typed lines also work during conversation mode
  if (recognizing) stopListen();
  await sendText(text, false);
});

talk.addEventListener('click', async () => {
  if (!SR) return;
  if (conversation) stopConversation();
  else await startConversation();
});

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (conversation) stopConversation();
    return;
  }
  if (e.code !== 'Space' || e.repeat) return;
  if (document.activeElement === q) return;
  e.preventDefault();
  if (!conversation) startConversation();
});

async function refreshDiag() {
  try {
    const r = await fetch('/api/diag');
    const d = await r.json();
    const parts = [];
    parts.push(d.ollama_ok ? 'Ollama OK' : 'Ollama FEJL — start Ollama / kør start-lite.bat');
    parts.push(d.model_ok ? ('Model ' + (d.model || '')) : ('Model mangler — ollama pull ' + (d.model || 'qwen2.5:3b')));
    parts.push(d.tts_ok ? 'TTS OK' : 'TTS mangler — pip install edge-tts');
    parts.push(SR ? 'Mic-API OK' : 'Mic-API mangler — brug Chrome/Edge');
    diagEl.textContent = parts.join(' · ');
    diagEl.style.color = (d.ollama_ok && d.model_ok) ? '' : '#ff8a3d';
    if (d.preferred) {
      forceBackend = d.preferred;
      if (['ollama','mistral','openai'].includes(d.preferred)) backendSel.value = d.preferred;
      applyTheme(forceBackend, d.model || forceBackend);
    }
    if (d.tts_voice) ttsVoice = d.tts_voice;
  } catch (e) {
    diagEl.textContent = 'Kan ikke nå serveren på http://127.0.0.1:7860 — kør start-lite.bat på denne PC.';
    diagEl.style.color = '#ff8a3d';
  }
}
refreshDiag();

if (SR) {
  rec = new SR();
  rec.lang = 'da-DK';
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;

  rec.onstart = () => {
    finalText = '';
    setHeard('…');
    setStatus('LISTENING');
    setOrb('listening');
  };

  rec.onresult = (ev) => {
    let interim = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finalText += t;
      else interim += t;
    }
    const shown = (finalText || interim).trim();
    q.value = shown;
    setHeard(shown || '…');
  };

  rec.onerror = (ev) => {
    recognizing = false;
    const err = (ev && ev.error) || '';
    if (err === 'not-allowed') {
      add('bot', 'Mikrofon blokeret. Klik på lås/info i adresselinjen og tillad mikrofon.');
      stopConversation();
      return;
    }
    if (conversation && (err === 'no-speech' || err === 'aborted' || err === 'network' || err === 'audio-capture')) {
      scheduleListen(400);
      return;
    }
    if (!conversation) {
      setStatus('STANDBY');
      setOrb(null);
      setHeard('');
      updateTalkBtn();
    }
  };

  rec.onend = () => {
    recognizing = false;
    const t = (finalText || q.value || '').trim();
    q.value = '';
    finalText = '';
    setHeard('');
    if (!conversation) {
      updateTalkBtn();
      setStatus('STANDBY');
      setOrb(null);
      return;
    }
    if (t) sendText(t, true);
    else scheduleListen(250);
  };

  updateTalkBtn();
  add('bot', 'Systems online. Tryk Start samtale, tillad mikrofon, og tal. Stemmen er neural (Edge). Esc stopper.');
} else {
  updateTalkBtn();
  setStatus('NO MIC API');
  add('bot', 'Tale-API mangler. Brug Chrome eller Edge på Windows.');
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
        if path in ("/api/health", "/api/diag"):
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
            from . import providers
            ollama_url = str(s.get("ollama_url") or "http://127.0.0.1:11434")
            ollama_ok = providers.ping_ollama(ollama_url)
            model_ok = False
            if ollama_ok:
                try:
                    import requests as _rq
                    tags = _rq.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=3).json()
                    names = [m.get("name", "") for m in tags.get("models") or []]
                    want = str(s.get("local_model") or "qwen2.5:3b")
                    base = want.split(":")[0]
                    model_ok = any(
                        n == want or n == base or n.startswith(base + ":") for n in names
                    )
                except Exception:
                    model_ok = False
            tts_ok = False
            try:
                import importlib.util
                tts_ok = importlib.util.find_spec("edge_tts") is not None
            except Exception:
                tts_ok = False
            self._json(200, {
                "ok": True, "host": HOST, "port": PORT,
                "voice": "edge-neural",
                "tts_voice": s.get("tts_voice") or "da-DK-JeppeNeural",
                "preferred": preferred,
                "model": model if preferred != "ollama" else (s.get("local_model") or model),
                "ollama_ok": ollama_ok,
                "model_ok": model_ok,
                "tts_ok": tts_ok,
                "cloud_keys": {
                    "openai": bool((_session.secrets.get("OPENAI_API_KEY") or "").strip()),
                    "mistral": bool((_session.secrets.get("MISTRAL_API_KEY") or "").strip()),
                },
            })
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return

        if path == "/api/tts":
            text = str(data.get("text") or "").strip()
            if not text:
                self._json(400, {"error": "empty text"})
                return
            voice = str(data.get("voice") or "").strip() or None
            try:
                from .voice_edge import synthesize
                _session.reload()
                if not voice:
                    voice = str(_session.settings.get("tts_voice") or "") or None
                mp3 = synthesize(text, voice=voice)
            except Exception as e:
                self._json(500, {"error": f"tts failed: {e}"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(mp3)))
            self.end_headers()
            self.wfile.write(mp3)
            return

        if path != "/api/chat":
            self._json(404, {"error": "not found"})
            return
        msg = str(data.get("message") or "").strip()
        if not msg:
            self._json(400, {"error": "empty message"})
            return
        backend = str(data.get("backend") or "").strip().lower() or None
        if backend == "auto":
            backend = None
        with _lock:
            _session.reload()
            _session.force_backend = backend
            reply = _session.ask(msg)
            meta = _session.format_meta()
            info = dict(_session.last_meta or {})
        self._json(200, {"reply": reply, "meta": meta, "info": info})


def run(host: str = HOST, port: int = PORT) -> None:
    global HOST, PORT
    HOST, PORT = host, port
    # Warm local model so the first spoken turn is not a cold load.
    try:
        from . import providers
        from . import router
        _session.reload()
        route = router.choose_route(_session.settings, _session.secrets, "ollama")
        if providers.ping_ollama(route.base_url):
            print(f"[lite-web] Warming {route.model}…")
            providers.chat(
                route,
                [{"role": "user", "content": "hi"}],
                max_tokens=1,
                timeout=180,
            )
            print("[lite-web] Local model ready.")
    except Exception as e:
        print(f"[lite-web] Warmup skipped: {e}")

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"JARVIS lite web: http://{host}:{port}")
    print("Default motor: Lokal (Ollama). HUD color follows model. Ctrl+C stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()

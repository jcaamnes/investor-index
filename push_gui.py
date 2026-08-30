"""Stocks Elite — desktop price updater (local web GUI).

Opens a little page in your browser with one button. Click "Update Prices" and
it fetches today's Yahoo closes for the live site's active quarter (right here
on your machine, where Yahoo works) and pushes them to the server — streaming
each symbol as it goes, with a summary at the end.

Uses Flask, which is already in your venv, so there's no tkinter to install.

Run it by double-clicking push_gui.command, or:  python push_gui.py
"""

import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import urllib.request
import webbrowser

from flask import Flask, Response, jsonify, request

import whatsapp_caption

HERE = os.path.dirname(os.path.abspath(__file__))

# Some macOS Python builds ship without CA certs wired up; use certifi's bundle
# when available (it's a yfinance dependency) so HTTPS to the live site works.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

# --- Config -----------------------------------------------------------------
# Credentials live in push_config.json (gitignored — never committed). Env vars
# PUSH_URL / ADMIN_PASSWORD override the file if set.
_CFG_PATH = os.path.join(HERE, "push_config.json")
_cfg = {}
try:
    with open(_CFG_PATH) as f:
        _cfg = json.load(f)
except FileNotFoundError:
    pass

URL = os.environ.get("PUSH_URL") or _cfg.get("url", "")
PASSWORD = os.environ.get("ADMIN_PASSWORD") or _cfg.get("password", "")

if not URL or not PASSWORD:
    sys.exit(
        "Missing config. Create push_config.json next to this script:\n"
        '  {"url": "https://investor-index.onrender.com", "password": "YOUR_PASSWORD"}\n'
        "(or set PUSH_URL / ADMIN_PASSWORD env vars)."
    )
VENV_PY = os.path.join(HERE, ".venv", "bin", "python")
PYTHON = VENV_PY if os.path.exists(VENV_PY) else sys.executable

# --- WhatsApp auto-post (optional) ------------------------------------------
# Posts the standings screenshot + a fun one-liner to a WhatsApp group after
# each successful push. Needs a one-time login (see whatsapp_login.command)
# and a "whatsapp" block in push_config.json, e.g.:
#   {"whatsapp": {"enabled": true, "group_invite": "https://chat.whatsapp.com/..."}}
_wa_cfg = _cfg.get("whatsapp") or {}
WHATSAPP_DIR = os.path.join(HERE, "whatsapp")
WHATSAPP_SCREENSHOT = os.path.join(WHATSAPP_DIR, "last_screenshot.png")
WHATSAPP_GROUP_INVITE = _wa_cfg.get("group_invite", "")
WHATSAPP_DEFAULT_ON = bool(_wa_cfg.get("enabled", True)) and bool(WHATSAPP_GROUP_INVITE)
WHATSAPP_CONFIGURED = bool(WHATSAPP_GROUP_INVITE) and os.path.isdir(WHATSAPP_DIR)
NODE = shutil.which("node") or "node"

app = Flask(__name__)

PAGE = """<!DOCTYPE html>
<html lang="en" data-theme="dark"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stocks Elite — Price Updater</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{
  --serif:'Cormorant Garamond','Playfair Display',Georgia,serif;
  --sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  --radius:16px;--radius-sm:11px;--maxw:880px;
  --gold:#c8a45c;--gold-soft:#e3cd9a;--pos:#3bb88a;--neg:#e07070;
  --bg:#070a09;--bg-grad:radial-gradient(1100px 560px at 72% -12%,#11231b 0%,#070a09 58%);
  --surface:#0e1413;--surface-2:#131c19;--surface-3:#19241f;
  --border:#22332d;--border-strong:#314a3f;
  --text:#eef2f0;--text-dim:#9bb0a8;--text-faint:#647e77;
  --shadow:0 26px 64px -30px rgba(0,0,0,.85);--chip:#16201d;
}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{font-family:var(--sans);background:var(--bg);background-image:var(--bg-grad);
  background-attachment:fixed;color:var(--text);-webkit-font-smoothing:antialiased;line-height:1.5;min-height:100vh}
.topbar{position:sticky;top:0;z-index:50;backdrop-filter:blur(14px);
  background:color-mix(in srgb,var(--bg) 80%,transparent);border-bottom:1px solid var(--border)}
.topbar-inner{max-width:var(--maxw);margin:0 auto;display:flex;align-items:center;gap:14px;padding:15px 26px;flex-wrap:wrap}
.brand{display:flex;align-items:baseline;gap:12px}
.brand .mark{font-family:var(--serif);font-weight:700;font-size:26px;letter-spacing:.04em}
.brand .mark em{color:var(--gold);font-style:normal}
.brand .sub{font-family:var(--mono);font-size:10px;letter-spacing:.28em;text-transform:uppercase;color:var(--text-faint)}
.spacer{flex:1}
.wrap{max-width:var(--maxw);margin:0 auto;padding:30px 26px 80px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:24px 26px;box-shadow:var(--shadow)}
.panel-head{display:flex;align-items:center;gap:12px;margin-bottom:20px}
.panel-head h3{font-family:var(--serif);font-size:24px;font-weight:700;margin:0;letter-spacing:.01em}
.panel-head .rule{flex:1;height:1px;background:var(--border)}
.panel-head .note{font-family:var(--mono);font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--text-faint)}
.row{display:flex;align-items:center;gap:18px;margin-bottom:20px;flex-wrap:wrap}
.field-q{display:flex;align-items:center;gap:10px}
.field-q label{font-family:var(--mono);font-size:10px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--text-faint)}
select#qsel{font-family:var(--sans);font-size:14px;color:var(--text);
  background:var(--surface-2);border:1px solid var(--border);border-radius:999px;
  padding:10px 16px;cursor:pointer;min-width:200px}
.btn{font-family:var(--sans);font-size:14px;font-weight:600;color:#1a1407;cursor:pointer;
  background:linear-gradient(180deg,var(--gold-soft),var(--gold));border:1px solid transparent;
  border-radius:999px;padding:11px 26px;transition:transform .1s,filter .2s}
.btn:hover{filter:brightness(1.05)}
.btn:active{transform:translateY(1px)}
.btn:disabled{background:var(--surface-3);color:var(--text-faint);cursor:default;filter:none}
.status{font-family:var(--mono);font-size:12px;letter-spacing:.06em;color:var(--text-dim)}
pre#log{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius-sm);
  padding:16px 18px;min-height:300px;max-height:60vh;overflow:auto;
  font-family:var(--mono);font-size:13px;line-height:1.6;white-space:pre-wrap;margin:0}
.ok{color:var(--pos)}.fail{color:var(--neg)}
.head{color:var(--gold);font-weight:600}.muted{color:var(--text-faint)}
.foot{text-align:center;color:var(--text-faint);font-family:var(--mono);
  font-size:11px;letter-spacing:.12em;margin-top:30px}
</style></head>
<body>
<div class="topbar"><div class="topbar-inner">
  <div class="brand">
    <span class="mark">Stocks <em>Elite</em></span>
    <span class="sub">Price Updater</span>
  </div>
  <span class="spacer"></span>
  <span class="status">__URL__</span>
</div></div>
<div class="wrap">
  <div class="panel">
    <div class="panel-head">
      <h3>Update Prices</h3><span class="rule"></span>
      <span class="note">Local Yahoo Fetch → Live Site</span>
    </div>
    <div class="row">
      <div class="field-q">
        <label for="qsel">Quarter</label>
        <select id="qsel"><option value="">Active quarter</option></select>
      </div>
      <label class="field-q" id="waWrap" style="display:none">
        <input type="checkbox" id="waChk">
        <span style="font-family:var(--mono);font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--text-faint)">Post to WhatsApp</span>
      </label>
      <button class="btn" id="go" onclick="run()">Update Prices</button>
      <button class="btn" id="waGo" onclick="runWhatsAppOnly()" style="display:none">Post to WhatsApp Now</button>
      <span class="status" id="status">Ready.</span>
    </div>
    <pre id="log"><span class="muted">Click “Update Prices” to fetch today’s closes and push them up.</span></pre>
  </div>
  <div class="foot">RUNS ON YOUR MACHINE · YAHOO SERVES YOUR RESIDENTIAL IP</div>
</div>
<script>
const log = document.getElementById('log');
const btn = document.getElementById('go');
const status = document.getElementById('status');
const qsel = document.getElementById('qsel');
const waWrap = document.getElementById('waWrap');
const waChk = document.getElementById('waChk');
const waGo = document.getElementById('waGo');
// Show/pre-check the WhatsApp toggle only if it's configured server-side.
(async function loadWA(){
  try{
    const r = await fetch('/whatsapp_status'); const d = await r.json();
    if(d.configured){
      waWrap.style.display='flex'; waChk.checked = !!d.default_enabled;
      waGo.style.display='inline-block';
    }
  }catch(e){ /* leave hidden */ }
})();
// Populate the quarter dropdown from the live server.
(async function loadQuarters(){
  try{
    const r = await fetch('/quarters'); const d = await r.json();
    const qs = (d.quarters||[]).slice().sort((a,b)=>a.start_date<b.start_date?1:-1);
    let html = '<option value="">Active quarter</option>';
    if(qs.length>1) html += '<option value="all">All quarters</option>';
    qs.forEach(q=>{
      const live = q.id===d.active_id ? ' · live' : '';
      html += `<option value="${q.id}">${q.label}${live}</option>`;
    });
    qsel.innerHTML = html;
  }catch(e){ /* leave the default "Active quarter" option */ }
})();
function add(line){
  let cls='', t=line.trim();
  if(t.startsWith('OK')) cls='ok';
  else if(t.startsWith('FAIL')) cls='fail';
  else if(t.startsWith('Quarter')||t.startsWith('Pushed')||t.startsWith('Posting')||t.startsWith('Caption')) cls='head';
  const span=document.createElement('span');
  if(cls) span.className=cls;
  span.textContent=line+"\\n";
  log.appendChild(span); log.scrollTop=log.scrollHeight;
}
function run(){
  btn.disabled=true; btn.textContent='Updating…'; waGo.disabled=true;
  status.textContent='Working…'; status.style.color='var(--gold)';
  log.textContent='';
  let ok=0, fail=0;
  const wa=(waWrap.style.display!=='none' && waChk.checked) ? '1' : '0';
  const es=new EventSource('/stream?q='+encodeURIComponent(qsel.value)+'&wa='+wa);
  es.onmessage=(e)=>{
    if(e.data==='__DONE__'){ es.close();
      btn.disabled=false; btn.textContent='Update Prices'; waGo.disabled=false;
      status.textContent='Done · '+ok+' ok · '+fail+' failed';
      status.style.color='var(--pos)'; return; }
    const t=e.data.trim();
    if(t.startsWith('OK')) ok++; else if(t.startsWith('FAIL')) fail++;
    if(ok||fail) status.textContent=ok+' ok · '+fail+' failed';
    add(e.data);
  };
  es.onerror=()=>{ es.close(); btn.disabled=false; btn.textContent='Update Prices'; waGo.disabled=false;
    status.textContent='Connection ended'; status.style.color='var(--neg)'; };
}
// Stand-alone WhatsApp post: reuses whatever prices are already live on the
// server right now — no price push involved. Same log/status area, and
// disables the price-push button meanwhile (both flows would otherwise
// drive the same WhatsApp session at once).
function runWhatsAppOnly(){
  btn.disabled=true; waGo.disabled=true; waGo.textContent='Posting…';
  status.textContent='Working…'; status.style.color='var(--gold)';
  log.textContent='';
  let ok=0, fail=0;
  const es=new EventSource('/whatsapp_stream');
  es.onmessage=(e)=>{
    if(e.data==='__DONE__'){ es.close();
      btn.disabled=false; waGo.disabled=false; waGo.textContent='Post to WhatsApp Now';
      status.textContent='Done · '+ok+' ok · '+fail+' failed';
      status.style.color=fail?'var(--neg)':'var(--pos)'; return; }
    const t=e.data.trim();
    if(t.startsWith('OK')) ok++; else if(t.startsWith('FAIL')) fail++;
    if(ok||fail) status.textContent=ok+' ok · '+fail+' failed';
    add(e.data);
  };
  es.onerror=()=>{ es.close(); btn.disabled=false; waGo.disabled=false; waGo.textContent='Post to WhatsApp Now';
    status.textContent='Connection ended'; status.style.color='var(--neg)'; };
}
</script></body></html>"""


@app.route("/")
def index():
    return PAGE.replace("__URL__", URL)


@app.route("/quarters")
def quarters():
    """Proxy the live site's quarter list so the dropdown can populate."""
    try:
        with urllib.request.urlopen(f"{URL.rstrip('/')}/api/quarters",
                                    timeout=30, context=_SSL_CTX) as resp:
            return jsonify(json.loads(resp.read().decode("utf-8")))
    except Exception as exc:
        return jsonify({"quarters": [], "active_id": None, "error": str(exc)})


@app.route("/whatsapp_status")
def whatsapp_status():
    """Tells the page whether the WhatsApp checkbox should show, and whether
    it should default to checked."""
    return jsonify({
        "configured": WHATSAPP_CONFIGURED,
        "default_enabled": WHATSAPP_DEFAULT_ON,
    })


def _run_node_capture(args, timeout=150):
    """Run a whatsapp/*.js helper to completion; return (returncode, lines)."""
    try:
        proc = subprocess.run(
            [NODE] + args, cwd=WHATSAPP_DIR, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout,
        )
        return proc.returncode, [ln for ln in proc.stdout.splitlines() if ln.strip()]
    except FileNotFoundError:
        return 1, ["FAIL Node.js not found on PATH — install it to use WhatsApp auto-post."]
    except subprocess.TimeoutExpired:
        return 1, [f"FAIL whatsapp/{args[0]} timed out after {timeout}s."]


def _post_to_whatsapp():
    """Fetch the just-pushed results, screenshot the standings, and send them
    to the configured WhatsApp group. Yields plain log lines (no SSE prefix
    — the caller adds that)."""
    try:
        with urllib.request.urlopen(f"{URL.rstrip('/')}/api/quarters",
                                    timeout=30, context=_SSL_CTX) as resp:
            qmeta = json.loads(resp.read().decode("utf-8"))
        qid = qmeta.get("active_id")
        if not qid:
            yield "FAIL WhatsApp: no active quarter on the server."
            return
        with urllib.request.urlopen(
                f"{URL.rstrip('/')}/api/dashboard?quarter_id={qid}",
                timeout=30, context=_SSL_CTX) as resp:
            dashboard = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        yield f"FAIL WhatsApp: could not fetch results ({exc})"
        return

    caption = whatsapp_caption.build_caption(dashboard)
    yield f"Caption: {caption}"

    rc, lines = _run_node_capture(["screenshot.js", URL, WHATSAPP_SCREENSHOT])
    yield from lines
    if rc != 0:
        yield "FAIL WhatsApp: screenshot failed — not sending."
        return

    full_caption = f"{caption}\n\n{URL}"
    rc, lines = _run_node_capture(
        ["send_update.js", WHATSAPP_SCREENSHOT, full_caption], timeout=180)
    yield from lines


@app.route("/whatsapp_stream")
def whatsapp_stream():
    """Stand-alone WhatsApp post — screenshots + sends whatever is already
    live on the server right now. Doesn't touch push_prices.py at all."""
    def gen():
        if not WHATSAPP_CONFIGURED:
            yield "data: FAIL WhatsApp: not configured (see push_config.json).\n\n"
            yield "data: __DONE__\n\n"
            return
        for ln in _post_to_whatsapp():
            yield f"data: {ln}\n\n"
        yield "data: __DONE__\n\n"
    return Response(gen(), mimetype="text/event-stream")


@app.route("/stream")
def stream():
    # Translate the dropdown choice into a push_prices flag.
    q = (request.args.get("q") or "").strip()
    wa_requested = (request.args.get("wa") or "0") == "1"
    extra = []
    if q == "all":
        extra = ["--all"]
    elif q.isdigit():
        extra = ["--quarter-id", q]
    # else: empty -> default (active quarter)

    def gen():
        cmd = [PYTHON, "-u", os.path.join(HERE, "push_prices.py"),
               "--url", URL, "--password", PASSWORD] + extra
        proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for ln in proc.stdout:
            yield f"data: {ln.rstrip(chr(10))}\n\n"
        proc.wait()

        if proc.returncode == 0 and wa_requested and WHATSAPP_CONFIGURED:
            yield "data: Posting to WhatsApp…\n\n"
            for ln in _post_to_whatsapp():
                yield f"data: {ln}\n\n"

        yield "data: __DONE__\n\n"
    return Response(gen(), mimetype="text/event-stream")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    port = int(os.environ.get("GUI_PORT", _free_port()))
    url = f"http://127.0.0.1:{port}/"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"Stocks Elite updater running at {url}  (Ctrl-C to quit)")
    app.run(host="127.0.0.1", port=port, threaded=True)


if __name__ == "__main__":
    main()

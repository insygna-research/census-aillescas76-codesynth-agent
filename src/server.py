"""HTTP entry point: the ADK API server over the requirement-implementation orchestrator.

Serves the standard ADK endpoints (POST /run, POST /run_sse, the session API under
/apps/codesynth/..., GET /list-apps, GET /health) plus a first page at GET /.

The agents need a Gemini API key. When none is configured the container still starts:
the first page asks for one, and the run endpoints answer 409 pointing there instead of
failing on every call. A key from the environment (GOOGLE_API_KEY) always wins; a key
entered on the page is kept in DATA_DIR so it survives a restart.
"""
import os
import pathlib

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse
from google.adk.agents import LlmAgent
from google.adk.cli.fast_api import get_fast_api_app

# Import the agent now rather than on the first request, so an agent that cannot
# load stops the container at startup instead of answering 500 for ever.
from apps.codesynth.agent import root_agent

APPS_DIR = pathlib.Path(__file__).parent / "apps"
DATA_DIR = pathlib.Path(os.environ.get("CODESYNTH_DATA_DIR", "/app/data"))
KEY_FILE = DATA_DIR / "google_api_key"
KEY_ENV = "GOOGLE_API_KEY"
RUN_PATHS = ("/run", "/run_sse", "/run_live")

# Whether the key in the environment came from the deployment (not changeable here)
# or from this page. Decided once, before the stored key is loaded.
KEY_FROM_DEPLOYMENT = bool(os.environ.get(KEY_ENV, "").strip())


def _load_stored_key() -> None:
    if KEY_FROM_DEPLOYMENT:
        return
    try:
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if key:
        os.environ[KEY_ENV] = key


def _key_configured() -> bool:
    return bool(os.environ.get(KEY_ENV, "").strip())


def _forget_cached_models(agent) -> None:
    """ADK keeps each agent's Gemini client, which holds the key it was made with."""
    if isinstance(agent, LlmAgent):
        agent._resolved_model = None
    for sub in agent.sub_agents or []:
        _forget_cached_models(sub)


def _check_key(key: str) -> str | None:
    """None when Google accepts the key, otherwise why not, in words."""
    from google import genai
    from google.genai import errors

    try:
        # Hold the client while the listing is read: a temporary one is closed under it.
        client = genai.Client(api_key=key)
        next(iter(client.models.list(config={"page_size": 1})), None)
        return None
    except errors.ClientError as e:
        if e.code in (400, 401, 403):
            return "Google did not accept this key: " + (e.message or str(e))
        return f"Google answered {e.code} while checking the key: {e.message or e}"
    except Exception as e:  # network, DNS, egress policy
        return f"Could not reach Google to check the key ({type(e).__name__}: {e})."


_load_stored_key()

app = get_fast_api_app(
    agents_dir=str(APPS_DIR),
    web=False,
    # Sessions live in memory: they are per conversation and need not survive a restart.
    use_local_storage=False,
)


@app.middleware("http")
async def require_key_for_runs(request: Request, call_next):
    if request.url.path in RUN_PATHS and not _key_configured():
        return JSONResponse(
            status_code=409,
            content={
                "error": "No Gemini API key is configured, so the agents cannot run.",
                "fix": "Open the agent's first page (/) and add a key.",
            },
        )
    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
def first_page():
    return HTMLResponse(_PAGE)


@app.get("/setup/status")
def setup_status():
    return {
        "keyConfigured": _key_configured(),
        "keySource": "deployment" if KEY_FROM_DEPLOYMENT else ("page" if _key_configured() else None),
    }


@app.post("/setup/google-api-key")
async def set_key(request: Request):
    if KEY_FROM_DEPLOYMENT:
        return JSONResponse(status_code=409, content={
            "error": "The key is set by the deployment (GOOGLE_API_KEY) and cannot be changed here."})
    body = await request.json()
    key = str(body.get("key", "")).strip()
    if not key:
        return JSONResponse(status_code=400, content={"error": "Paste a Gemini API key."})
    problem = await run_in_threadpool(_check_key, key)
    if problem:
        return JSONResponse(status_code=400, content={"error": problem})
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = KEY_FILE.with_suffix(".tmp")
    tmp.write_text(key, encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(KEY_FILE)
    os.environ[KEY_ENV] = key
    _forget_cached_models(root_agent)
    return {"keyConfigured": True, "keySource": "page"}


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CodeSynth Agent</title>
<style>
  :root { --bg:#f8fafc; --card:#fff; --tx:#0f172a; --mut:#64748b; --bd:#e2e8f0; --ac:#2563eb; --err:#b91c1c; --ok:#15803d; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0b1120; --card:#111827; --tx:#e5e7eb; --mut:#94a3b8; --bd:#1f2937; --ac:#60a5fa; --err:#f87171; --ok:#4ade80; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--tx); font:15px/1.5 system-ui, -apple-system, Segoe UI, sans-serif; }
  main { max-width: 760px; margin: 0 auto; padding: 32px 16px 64px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  p.lead { color: var(--mut); margin: 0 0 24px; }
  .card { background: var(--card); border: 1px solid var(--bd); border-radius: 10px; padding: 20px; margin-bottom: 16px; }
  h2 { font-size: 16px; margin: 0 0 8px; }
  label { display:block; font-size:13px; color:var(--mut); margin: 12px 0 4px; }
  input, textarea { width:100%; padding:9px 10px; border:1px solid var(--bd); border-radius:8px; background:transparent; color:var(--tx); font:inherit; }
  textarea { min-height: 120px; resize: vertical; }
  button { margin-top: 14px; padding: 9px 16px; border: 0; border-radius: 8px; background: var(--ac); color: #fff; font: inherit; cursor: pointer; }
  button[disabled] { opacity: .6; cursor: default; }
  button.link { background: none; color: var(--ac); padding: 0; margin: 0; }
  .msg { margin-top: 10px; font-size: 14px; }
  .msg.err { color: var(--err); } .msg.ok { color: var(--ok); }
  .muted { color: var(--mut); font-size: 13px; }
  .event { border-top: 1px solid var(--bd); padding: 10px 0; }
  .event:first-child { border-top: 0; }
  .who { font-size: 12px; color: var(--mut); text-transform: uppercase; letter-spacing: .04em; }
  .event pre { white-space: pre-wrap; word-break: break-word; margin: 4px 0 0; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
  a { color: var(--ac); }
  [hidden] { display: none !important; }
</style>
</head>
<body>
<main>
  <h1>CodeSynth Agent</h1>
  <p class="lead">Describe a software requirement. A team of agents analyses it, plans, writes the code and reviews it.</p>

  <section class="card" id="setup" hidden>
    <h2>Add a Gemini API key</h2>
    <p class="muted">The agents run on Google Gemini and need a key before they can work.
      Create one at <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener">Google AI Studio</a>.
      It is checked with Google, then kept with this agent and used for every run.</p>
    <form id="keyForm">
      <label for="key">Gemini API key</label>
      <input id="key" type="password" autocomplete="off" spellcheck="false" placeholder="AIza...">
      <button id="keyBtn" type="submit">Save key</button>
      <div class="msg" id="keyMsg"></div>
    </form>
  </section>

  <section class="card" id="keyInfo" hidden>
    <span class="muted" id="keyInfoText"></span>
    <button class="link" id="replaceBtn" type="button" hidden>Replace key</button>
  </section>

  <section class="card" id="runCard" hidden>
    <h2>New requirement</h2>
    <form id="runForm">
      <label for="req">Requirement</label>
      <textarea id="req" placeholder="e.g. Write a Python function that validates an IBAN, with unit tests."></textarea>
      <label for="path">Project folder (relative, where generated files are written)</label>
      <input id="path" value="workspace">
      <button id="runBtn" type="submit">Run</button>
      <div class="msg" id="runMsg"></div>
    </form>
  </section>

  <section class="card" id="out" hidden><h2>Progress</h2><div id="events"></div></section>
</main>
<script>
const $ = (id) => document.getElementById(id);
const APP = "codesynth", USER = "web";

async function refresh() {
  const s = await (await fetch("setup/status")).json();
  $("setup").hidden = s.keyConfigured;
  $("runCard").hidden = !s.keyConfigured;
  $("keyInfo").hidden = !s.keyConfigured;
  if (s.keyConfigured) {
    $("keyInfoText").textContent = s.keySource === "deployment"
      ? "Gemini API key: set by the deployment."
      : "Gemini API key: added on this page. ";
    $("replaceBtn").hidden = s.keySource !== "page";
  }
}

$("replaceBtn").onclick = () => { $("setup").hidden = false; $("key").focus(); };

$("keyForm").onsubmit = async (e) => {
  e.preventDefault();
  const btn = $("keyBtn"), msg = $("keyMsg");
  btn.disabled = true; msg.className = "msg"; msg.textContent = "Checking the key with Google…";
  try {
    const r = await fetch("setup/google-api-key", { method: "POST",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ key: $("key").value }) });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || ("HTTP " + r.status));
    $("key").value = ""; msg.className = "msg ok"; msg.textContent = "Key saved.";
    await refresh();
  } catch (err) { msg.className = "msg err"; msg.textContent = err.message; }
  finally { btn.disabled = false; }
};

function addEvent(who, text) {
  const div = document.createElement("div"); div.className = "event";
  const w = document.createElement("div"); w.className = "who"; w.textContent = who;
  const pre = document.createElement("pre"); pre.textContent = text;
  div.append(w, pre); $("events").append(div); div.scrollIntoView({ block: "nearest" });
}

function describe(ev) {
  const parts = (ev.content && ev.content.parts) || [];
  const out = [];
  for (const p of parts) {
    if (p.text) out.push(p.text);
    else if (p.functionCall) out.push("→ " + p.functionCall.name + "(" + JSON.stringify(p.functionCall.args || {}) + ")");
    else if (p.functionResponse) out.push("← " + p.functionResponse.name + " " + JSON.stringify(p.functionResponse.response || {}).slice(0, 400));
  }
  if (ev.errorMessage) out.push("Error: " + ev.errorMessage);
  return out.join("\\n");
}

$("runForm").onsubmit = async (e) => {
  e.preventDefault();
  const req = $("req").value.trim(), msg = $("runMsg"), btn = $("runBtn");
  if (!req) { msg.className = "msg err"; msg.textContent = "Describe the requirement first."; return; }
  btn.disabled = true; msg.className = "msg"; msg.textContent = "Running… this can take several minutes.";
  $("events").innerHTML = ""; $("out").hidden = false;
  try {
    const sr = await fetch(`apps/${APP}/users/${USER}/sessions`, { method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ state: { project_path: $("path").value.trim() || "workspace" } }) });
    if (!sr.ok) throw new Error("Could not start a session (HTTP " + sr.status + ")");
    const session = await sr.json();
    const r = await fetch("run_sse", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ appName: APP, userId: USER, sessionId: session.id,
        newMessage: { role: "user", parts: [{ text: req }] }, streaming: false }) });
    if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b.error || b.detail || ("HTTP " + r.status)); }
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "", failed = false;
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\\n\\n")) >= 0) {
        const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
        const data = chunk.split("\\n").filter(l => l.startsWith("data:")).map(l => l.slice(5)).join("");
        if (!data) continue;
        try { const ev = JSON.parse(data); const t = describe(ev); if (t) addEvent(ev.author || "agent", t); if (ev.error) { failed = true; addEvent("error", ev.error); } if (ev.errorMessage) failed = true; }
        catch { addEvent("agent", data); }
      }
    }
    if (failed) { msg.className = "msg err"; msg.textContent = "Stopped with an error — see below."; }
    else { msg.className = "msg ok"; msg.textContent = "Finished."; }
  } catch (err) { msg.className = "msg err"; msg.textContent = err.message; }
  finally { btn.disabled = false; }
};

refresh();
</script>
</body>
</html>
"""

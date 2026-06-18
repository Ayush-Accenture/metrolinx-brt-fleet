// Tiny client for the demo UI backend (demo/api/main.py).
// Everything the UI shows comes from the DB via this API; approvals are written
// back through it. If the backend isn't running, the UI falls back to the mock
// data in data.js so the static demo still works.

const API_BASE = window.API_BASE || "http://localhost:8080";

const Api = {
  async health() {
    const r = await fetch(`${API_BASE}/api/health`);
    if (!r.ok) throw new Error(`health ${r.status}`);
    return r.json();
  },
  async listRuns() {
    const r = await fetch(`${API_BASE}/api/runs`);
    if (!r.ok) throw new Error(`listRuns ${r.status}`);
    return r.json();
  },
  async getRun(runId) {
    const r = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}`);
    if (!r.ok) throw new Error(`getRun ${r.status}`);
    return r.json();
  },
  async getPending(runId) {
    const r = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}/pending`);
    if (!r.ok) throw new Error(`getPending ${r.status}`);
    return r.json();
  },
  async submitDecision(runId, gate, decision, note = "") {
    const body = new URLSearchParams({ gate, decision, note });
    const r = await fetch(`${API_BASE}/api/runs/${encodeURIComponent(runId)}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!r.ok) throw new Error(`submitDecision ${r.status}`);
    return r.json();
  },
};

// Non-invasive live check: if the backend is up, show a small badge with the
// real run + state pulled from the DB (proves the UI↔DB loop). On failure,
// stay silent and let the mock demo run as-is.
async function detectLiveBackend() {
  try {
    const health = await Api.health();
    const runs = await Api.listRuns();
    const badge = document.createElement("div");
    badge.style.cssText =
      "position:fixed;bottom:12px;left:12px;z-index:9999;font:12px/1.4 system-ui;" +
      "background:#0b7a3b;color:#fff;padding:6px 10px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.25)";
    const run = runs[0];
    badge.textContent = run
      ? `🟢 Live DB (${health.mock ? "mock" : "cosmos"}) — ${run.run_id} · ${run.state}`
      : `🟢 Live DB (${health.mock ? "mock" : "cosmos"}) — no runs`;
    document.body.appendChild(badge);
    if (run) {
      const full = await Api.getRun(run.run_id);
      console.info("[api] live run from DB:", full);
    }
  } catch (e) {
    console.info("[api] backend not reachable — using mock demo data.", e.message);
  }
}

window.addEventListener("load", detectLiveBackend);

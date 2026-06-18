"""
Demo UI backend — FastAPI.

Bridges the demo UI to Cosmos DB (MongoDB vCore). Per the team decision, the UI
reads ALL data from the DB and writes approvals back to the DB — no file bridge.

  READ  : GET  /api/runs                  → list runs
          GET  /api/runs/{run_id}         → one run (plan + state + steps + approvals)
          GET  /api/runs/{run_id}/pending → current HITL gate (derived from state)
  WRITE : POST /api/runs/{run_id}/decision→ append approval + update state in Cosmos

Collection: the run documents live in the Cosmos `runs` collection (same DB the
intake/movement collections use). Shape matches fleet-agents/schemas/run_doc.py.

NOTE (dependency): today the orchestrator's state_store writes run docs to local
files (output/run_*.json), NOT Cosmos. For live data the orchestrator must also
write run docs to the Cosmos `runs` collection (that change is on the agent side).
Until then, run with USE_MOCK_COSMOS=true to serve a realistic sample.

Run:
  pip install -r requirements.txt
  cp .env.example .env          # fill COSMOS_CONNECTION_STRING, or leave mock on
  uvicorn main:app --port 8080
"""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

COSMOS_CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING", "")
COSMOS_DATABASE          = os.getenv("COSMOS_DATABASE", "fmi-db")
COSMOS_RUNS_COLLECTION   = os.getenv("COSMOS_RUNS_COLLECTION", "runs")
USE_MOCK_COSMOS          = os.getenv("USE_MOCK_COSMOS", "true").lower() == "true"

# States that mean the run is paused at a human-approval gate.
AWAITING_GATES = {
    "AWAITING_PRE_APPROVAL":  "HITL-2",   # review the move plan before executing
    "AWAITING_VALIDATION":    "HITL-3",   # review results after the SOTI moves
    "AWAITING_SR_APPROVAL":   "HITL-4",   # review the SR before it is raised
}

app = FastAPI(title="Fleet Demo UI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_client = None


def _runs():
    """Return the Cosmos `runs` collection (cached client). Raises if not configured."""
    global _client
    if not COSMOS_CONNECTION_STRING:
        raise RuntimeError("COSMOS_CONNECTION_STRING not set (or keep USE_MOCK_COSMOS=true).")
    if _client is None:
        from pymongo import MongoClient
        _client = MongoClient(COSMOS_CONNECTION_STRING)
    return _client[COSMOS_DATABASE][COSMOS_RUNS_COLLECTION]


def _pending_for(doc: dict) -> dict:
    """Derive the current HITL gate from the run's state."""
    gate = AWAITING_GATES.get(doc.get("state", ""))
    if not gate:
        return {"status": "none"}
    return {"status": "pending", "gate": gate, "run_id": doc.get("run_id"),
            "state": doc.get("state"), "payload": {"steps": doc.get("steps", [])}}


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"ok": True, "mock": USE_MOCK_COSMOS, "db": COSMOS_DATABASE,
            "collection": COSMOS_RUNS_COLLECTION}


@app.get("/api/runs")
def list_runs():
    """List runs, newest first (summary fields only)."""
    if USE_MOCK_COSMOS:
        d = _MOCK_RUN
        return [{"run_id": d["run_id"], "agency": d["agency"], "state": d["state"],
                 "current_step": d["current_step"], "started_utc": d["started_utc"]}]
    docs = _runs().find({}, {"_id": 0, "run_id": 1, "agency": 1, "state": 1,
                             "current_step": 1, "started_utc": 1}).sort("started_utc", -1)
    return list(docs)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    """Full run document — the plan, state, steps and approvals the UI renders."""
    if USE_MOCK_COSMOS:
        return _MOCK_RUN if run_id == _MOCK_RUN["run_id"] else JSONResponse(
            {"error": "not found"}, status_code=404)
    doc = _runs().find_one({"run_id": run_id}, {"_id": 0})
    return doc or JSONResponse({"error": "not found"}, status_code=404)


@app.get("/api/runs/{run_id}/pending")
def get_pending(run_id: str):
    """Return the current pending HITL gate (or {status:none})."""
    if USE_MOCK_COSMOS:
        return _pending_for(_MOCK_RUN) if run_id == _MOCK_RUN["run_id"] else {"status": "none"}
    doc = _runs().find_one({"run_id": run_id}, {"_id": 0})
    return _pending_for(doc) if doc else {"status": "none"}


@app.post("/api/runs/{run_id}/decision")
def submit_decision(run_id: str, gate: str = Form(...), decision: str = Form(...),
                    note: str = Form("")):
    """
    Write an L2 approval/rejection back to the DB: append to `approvals` and
    advance/abort the run state. This is the 'write to DB' half of the HITL loop.
    """
    approval = {
        "gate": gate, "decision": decision, "note": note,
        "decided_by": "L2-ops-ui",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    new_state = _next_state(gate, decision)

    if USE_MOCK_COSMOS:
        _MOCK_RUN["approvals"].append(approval)
        if new_state:
            _MOCK_RUN["state"] = new_state
        return {"status": "ok", "run_id": run_id, "gate": gate,
                "decision": decision, "new_state": _MOCK_RUN["state"]}

    update: dict = {"$push": {"approvals": approval}}
    if new_state:
        update["$set"] = {"state": new_state}
    res = _runs().update_one({"run_id": run_id}, update)
    if res.matched_count == 0:
        return JSONResponse({"error": "run not found"}, status_code=404)
    return {"status": "ok", "run_id": run_id, "gate": gate,
            "decision": decision, "new_state": new_state}


def _next_state(gate: str, decision: str) -> str | None:
    """Map a gate decision to the next run state (the orchestrator also reads this)."""
    if decision in ("reject", "abort"):
        return "ABORTED"
    return {
        "HITL-2": "MOVING",
        "HITL-3": "DRAFTING_SR",
        "HITL-4": "EXECUTING",
    }.get(gate)


# ── Mock run (used when USE_MOCK_COSMOS=true) — mirrors the BRT demo scenario ──
_MOCK_RUN = {
    "run_id": "BRT-2026-06-18",
    "intake_id": "intake_BRT_2026-06-18",
    "agency": "BRT",
    "state": "AWAITING_PRE_APPROVAL",
    "current_step": "stage3_hitl_pre",
    "started_utc": datetime.now(timezone.utc).isoformat(),
    "steps": [
        {"step": "stage1_intake", "status": "DONE"},
        {"step": "stage2_parse", "status": "DONE",
         "output": {"intended_moves": [
             {"bus_number": "1003", "current_device": "BRT_DCU_1003_1", "target_folder": "LTM"},
             {"bus_number": "1004", "current_device": "BRT_BFTP_1004_2", "target_folder": "LTM"},
             {"bus_number": "9001", "current_device": "LTM_BRT_DCU_9001_1", "target_folder": "Production"},
         ]}},
    ],
    "approvals": [],
    "tool_calls": [],
}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

# Demo UI — Backend API

Bridges the demo UI to **Cosmos DB**. Per the team decision the UI reads all data
from the DB and writes approvals back to the DB (no file bridge).

## Run

```bash
pip install -r requirements.txt
cp .env.example .env        # fill COSMOS_CONNECTION_STRING, or leave USE_MOCK_COSMOS=true
uvicorn main:app --port 8080
```

Then serve the UI (`cd demo && npm start`) — the frontend calls this API at
`http://localhost:8080` (see `demo/js/api.js`).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health` | Health + which mode (mock/live) |
| GET  | `/api/runs` | List runs (newest first) |
| GET  | `/api/runs/{run_id}` | One run — plan, state, steps, approvals |
| GET  | `/api/runs/{run_id}/pending` | Current HITL gate (derived from state) |
| POST | `/api/runs/{run_id}/decision` | Write approve/reject to the DB (form: `gate`, `decision`, `note`) |

## Data

- DB: `fmi-db` (same as `intake` / `movement`). Run docs live in the **`runs`** collection.
- Document shape matches `fleet-agents/schemas/run_doc.py` (`run_id`, `state`, `steps`, `approvals`, …).
- The HITL loop: agent writes `state: AWAITING_*` → UI reads it → L2 approves → this API
  writes the approval + advances `state` → agent reads the new state and continues.

## ⚠️ One dependency (agent side)

Today the orchestrator's `state_store.py` writes run docs to **local files**
(`output/run_*.json`), not Cosmos. For live data, the orchestrator must also write
run docs to the Cosmos **`runs`** collection. Until that lands, run with
`USE_MOCK_COSMOS=true` (serves a realistic sample so the UI works end-to-end).

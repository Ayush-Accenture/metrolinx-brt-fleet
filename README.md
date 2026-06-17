# BRT Fleet Movement — Agentic AI Pipeline

End-to-end agentic pipeline that automates Brampton Transit device-vehicle allocation (DVA) fleet movements in SOTI MobiControl, with a React + TypeScript Ops Console for human-in-the-loop (HITL) review.

---

## Project Structure

```
metrolinx/
├── fleet-agents/               # Python agentic pipeline
│   ├── run.py                  # Entry point
│   ├── orchestrator.py         # 8-stage workflow driver
│   ├── config.py               # All config / env vars
│   ├── core/
│   │   ├── excel_parser.py     # DVA Excel → IntendedMove list
│   │   ├── cosmos_audit.py     # Non-fatal Cosmos write-back
│   │   └── state_store.py      # Run state JSON persistence
│   ├── tools/
│   │   └── hitl_console.py     # HITL gate prompts + web bridge
│   ├── agents/                 # Azure AI Foundry agent wrappers
│   ├── mcp_clients/            # SOTI MCP client
│   ├── output/                 # ← All run outputs written here
│   │   ├── run_<run_id>.json
│   │   ├── BRT_FleetMovement_<run_id>.xlsx  (5-tab workbook)
│   │   ├── hitl_pending_<run_id>_<gate>.json
│   │   └── hitl_decision_<run_id>_<gate>.json
│   ├── .env                    # Local secrets (not committed)
│   ├── .env.example            # Template for .env
│   └── requirements.txt
│
├── ops-dashboard-portal/       # Ops Console web app
│   ├── main.py                 # FastAPI JSON API backend (port 8080)
│   ├── requirements.txt
│   ├── .venv/                  # Python venv for backend
│   └── frontend/               # React + TypeScript UI (Vite)
│       ├── src/
│       │   ├── main.tsx
│       │   ├── App.tsx
│       │   ├── api.ts          # fetch helpers
│       │   ├── types.ts        # TypeScript interfaces
│       │   └── components/
│       │       ├── RunList.tsx       # All-runs table (auto-polls 10s)
│       │       ├── RunDetail.tsx     # 5-panel run view (auto-polls 5s)
│       │       ├── HITLPanel.tsx     # Gate decision form + move preview
│       │       ├── WorkbookTabs.tsx  # 5-tab xlsx viewer
│       │       ├── AuditTail.tsx     # Step + approval timeline
│       │       └── StateBadge.tsx    # Colour-coded state badge
│       ├── package.json
│       ├── vite.config.ts      # Proxies /api/* → port 8080
│       └── tsconfig.json
│
└── soti_mcp_server/            # Local SOTI MCP server (stdio)
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.13+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Azure CLI | latest | For Blob / Cosmos auth |

> **Windows note:** PowerShell execution policy may block `npm`. Use `& "C:\Program Files\nodejs\npm.cmd"` instead of bare `npm`.

---

## Pipeline Setup (`fleet-agents/`)

### 1. Create virtual environment

```powershell
cd fleet-agents
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. Configure `.env`

Copy `.env.example` to `.env` and fill in values:

```ini
# ── Mock flags (safe defaults for dev) ────────────────────────────────────
USE_MOCK_LLM=true          # true = use stub LLM, false = real Azure OpenAI
USE_MOCK_SOTI=false        # true = skip real SOTI calls
USE_MOCK_HITL=false        # true = auto-approve all gates (unattended/CI)
USE_MOCK_COSMOS=false      # true = skip Cosmos writes

# ── Output directory ───────────────────────────────────────────────────────
STATE_DIR=output           # All run files written here

# ── Web HITL (set true to use portal instead of console prompts) ───────────
USE_WEB_HITL=false
OPS_PORTAL_URL=http://localhost:8080

# ── Azure Blob Storage (DVA Excel source) ─────────────────────────────────
AZURE_STORAGE_SAS_URL=https://agenticaidashboardsa.blob.core.windows.net/fmi?...

# ── Azure Cosmos DB ────────────────────────────────────────────────────────
COSMOS_CONNECTION_STRING=mongodb+srv://...
COSMOS_DATABASE=agenticaicosmos
COSMOS_INTAKE_COLLECTION=dva_intake

# ── Fallback local DVA (used if Blob download fails) ──────────────────────
SAMPLE_DVA=C:\path\to\Brampton's Vehicle Device Allocation File.xlsx
```

### 3. Run the pipeline

```powershell
cd fleet-agents
$env:PYTHONUTF8 = "1"        # Required on Windows for Unicode in logs
.\.venv\Scripts\python run.py BRT-2026-05-27 --auto
```

**Options:**

| Flag | Effect |
|------|--------|
| `--auto` | Sets `USE_MOCK_HITL=true` — auto-approves all HITL gates |
| *(no flag)* | Pauses at each gate for console input (or web portal if `USE_WEB_HITL=true`) |

**Output files written to `fleet-agents/output/`:**

| File | Description |
|------|-------------|
| `run_<run_id>.json` | Full run state (steps, approvals, tool calls) |
| `BRT_FleetMovement_<run_id>.xlsx` | 5-tab output workbook |
| `hitl_pending_<run_id>_<gate>.json` | Written when a gate is waiting |
| `hitl_decision_<run_id>_<gate>.json` | Written when L2 submits a decision |

---

## Pipeline Stages

| Stage | Description |
|-------|-------------|
| 1 | **Cosmos check** — find intake record for the run date |
| 2 | **DVA parse** — download Excel from Azure Blob, generate IntendedMoves |
| 2b | **SOTI enrichment** — look up current folder per device |
| 3 | **HITL-2** — pre-move approval (shows dry-run preview) |
| 4 | **SOTI moves** — call `move_device_to_folder` via MCP for each device |
| 5 | **Reconciliation** — verify each move; write 5-tab workbook |
| 6 | **HITL-3** — post-move validation |
| 7 | **Fleet tracker** — append to `Fleet.xlsx`; HITL-4 SR closure |
| 8 | **COMPLETED** |

---

## Ops Console Setup (`ops-dashboard-portal/`)

### Backend — FastAPI JSON API

```powershell
cd ops-dashboard-portal

# First time only
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# Start the API server
.\.venv\Scripts\uvicorn main:app --port 8080
```

API is now available at **http://localhost:8080**

### Frontend — React + TypeScript (Vite)

```powershell
cd ops-dashboard-portal\frontend

# First time only — install dependencies
& "C:\Program Files\nodejs\npm.cmd" install

# Start the dev server
& "C:\Program Files\nodejs\npm.cmd" run dev
```

UI is now available at **http://localhost:5173**

> The Vite dev server proxies all `/api/*` requests to the FastAPI backend at port 8080 automatically. Both must be running at the same time.

---

## API Reference (Backend)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/runs` | List all runs (newest first) |
| `GET` | `/api/runs/{run_id}` | Get a single run document |
| `GET` | `/api/runs/{run_id}/pending` | Pending HITL gate or `{status: "none"}` |
| `GET` | `/api/runs/{run_id}/workbook` | 5-tab xlsx as JSON `{tab: [[row],...]}` |
| `POST` | `/api/runs/{run_id}/decision` | Submit L2 HITL decision |

**Decision POST body** (form-encoded):

| Field | Type | Values |
|-------|------|--------|
| `gate` | string | `HITL-2`, `HITL-3`, `HITL-4`, etc. |
| `decision` | string | `approve_all`, `approve_subset`, `reject`, `confirm`, `abort`… |
| `note` | string | Free-text audit note (optional) |
| `subset_indices` | string | Comma-separated 0-based indices for `approve_subset` |

---

## HITL File Bridge

When `USE_WEB_HITL=true` the pipeline pauses at each gate and signals the portal:

```
Pipeline                          Portal (React UI)
────────                          ─────────────────
writes hitl_pending_{id}_{gate}.json
opens browser → http://localhost:8080/runs/{run_id}
                                  ← L2 sees gate panel
                                  L2 submits decision
                                  portal writes hitl_decision_{id}_{gate}.json
                                  removes hitl_pending file
polls every 2s ←
reads decision file
resumes workflow
```

---

## Production Build (optional)

Build the React app into static files served directly by FastAPI:

```powershell
cd ops-dashboard-portal\frontend
& "C:\Program Files\nodejs\npm.cmd" run build
# Output: frontend/dist/

# Now FastAPI serves the SPA at http://localhost:8080
cd ..
.\.venv\Scripts\uvicorn main:app --port 8080
```

---

## Key Environment Flags

| Flag | Default | Description |
|------|---------|-------------|
| `USE_MOCK_LLM` | `true` | Skip real Azure OpenAI calls |
| `USE_MOCK_SOTI` | `false` | Skip real SOTI MCP calls |
| `USE_MOCK_HITL` | `false` | Auto-approve all HITL gates |
| `USE_MOCK_COSMOS` | `false` | Skip Cosmos DB writes |
| `USE_MOCK_BLOB` | `false` | Skip Azure Blob download |
| `USE_WEB_HITL` | `false` | Use portal instead of console for HITL |
| `STATE_DIR` | `output` | Directory for all output files |

---

## Azure Resources

| Resource | Name | Usage |
|----------|------|-------|
| Cosmos DB (MongoDB vCore) | `agenticai-dashboard-dev-cosmosdb` | Intake records + audit write-back |
| Blob Storage | `agenticaidashboardsa` / container `fmi` | DVA Excel source files |
| Azure OpenAI | `pds-dev-agenticai-dashboard-azureopenai-foundry` | GPT model (when `USE_MOCK_LLM=false`) |

> **Blob write access:** Current account has read-only access. Output files are saved locally in `fleet-agents/output/` instead.

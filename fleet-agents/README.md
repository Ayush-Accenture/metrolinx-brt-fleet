# BRT Fleet Movement — Phase 1

A hybrid agentic system for automating BRT bus device movements in SOTI MDM.
LLM agents generate prose narrations for L2 review; all routing, comparisons,
and SOTI decisions are pure Python. No AI in the decision path.

---

## How the Hybrid Pattern Works

```
DVA Excel ──► excel_parser.py (pure code) ──► IntendedMove list
                                                      │
                                             ParserNarrator.narrate()
                                             (LLM → plain-English for L2)
                                                      │
                                              HITL-2 pre-approval
                                                      │
                                       SotiMcpClient.move_device() × N
                                                      │
                                           reconciler.py (pure code)
                                                      │
                                        ReconciliationNarrator.narrate()
                                             (LLM → report for L2)
                                                      │
                                              HITL-3 validation
                                                      │
                                        ExecutionNarrator.narrate()
                                             (LLM → SR notes + email)
                                                      │
                                              HITL-4 SR closure
```

**Rule:** LLM touches only the three `narrator.narrate()` calls.
Everything else is deterministic Python.

---

## 8-Stage Flow

```
Stage 1  RECEIVED          Initialise run document + connect to SOTI MCP
Stage 2  PARSING           Parse DVA Excel (pure code) + narrator summary
         ├─ HITL-schema    L2 reviews schema issues (if any)
Stage 3  PLANNED           L2 pre-approval of full move list (HITL-2)
Stage 4  MOVING            Execute moves via SOTI MCP tool calls
Stage 5  RECONCILING       Poll actual locations + reconcile (pure code)
                           + reconciliation narrator summary
Stage 6  AWAITING_VALID.   L2 validation of reconciliation result (HITL-3)
Stage 7  DRAFTING_SR       LLM drafts SR notes + email
         AWAITING_SR_APPR  L2 SR closure approval (HITL-4)
Stage 8  COMPLETED         Wrap-up (SR mocked; Graph + ServiceNow in Phase 2)
```

---

## Prerequisites

- Python 3.11
- `az login` already completed (DefaultAzureCredential used everywhere)
- `../soti_mcp_server/` sibling folder present (for real SOTI — mocked by default)

---

## Setup (4 commands)

```bash
cd fleet-agents

# 1. Create virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt

# 2. Copy example env (edit if needed — defaults work with mocks)
cp .env.example .env
```

---

## Run the Full Workflow with Mocks

```bash
# Interactive HITL prompts — you approve each gate manually
python run.py BRT-2026-06-16

# Fully unattended — all gates auto-approved
python run.py BRT-2026-06-16 --auto
```

The first run auto-creates `samples/sample_dva.xlsx` with 4 synthetic rows.
To use a real DVA, copy it over:

```bash
copy "C:\path\to\real_dva.xlsx" samples\sample_dva.xlsx
```

---

## Inspect the Run Document

```bash
# PowerShell
Get-Content state\run_BRT-2026-06-16.json

# Or pretty-print with Python
python -c "import json,pathlib; print(json.dumps(json.loads(pathlib.Path('state/run_BRT-2026-06-16.json').read_text()), indent=2))"
```

---

## How the Orchestrator Connects to soti_mcp_server

`mcp_clients/soti_client.py` uses the official MCP Python SDK.

**stdio mode (default for local dev):**
```
fleet-agents/ runs python -m soti_mcp_server in ../soti_mcp_server/
```

**HTTP mode:**
Set `SOTI_MCP_TRANSPORT=http` and `SOTI_MCP_HTTP_URL=http://localhost:8000/mcp`
in your `.env`.

Both modes are bypassed when `USE_MOCK_SOTI=true` (default).

---

## Flipping Mocks Off (when access lands)

| Flag | When to flip | What changes |
|---|---|---|
| `USE_MOCK_LLM=false` | OpenAI User role + `FOUNDRY_PROJECT_CONNECTION_STRING` set | Real LLM narrations via Azure AI Foundry |
| `USE_MOCK_SOTI=false` | `soti_mcp_server` confirmed working | Real SOTI move/get calls via MCP |
| `USE_MOCK_HITL=true` | Unattended scheduled runs | All HITL gates auto-approve |

Edit `.env` or export environment variables — no code changes needed.

**Before setting `USE_MOCK_SOTI=false`**, verify tool names in
`mcp_clients/soti_client.py` match the actual tool definitions in
`../soti_mcp_server/` (look for `TODO:` comments).

---

## TODO — Production Hardening (Phase 2+)

- [ ] Replace `SR-MOCK-*` with real ServiceNow MCP `create_incident` call
- [ ] Replace Fleet.xlsx append stub with Microsoft Graph MCP `upload_file` call
- [ ] Replace email stub with Graph `send_mail` call
- [ ] Add `--resume` full state-machine resume logic (currently informational)
- [ ] Add retry loop in Stage 4 for failed SOTI moves
- [ ] Add unit tests (pytest + mocks) — Phase 2.5
- [ ] Add Key Vault reference for `FOUNDRY_PROJECT_CONNECTION_STRING`
- [ ] Investigate DST-aware cron in Azure Container Apps Job (see fleet-phase1/README)
- [ ] Verify `get_device`, `move_device`, `search_devices` tool names against soti_mcp_server

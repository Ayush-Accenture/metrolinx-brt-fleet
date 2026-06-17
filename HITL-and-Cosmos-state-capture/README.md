# HITL Run State Machine — Python + Cosmos DB

Implementation of the **Durable Functions orchestration** state machine with
Human-in-the-Loop (HITL) gates, backed by Azure Cosmos DB.

---

## File layout

```
hitl/
├── models.py          # Enums, dataclasses: RunState, HITLGate, HITLDecision, RunRecord, Checkpoint, HITLEvent
├── cosmos_client.py   # HITLCosmosClient — provisions containers + typed CRUD helpers
├── state_machine.py   # RunStateMachine — every transition & HITL gate handler
├── example_run.py     # Happy-path walkthrough you can run locally
└── requirements.txt
```

---

## Cosmos DB containers

| Container | Partition key | Purpose | TTL |
|---|---|---|---|
| **runs** | `/partitionKey` (= runDate) | One document per run; mutable source of truth | none |
| **checkpoints** | `/partitionKey` (= runId) | Immutable transition log; resume-from-checkpoint | none |
| **hitl_events** | `/partitionKey` (= runId) | All human gate decisions with context snapshot | none |
| **schema_errors** | `/partitionKey` (= runId) | DVA schema / format-drift errors from PARSING | 90 days |
| **sr_drafts** | `/partitionKey` (= runId) | Service-request drafts; upserted on each edit | none |
| **move_exceptions** | `/partitionKey` (= runId) | Intended-vs-actual reconciliation discrepancies | 180 days |

All containers are created automatically on first call to `cosmos.provision()`.

---

## State transitions

```
RECEIVED
  ├─(file missing)──► ON_HOLD ──(HITL-1)──► PARSING / ABORTED
  └─(file ok)───────► PARSING
                         ├─(valid)──────► PLANNED ──► HITL-2 ──► MOVING ──► RECONCILING
                         └─(invalid)────► HITL_SCHEMA ──► PARSING / PLANNED / ABORTED

RECONCILING
  ├─(ok)────────────► HITL-3 ──► DRAFTING_SR ──► HITL-4 ──► EXECUTING ──► COMPLETED
  │                          └─(no moves)──────────────────────────────► COMPLETED
  └─(tool error)────► FAILED (HITL-Error) ──► RECONCILING / ABORTED
```

---

## Quick start

```bash
pip install azure-cosmos

export COSMOS_ENDPOINT="https://<account>.documents.azure.com:443/"
export COSMOS_KEY="<primary-key>"
export COSMOS_DB_NAME="RunOrchestration"   # optional, default shown

python example_run.py
```

---

## Using the state machine in your own code

```python
from cosmos_client import HITLCosmosClient
from models import HITLDecision, RunRecord
from state_machine import RunStateMachine
import uuid

cosmos = HITLCosmosClient(endpoint=..., key=..., database_name="RunOrchestration")
cosmos.provision()

run = RunRecord(id=str(uuid.uuid4()), run_date="2024-06-16", operator_id="jsmith")
sm  = RunStateMachine(cosmos=cosmos, run=run, operator_id="jsmith")

sm.receive(file_path="/intake/moves.xlsx")

# … call sm.check_file_by_deadline(), sm.parse(), sm.plan(), etc.
# Each step automatically checkpoints to Cosmos.

# Retrieve the full audit trail at any time
audit = sm.get_full_audit()
```

---

## HITL gate decision reference

| Gate | Trigger | Decisions |
|---|---|---|
| **HITL-1** | No file by 12:30 | WAIT · PLACE_FILE · ABORT_TODAY |
| **HITL-Schema** | Schema / format errors | FIX_REPLACE_RETRY · OVERRIDE_ACCEPT · ABORT |
| **HITL-2** | Always (R1 policy) | RECHECK_SOTI · APPROVE_ALL · APPROVE_SUBSET · SKIP · REJECT |
| **HITL-3** | After every LIVE run | RECHECK_SOTI · CORRECT_INLINE · EXCLUDE_FLAG · CONFIRM · RERUN |
| **HITL-4** | SR drafted | APPROVE_CLOSE · EDIT_DETAILS · KEEP_OPEN |
| **HITL-Error** | Tool / job failure | RETRY_FROM_FAILURE · EDIT_AND_RETRY · SKIP_DEVICE · ABORT |

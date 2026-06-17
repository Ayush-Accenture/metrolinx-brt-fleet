"""
example_run.py — Full happy-path walkthrough of the state machine.

Run locally (needs azure-cosmos installed):
    pip install azure-cosmos
    python example_run.py

Set the environment variables or replace the placeholders below.
"""

import logging
import os
import uuid
from datetime import date

from cosmos_client import HITLCosmosClient
from models import HITLDecision, RunRecord
from state_machine import RunStateMachine

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


# ---------------------------------------------------------------------------
# 1. Connect and provision Cosmos
# ---------------------------------------------------------------------------

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "https://<account>.documents.azure.com:443/")
COSMOS_KEY      = os.getenv("COSMOS_KEY",      "<primary-key>")
DATABASE_NAME   = os.getenv("COSMOS_DB_NAME",  "RunOrchestration")

cosmos = HITLCosmosClient(
    endpoint=COSMOS_ENDPOINT,
    key=COSMOS_KEY,
    database_name=DATABASE_NAME,
)
cosmos.provision()   # idempotent – creates DB + 6 containers if missing


# ---------------------------------------------------------------------------
# 2. Create a new run
# ---------------------------------------------------------------------------

today = date.today().isoformat()
run = RunRecord(
    id=str(uuid.uuid4()),
    run_date=today,
    operator_id="operator-jsmith",
)
run.partition_key = today   # partition by date

sm = RunStateMachine(cosmos=cosmos, run=run, operator_id="operator-jsmith")

# Register the run in Cosmos (RECEIVED state)
sm.receive(file_path="/intake/2024-06-16/moves.xlsx")
print(f"\n✔ Run created: {run.id}")


# ---------------------------------------------------------------------------
# 3. File arrived on time → no HITL-1
# ---------------------------------------------------------------------------

sm.check_file_by_deadline(file_arrived=True)
print(f"✔ File arrived – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 4. Parsing succeeds → PLANNED
# ---------------------------------------------------------------------------

sm.parse(schema_valid=True)
print(f"✔ Parsing OK – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 5. Plan the moves → HITL-2 gate opens
# ---------------------------------------------------------------------------

intended_moves = [
    {"device_id": "DEV-001", "from_group": "GroupA", "to_group": "GroupB"},
    {"device_id": "DEV-002", "from_group": "GroupA", "to_group": "GroupC"},
]
sm.plan(intended_moves=intended_moves)
print(f"✔ Planned {len(intended_moves)} moves – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 6. HITL-2: operator approves all moves
# ---------------------------------------------------------------------------

sm.handle_hitl_2(
    decision=HITLDecision.APPROVE_ALL,
    notes="Verified against SOTI; all moves look correct.",
)
print(f"✔ HITL-2 approved – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 7. Execute moves (LIVE)
# ---------------------------------------------------------------------------

actual_moves = [
    {"device_id": "DEV-001", "from_group": "GroupA", "to_group": "GroupB", "status": "ok"},
    {"device_id": "DEV-002", "from_group": "GroupA", "to_group": "GroupC", "status": "ok"},
]
sm.move(actual_moves=actual_moves)
print(f"✔ Moves executed – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 8. Reconcile (no exceptions)
# ---------------------------------------------------------------------------

sm.reconcile(exceptions=[])
print(f"✔ Reconciled – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 9. HITL-3: post-move validation – operator confirms
# ---------------------------------------------------------------------------

sm.handle_hitl_3(
    decision=HITLDecision.CONFIRM,
    notes="SOTI paths match intended moves. No exceptions.",
)
print(f"✔ HITL-3 confirmed – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 10. Draft SR
# ---------------------------------------------------------------------------

sm.draft_sr(
    sr_id=f"SR-{uuid.uuid4().hex[:8].upper()}",
    sr_notes="Automated SR: 2 devices moved from GroupA to GroupB/C.",
)
print(f"✔ SR drafted ({run.sr_id}) – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 11. HITL-4: SR closure – operator approves
# ---------------------------------------------------------------------------

sm.handle_hitl_4(
    decision=HITLDecision.APPROVE_CLOSE,
    notes="SR looks good.",
)
print(f"✔ HITL-4 SR closed – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 12. Execute (SR + tracker + summary) → COMPLETED
# ---------------------------------------------------------------------------

sm.execute(
    tracker_id=f"TRK-{uuid.uuid4().hex[:8].upper()}",
    summary={"devices_moved": 2, "exceptions": 0, "sr_id": run.sr_id},
)
print(f"✔ Run COMPLETED – state: {run.current_state}")


# ---------------------------------------------------------------------------
# 13. Print full audit trail
# ---------------------------------------------------------------------------

audit = sm.get_full_audit()
print(f"\n── Audit summary ──────────────────────────────────")
print(f"  Checkpoints : {len(audit['checkpoints'])}")
print(f"  HITL events : {len(audit['hitl_events'])}")
print(f"  SR draft    : {'yes' if audit['sr_draft'] else 'no'}")
print(f"  Exceptions  : {len(audit['exceptions'])}")
print(f"  Final state : {audit['run']['currentState']}")

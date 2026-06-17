"""
state_machine.py — RunStateMachine

Implements every state transition shown in the diagram.
Each public method corresponds to one node or gate in the flow.
All transitions are checkpointed to Cosmos before returning.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from models import (
    Checkpoint,
    HITLDecision,
    HITLEvent,
    HITLGate,
    RunRecord,
    RunState,
)
from cosmos_client import HITLCosmosClient

logger = logging.getLogger(__name__)


class InvalidTransitionError(Exception):
    pass


class RunStateMachine:
    """
    Orchestrates a single run through the state machine.

    Parameters
    ----------
    cosmos : HITLCosmosClient
        Provisioned Cosmos client (call .provision() before passing in).
    run : RunRecord
        New or rehydrated run document.
    operator_id : str
        Identity of the human operator driving HITL gates.
    """

    # Legal transitions: from_state -> [allowed to_states]
    TRANSITIONS: Dict[str, List[str]] = {
        RunState.RECEIVED:    [RunState.PARSING, RunState.ON_HOLD],
        RunState.ON_HOLD:     [RunState.PARSING, RunState.ABORTED],
        RunState.PARSING:     [RunState.PLANNED, RunState.HITL_SCHEMA],
        RunState.HITL_SCHEMA: [RunState.PARSING, RunState.PLANNED, RunState.ABORTED],
        RunState.PLANNED:     [RunState.HITL_2],
        RunState.HITL_2:      [RunState.MOVING, RunState.RECONCILING, RunState.ABORTED],
        RunState.MOVING:      [RunState.RECONCILING],
        RunState.RECONCILING: [RunState.HITL_3, RunState.FAILED],
        RunState.FAILED:      [RunState.RECONCILING, RunState.ABORTED],
        RunState.HITL_3:      [RunState.DRAFTING_SR, RunState.RECONCILING, RunState.COMPLETED],
        RunState.DRAFTING_SR: [RunState.HITL_4, RunState.ABORTED],
        RunState.HITL_4:      [RunState.EXECUTING],
        RunState.EXECUTING:   [RunState.COMPLETED],
        RunState.COMPLETED:   [],
        RunState.ABORTED:     [],
    }

    def __init__(
        self,
        cosmos: HITLCosmosClient,
        run: RunRecord,
        operator_id: str = "system",
    ) -> None:
        self._cosmos = cosmos
        self.run = run
        self.operator_id = operator_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(
        self,
        to_state: RunState,
        payload: Optional[Dict[str, Any]] = None,
        triggered_by: Optional[str] = None,
    ) -> None:
        """Validate → update run → checkpoint → persist."""
        from_state = self.run.current_state
        allowed = self.TRANSITIONS.get(from_state, [])
        if to_state not in allowed:
            raise InvalidTransitionError(
                f"Transition {from_state} → {to_state} is not allowed. "
                f"Legal targets: {allowed}"
            )

        # Update run document
        self.run.previous_state = from_state
        self.run.current_state = to_state
        self.run.updated_at = datetime.utcnow().isoformat()

        # Persist checkpoint (immutable)
        cp = Checkpoint(
            run_id=self.run.id,
            from_state=from_state,
            to_state=to_state,
            triggered_by=triggered_by or self.operator_id,
            payload=payload or {},
        )
        saved_cp = self._cosmos.append_checkpoint(cp.to_dict())
        self.run.last_checkpoint_id = saved_cp["id"]

        # Persist updated run
        self._cosmos.upsert_run(self.run.to_dict())
        logger.info("[%s] %s → %s", self.run.id[:8], from_state, to_state)

    def _record_hitl(
        self,
        gate: HITLGate,
        decision: HITLDecision,
        notes: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        evt = HITLEvent(
            run_id=self.run.id,
            gate=gate,
            decision=decision,
            operator_id=self.operator_id,
            notes=notes,
            context_snapshot=context or self._context_snapshot(),
        )
        self._cosmos.append_hitl_event(evt.to_dict())
        logger.info(
            "[%s] HITL gate=%s decision=%s operator=%s",
            self.run.id[:8], gate, decision, self.operator_id,
        )

    def _context_snapshot(self) -> Dict[str, Any]:
        return {
            "currentState":   self.run.current_state,
            "intendedMoves":  len(self.run.intended_moves),
            "actualMoves":    len(self.run.actual_moves),
            "exceptions":     len(self.run.exceptions),
            "srId":           self.run.sr_id,
        }

    # ------------------------------------------------------------------
    # State handlers — one per diagram node
    # ------------------------------------------------------------------

    # ── RECEIVED ────────────────────────────────────────────────────────

    def receive(self, file_path: Optional[str] = None) -> None:
        """Create the run and persist it in RECEIVED state."""
        self.run.intake_file_path = file_path
        self._cosmos.upsert_run(self.run.to_dict())
        logger.info("[%s] Run created in RECEIVED state.", self.run.id[:8])

    # ── HITL-1: late/missing file ────────────────────────────────────────

    def check_file_by_deadline(self, file_arrived: bool) -> None:
        """
        Called at/after 12:30.
        If file is present → move straight to PARSING.
        If missing → go ON_HOLD and wait for human decision.
        """
        if file_arrived:
            self._transition(RunState.PARSING, payload={"trigger": "file_on_time"})
        else:
            self._transition(
                RunState.ON_HOLD,
                payload={"trigger": "no_file_by_deadline"},
            )

    def handle_hitl_1(
        self,
        decision: HITLDecision,
        notes: str = "",
        new_file_path: Optional[str] = None,
    ) -> None:
        """
        Human response to HITL-1 (ON_HOLD).

        decision options
        ----------------
        WAIT            – keep on hold (no-op, operator will call again)
        PLACE_FILE      – file has been placed; move to PARSING
        ABORT_TODAY     – cancel today's run
        """
        self._record_hitl(HITLGate.HITL_1, decision, notes)

        if decision == HITLDecision.WAIT:
            logger.info("[%s] HITL-1: still waiting for file.", self.run.id[:8])
            return

        if decision == HITLDecision.PLACE_FILE:
            if new_file_path:
                self.run.intake_file_path = new_file_path
            self._transition(RunState.PARSING, payload={"trigger": "file_placed_by_operator"})

        elif decision == HITLDecision.ABORT_TODAY:
            self._transition(RunState.ABORTED, payload={"reason": "operator_abort_hitl1"})

    # ── PARSING ──────────────────────────────────────────────────────────

    def parse(
        self,
        schema_valid: bool,
        schema_errors: Optional[List[str]] = None,
    ) -> None:
        """
        Attempt to parse + validate the intake file.
        On success → PLANNED.
        On failure → HITL_SCHEMA.
        """
        if schema_valid:
            self.run.schema_errors = []
            self._transition(RunState.PLANNED, payload={"schema_valid": True})
        else:
            self.run.schema_errors = schema_errors or []
            # Persist schema error detail in its own container
            err_doc = {
                "id": str(uuid.uuid4()),
                "runId": self.run.id,
                "partitionKey": self.run.id,
                "timestamp": datetime.utcnow().isoformat(),
                "errors": schema_errors or [],
                "filePath": self.run.intake_file_path,
            }
            self._cosmos.upsert_schema_error(err_doc)
            self._transition(
                RunState.HITL_SCHEMA,
                payload={"schema_errors": schema_errors},
            )

    # ── HITL-Schema ──────────────────────────────────────────────────────

    def handle_hitl_schema(
        self,
        decision: HITLDecision,
        fixed_file_path: Optional[str] = None,
        notes: str = "",
    ) -> None:
        """
        Human response to schema validation failure.

        decision options
        ----------------
        FIX_REPLACE_RETRY – operator fixed the file; loop back to PARSING
        OVERRIDE_ACCEPT   – accept despite errors; continue to PLANNED
        ABORT             – cancel the run
        """
        self._record_hitl(HITLGate.HITL_SCHEMA, decision, notes)

        if decision == HITLDecision.FIX_REPLACE_RETRY:
            if fixed_file_path:
                self.run.intake_file_path = fixed_file_path
            self._transition(
                RunState.PARSING,
                payload={"trigger": "file_replaced_by_operator"},
            )

        elif decision == HITLDecision.OVERRIDE_ACCEPT:
            self._transition(
                RunState.PLANNED,
                payload={"trigger": "schema_override_accepted"},
            )

        elif decision == HITLDecision.ABORT:
            self._transition(RunState.ABORTED, payload={"reason": "operator_abort_schema"})

    # ── PLANNED ──────────────────────────────────────────────────────────

    def plan(self, intended_moves: List[Dict]) -> None:
        """Build the intended-move set (always → HITL-2 in R1)."""
        self.run.intended_moves = intended_moves
        self._transition(RunState.HITL_2, payload={"intended_moves": len(intended_moves)})

    # ── HITL-2: pre-move approval ─────────────────────────────────────────

    def handle_hitl_2(
        self,
        decision: HITLDecision,
        approved_moves: Optional[List[Dict]] = None,
        notes: str = "",
    ) -> None:
        """
        Human pre-move approval gate (always fires in R1).

        decision options
        ----------------
        RECHECK_SOTI    – re-fetch SOTI state before deciding (no transition)
        APPROVE_ALL     – approve every planned move → MOVING
        APPROVE_SUBSET  – approve a subset → MOVING with filtered list
        SKIP            – no movement needed → jump straight to RECONCILING
        REJECT          – cancel → ABORTED
        """
        self._record_hitl(HITLGate.HITL_2, decision, notes)

        if decision == HITLDecision.RECHECK_SOTI:
            logger.info("[%s] HITL-2: rechecking SOTI, no transition.", self.run.id[:8])
            return

        if decision in (HITLDecision.APPROVE_ALL, HITLDecision.APPROVE_SUBSET):
            if decision == HITLDecision.APPROVE_SUBSET and approved_moves is not None:
                self.run.intended_moves = approved_moves
            self._transition(RunState.MOVING, payload={"approved_moves": len(self.run.intended_moves)})

        elif decision == HITLDecision.SKIP:
            # "no movement → skip SR (per SOP)" dashed arrow in diagram
            self._transition(
                RunState.RECONCILING,
                payload={"trigger": "skip_no_movement"},
                triggered_by=self.operator_id,
            )

        elif decision == HITLDecision.REJECT:
            self._transition(RunState.ABORTED, payload={"reason": "operator_reject_hitl2"})

    # ── MOVING ────────────────────────────────────────────────────────────

    def move(self, actual_moves: List[Dict]) -> None:
        """Execute device moves and record actual results."""
        self.run.actual_moves = actual_moves
        self._transition(RunState.RECONCILING, payload={"actual_moves": len(actual_moves)})

    # ── RECONCILING ──────────────────────────────────────────────────────

    def reconcile(
        self,
        exceptions: Optional[List[Dict]] = None,
        tool_error: Optional[Dict] = None,
    ) -> None:
        """
        Auto-reconcile intended vs actual.
        Errors → FAILED (HITL-Error); success → HITL-3.
        """
        if tool_error:
            self.run.error_info = tool_error
            self._transition(RunState.FAILED, payload={"error": tool_error})
        else:
            self.run.exceptions = exceptions or []
            # Store each exception in its own container for easy querying
            for exc in self.run.exceptions:
                exc_doc = {
                    "id": str(uuid.uuid4()),
                    "runId": self.run.id,
                    "partitionKey": self.run.id,
                    "timestamp": datetime.utcnow().isoformat(),
                    **exc,
                }
                self._cosmos.upsert_move_exception(exc_doc)
            self._transition(RunState.HITL_3, payload={"exceptions": len(self.run.exceptions)})

    # ── HITL-Error (FAILED state) ──────────────────────────────────────────

    def handle_hitl_error(
        self,
        decision: HITLDecision,
        edit_payload: Optional[Dict] = None,
        notes: str = "",
    ) -> None:
        """
        Human response to a tool/job failure.

        decision options
        ----------------
        RETRY_FROM_FAILURE – resume from last good checkpoint → RECONCILING
        EDIT_AND_RETRY     – operator patches state, then retry → RECONCILING
        SKIP_DEVICE        – skip the failing device → RECONCILING
        ABORT              – give up → ABORTED
        """
        self._record_hitl(HITLGate.HITL_ERROR, decision, notes)

        if decision == HITLDecision.RETRY_FROM_FAILURE:
            self.run.error_info = None
            self._transition(RunState.RECONCILING, payload={"trigger": "retry_from_checkpoint"})

        elif decision == HITLDecision.EDIT_AND_RETRY:
            if edit_payload:
                self.run.metadata.update(edit_payload)
            self.run.error_info = None
            self._transition(RunState.RECONCILING, payload={"trigger": "edit_and_retry"})

        elif decision == HITLDecision.SKIP_DEVICE:
            self.run.error_info = None
            self._transition(RunState.RECONCILING, payload={"trigger": "device_skipped"})

        elif decision == HITLDecision.ABORT:
            self._transition(RunState.ABORTED, payload={"reason": "operator_abort_hitl_error"})

    # ── HITL-3: post-move validation ──────────────────────────────────────

    def handle_hitl_3(
        self,
        decision: HITLDecision,
        corrections: Optional[List[Dict]] = None,
        notes: str = "",
    ) -> None:
        """
        Human post-move validation (mandatory after every LIVE run).

        decision options
        ----------------
        RECHECK_SOTI    – re-fetch SOTI (no transition)
        CORRECT_INLINE  – operator applies NL/inline corrections → RECONCILING
        EXCLUDE_FLAG    – exclude / flag specific devices → RECONCILING
        CONFIRM         – all good → DRAFTING_SR
        RERUN           – something wrong; go back → RECONCILING
        SKIP            – no moves occurred, skip SR step → COMPLETED (via dashed arrow)
        """
        self._record_hitl(HITLGate.HITL_3, decision, notes)

        if decision == HITLDecision.RECHECK_SOTI:
            return

        if decision in (HITLDecision.CORRECT_INLINE, HITLDecision.EXCLUDE_FLAG):
            if corrections:
                self.run.exceptions.extend(corrections)
            self._transition(RunState.RECONCILING, payload={"trigger": decision})

        elif decision == HITLDecision.RERUN:
            self._transition(RunState.RECONCILING, payload={"trigger": "rerun_requested"})

        elif decision == HITLDecision.CONFIRM:
            self._transition(RunState.DRAFTING_SR, payload={"trigger": "post_move_confirmed"})

        elif decision == HITLDecision.SKIP:
            # "no movement → skip SR" dashed green arrow
            self._transition(RunState.COMPLETED, payload={"trigger": "skip_sr_no_movement"})

    # ── DRAFTING_SR ───────────────────────────────────────────────────────

    def draft_sr(self, sr_id: str, sr_notes: str) -> None:
        """Auto-create the SR and store the draft."""
        self.run.sr_id = sr_id
        self.run.sr_notes = sr_notes
        sr_doc = {
            "id": sr_id,
            "runId": self.run.id,
            "partitionKey": self.run.id,
            "timestamp": datetime.utcnow().isoformat(),
            "notes": sr_notes,
            "moves": self.run.actual_moves,
            "status": "draft",
        }
        self._cosmos.upsert_sr_draft(sr_doc)
        self._transition(RunState.HITL_4, payload={"srId": sr_id})

    def abort_from_drafting(self, notes: str = "") -> None:
        self._transition(RunState.ABORTED, payload={"reason": "operator_abort_drafting_sr", "notes": notes})

    # ── HITL-4: SR closure ─────────────────────────────────────────────────

    def handle_hitl_4(
        self,
        decision: HITLDecision,
        edited_notes: Optional[str] = None,
        notes: str = "",
    ) -> None:
        """
        Human SR closure gate.

        decision options
        ----------------
        APPROVE_CLOSE   – close the SR and proceed → EXECUTING
        EDIT_DETAILS    – operator edits SR notes (no transition until approved)
        KEEP_OPEN       – leave SR open (no transition)
        """
        self._record_hitl(HITLGate.HITL_4, decision, notes)

        if decision == HITLDecision.APPROVE_CLOSE:
            # Update SR draft to closed
            sr_doc = self._cosmos.get_sr_draft(self.run.id) or {}
            sr_doc["status"] = "closed"
            sr_doc["closedAt"] = datetime.utcnow().isoformat()
            self._cosmos.upsert_sr_draft(sr_doc)
            self._transition(RunState.EXECUTING, payload={"srStatus": "closed"})

        elif decision == HITLDecision.EDIT_DETAILS:
            if edited_notes:
                self.run.sr_notes = edited_notes
                sr_doc = self._cosmos.get_sr_draft(self.run.id) or {}
                sr_doc["notes"] = edited_notes
                self._cosmos.upsert_sr_draft(sr_doc)
                self._cosmos.upsert_run(self.run.to_dict())
            logger.info("[%s] HITL-4: SR details edited; awaiting approval.", self.run.id[:8])

        elif decision == HITLDecision.KEEP_OPEN:
            logger.info("[%s] HITL-4: SR kept open.", self.run.id[:8])

    # ── EXECUTING ─────────────────────────────────────────────────────────

    def execute(self, tracker_id: str, summary: Dict[str, Any]) -> None:
        """Produce SR tracker + summary artefacts, then complete."""
        self._transition(
            RunState.EXECUTING,
            payload={"trackerId": tracker_id},
        ) if self.run.current_state == RunState.HITL_4 else None
        self._transition(
            RunState.COMPLETED,
            payload={"trackerId": tracker_id, "summary": summary},
        )

    # ── Convenience: full run summary ────────────────────────────────────

    def get_full_audit(self) -> Dict[str, Any]:
        return {
            "run":          self.run.to_dict(),
            "checkpoints":  self._cosmos.get_checkpoints(self.run.id),
            "hitl_events":  self._cosmos.get_hitl_events(self.run.id),
            "schema_errors":self._cosmos.get_schema_errors(self.run.id),
            "sr_draft":     self._cosmos.get_sr_draft(self.run.id),
            "exceptions":   self._cosmos.get_move_exceptions(self.run.id),
        }

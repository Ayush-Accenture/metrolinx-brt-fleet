"""
models.py — Enums, dataclasses, and type definitions for the
Run State Machine (Durable Functions / HITL orchestration).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# State & gate enumerations
# ---------------------------------------------------------------------------

class RunState(str, Enum):
    """Every node in the state machine diagram."""
    RECEIVED        = "RECEIVED"
    ON_HOLD         = "ON_HOLD"          # HITL-1
    PARSING         = "PARSING"
    HITL_SCHEMA     = "HITL_SCHEMA"      # HITL-Schema gate
    PLANNED         = "PLANNED"
    HITL_2          = "HITL_2"           # pre-move approval
    MOVING          = "MOVING"
    RECONCILING     = "RECONCILING"
    FAILED          = "FAILED"           # HITL-Error
    HITL_3          = "HITL_3"           # post-move validation
    DRAFTING_SR     = "DRAFTING_SR"
    ABORTED         = "ABORTED"          # operator terminal stop
    HITL_4          = "HITL_4"           # SR closure
    EXECUTING       = "EXECUTING"
    COMPLETED       = "COMPLETED"


class HITLGate(str, Enum):
    HITL_1      = "HITL_1"
    HITL_SCHEMA = "HITL_SCHEMA"
    HITL_2      = "HITL_2"
    HITL_3      = "HITL_3"
    HITL_4      = "HITL_4"
    HITL_ERROR  = "HITL_ERROR"


class HITLDecision(str, Enum):
    # HITL-1
    WAIT                = "WAIT"
    PLACE_FILE          = "PLACE_FILE"
    ABORT_TODAY         = "ABORT_TODAY"
    # HITL-Schema
    FIX_REPLACE_RETRY   = "FIX_REPLACE_RETRY"
    OVERRIDE_ACCEPT     = "OVERRIDE_ACCEPT"
    ABORT               = "ABORT"
    # HITL-2
    RECHECK_SOTI        = "RECHECK_SOTI"
    APPROVE_ALL         = "APPROVE_ALL"
    APPROVE_SUBSET      = "APPROVE_SUBSET"
    SKIP                = "SKIP"
    REJECT              = "REJECT"
    # HITL-3
    CORRECT_INLINE      = "CORRECT_INLINE"
    EXCLUDE_FLAG        = "EXCLUDE_FLAG"
    CONFIRM             = "CONFIRM"
    RERUN               = "RERUN"
    # HITL-4
    APPROVE_CLOSE       = "APPROVE_CLOSE"
    EDIT_DETAILS        = "EDIT_DETAILS"
    KEEP_OPEN           = "KEEP_OPEN"
    # HITL-Error
    RETRY_FROM_FAILURE  = "RETRY_FROM_FAILURE"
    EDIT_AND_RETRY      = "EDIT_AND_RETRY"
    SKIP_DEVICE         = "SKIP_DEVICE"


class StateType(str, Enum):
    AUTOMATED = "automated"   # blue
    HITL_GATE = "hitl_gate"   # gold
    TERMINAL  = "terminal"    # red / green


# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------

@dataclass
class Checkpoint:
    """Single immutable transition record saved to Cosmos."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    from_state: str = ""
    to_state: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    triggered_by: str = "system"          # "system" | operator user-id
    payload: Dict[str, Any] = field(default_factory=dict)
    # Cosmos partition key convenience copy
    partition_key: str = ""               # filled = run_id at creation

    def __post_init__(self):
        if not self.partition_key:
            self.partition_key = self.run_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":           self.id,
            "runId":        self.run_id,
            "fromState":    self.from_state,
            "toState":      self.to_state,
            "timestamp":    self.timestamp,
            "triggeredBy":  self.triggered_by,
            "payload":      self.payload,
            "partitionKey": self.partition_key,
        }


@dataclass
class HITLEvent:
    """A human decision recorded at a gate."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    gate: str = ""                        # HITLGate value
    decision: str = ""                    # HITLDecision value
    operator_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    partition_key: str = ""

    def __post_init__(self):
        if not self.partition_key:
            self.partition_key = self.run_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":              self.id,
            "runId":           self.run_id,
            "gate":            self.gate,
            "decision":        self.decision,
            "operatorId":      self.operator_id,
            "timestamp":       self.timestamp,
            "notes":           self.notes,
            "contextSnapshot": self.context_snapshot,
            "partitionKey":    self.partition_key,
        }


@dataclass
class RunRecord:
    """Top-level run document — the single source of truth for a run."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_date: str = ""                    # e.g. "2024-06-16"
    current_state: str = RunState.RECEIVED
    previous_state: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    operator_id: str = ""
    intake_file_path: Optional[str] = None
    schema_errors: List[str] = field(default_factory=list)
    intended_moves: List[Dict] = field(default_factory=list)
    actual_moves: List[Dict] = field(default_factory=list)
    exceptions: List[Dict] = field(default_factory=list)
    sr_id: Optional[str] = None
    sr_notes: str = ""
    last_checkpoint_id: Optional[str] = None
    error_info: Optional[Dict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    partition_key: str = ""               # = run_date (for time-based partitioning)

    def __post_init__(self):
        if not self.partition_key:
            self.partition_key = self.run_date or self.id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":              self.id,
            "runDate":         self.run_date,
            "currentState":    self.current_state,
            "previousState":   self.previous_state,
            "createdAt":       self.created_at,
            "updatedAt":       self.updated_at,
            "operatorId":      self.operator_id,
            "intakeFilePath":  self.intake_file_path,
            "schemaErrors":    self.schema_errors,
            "intendedMoves":   self.intended_moves,
            "actualMoves":     self.actual_moves,
            "exceptions":      self.exceptions,
            "srId":            self.sr_id,
            "srNotes":         self.sr_notes,
            "lastCheckpointId":self.last_checkpoint_id,
            "errorInfo":       self.error_info,
            "metadata":        self.metadata,
            "partitionKey":    self.partition_key,
        }

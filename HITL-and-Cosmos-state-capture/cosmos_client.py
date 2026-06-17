"""
cosmos_client.py — Thin wrapper around azure-cosmos that:
  • provisions the database and all required containers on first run
  • exposes typed upsert / query helpers for each container
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Container definitions
# ---------------------------------------------------------------------------
# Each dict maps to one Cosmos container.
# partition_key  – the JSON property path used for partitioning
# ttl            – optional default TTL in seconds (None = no expiry)
# unique_keys    – optional unique-key policies

CONTAINER_SPECS: List[Dict[str, Any]] = [
    {
        "name": "runs",
        # One document per run; partitioned by runDate for even distribution
        # while keeping a whole day's runs on the same partition.
        "partition_key": "/partitionKey",   # value = runDate  e.g. "2024-06-16"
        "ttl": None,
        "unique_keys": [],
        "description": (
            "Top-level run documents. One document per run containing "
            "the full mutable run state (currentState, moves, SR info …)."
        ),
    },
    {
        "name": "checkpoints",
        # Immutable transition log; partitioned by runId so all checkpoints
        # for a single run land on the same logical partition.
        "partition_key": "/partitionKey",   # value = runId
        "ttl": None,
        "unique_keys": [],
        "description": (
            "Immutable event-sourcing log. One document per state transition. "
            "Used for resume-from-checkpoint and full audit trail."
        ),
    },
    {
        "name": "hitl_events",
        # Human decisions at each HITL gate; partitioned by runId.
        "partition_key": "/partitionKey",   # value = runId
        "ttl": None,
        "unique_keys": [],
        "description": (
            "All human-in-the-loop decisions (gate, decision, operator, notes, "
            "context snapshot). One document per human interaction."
        ),
    },
    {
        "name": "schema_errors",
        # Schema-validation failures during PARSING; partitioned by runId.
        "partition_key": "/partitionKey",   # value = runId
        "ttl": 60 * 60 * 24 * 90,          # auto-expire after 90 days
        "unique_keys": [],
        "description": (
            "DVA schema / format-drift errors captured at HITL-Schema gate. "
            "Stored separately for easy querying by validation engineers."
        ),
    },
    {
        "name": "sr_drafts",
        # SR (Service Request) drafts created during DRAFTING_SR; partitioned by runId.
        "partition_key": "/partitionKey",   # value = runId
        "ttl": None,
        "unique_keys": [],
        "description": (
            "Service-request drafts. One document per run (upserted). "
            "Contains auto-generated notes, move lists, and final closed state."
        ),
    },
    {
        "name": "move_exceptions",
        # Reconciliation exceptions found during HITL-3; partitioned by runId.
        "partition_key": "/partitionKey",   # value = runId
        "ttl": 60 * 60 * 24 * 180,         # 180-day retention
        "unique_keys": [],
        "description": (
            "Intended-vs-actual SOTI path discrepancies surfaced at HITL-3. "
            "Supports inline corrections and exclusion flags."
        ),
    },
]


# ---------------------------------------------------------------------------
# Synchronous client (use in Azure Functions / orchestrators)
# ---------------------------------------------------------------------------

class HITLCosmosClient:
    """
    Synchronous Cosmos DB client for the HITL state machine.

    Usage
    -----
    client = HITLCosmosClient(
        endpoint="https://<account>.documents.azure.com:443/",
        key="<primary-key>",
        database_name="RunOrchestration",
    )
    client.provision()          # idempotent – safe to call on every cold start
    client.upsert_run(run.to_dict())
    """

    def __init__(
        self,
        endpoint: str,
        key: str,
        database_name: str = "RunOrchestration",
        create_if_missing: bool = True,
    ) -> None:
        self._client = CosmosClient(endpoint, credential=key)
        self._db_name = database_name
        self._create_if_missing = create_if_missing
        self._db = None
        self._containers: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Provisioning
    # ------------------------------------------------------------------

    def provision(self) -> None:
        """Create database + all containers if they don't already exist."""
        try:
            self._db = self._client.create_database_if_not_exists(
                id=self._db_name,
                offer_throughput=400,       # shared RU/s; raise for production
            )
            logger.info("Database '%s' ready.", self._db_name)
        except exceptions.CosmosHttpResponseError as exc:
            logger.error("Failed to create database: %s", exc)
            raise

        for spec in CONTAINER_SPECS:
            try:
                pk_path = spec["partition_key"]
                kwargs: Dict[str, Any] = dict(
                    id=spec["name"],
                    partition_key=PartitionKey(path=pk_path),
                )
                if spec.get("ttl") is not None:
                    kwargs["default_ttl"] = spec["ttl"]
                if spec.get("unique_keys"):
                    kwargs["unique_key_policy"] = {
                        "uniqueKeys": [{"paths": uk} for uk in spec["unique_keys"]]
                    }
                container = self._db.create_container_if_not_exists(**kwargs)
                self._containers[spec["name"]] = container
                logger.info(
                    "Container '%s' ready (partition: %s).",
                    spec["name"],
                    pk_path,
                )
            except exceptions.CosmosHttpResponseError as exc:
                logger.error("Failed to create container '%s': %s", spec["name"], exc)
                raise

    def _container(self, name: str):
        if name not in self._containers:
            if self._db is None:
                self.provision()
            self._containers[name] = self._db.get_container_client(name)
        return self._containers[name]

    # ------------------------------------------------------------------
    # runs
    # ------------------------------------------------------------------

    def upsert_run(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return self._container("runs").upsert_item(doc)

    def get_run(self, run_id: str, partition_key: str) -> Optional[Dict[str, Any]]:
        try:
            return self._container("runs").read_item(
                item=run_id, partition_key=partition_key
            )
        except exceptions.CosmosResourceNotFoundError:
            return None

    def query_runs_by_date(self, run_date: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.runDate = @date"
        params = [{"name": "@date", "value": run_date}]
        return list(
            self._container("runs").query_items(
                query=query,
                parameters=params,
                partition_key=run_date,
            )
        )

    def query_runs_by_state(self, state: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.currentState = @state"
        params = [{"name": "@state", "value": state}]
        return list(
            self._container("runs").query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )

    # ------------------------------------------------------------------
    # checkpoints
    # ------------------------------------------------------------------

    def append_checkpoint(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Always INSERT (never upsert) to preserve immutable audit log."""
        return self._container("checkpoints").create_item(doc)

    def get_checkpoints(self, run_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.runId = @rid ORDER BY c.timestamp ASC"
        params = [{"name": "@rid", "value": run_id}]
        return list(
            self._container("checkpoints").query_items(
                query=query,
                parameters=params,
                partition_key=run_id,
            )
        )

    def get_last_checkpoint(self, run_id: str) -> Optional[Dict[str, Any]]:
        query = (
            "SELECT TOP 1 * FROM c WHERE c.runId = @rid "
            "ORDER BY c.timestamp DESC"
        )
        params = [{"name": "@rid", "value": run_id}]
        results = list(
            self._container("checkpoints").query_items(
                query=query,
                parameters=params,
                partition_key=run_id,
            )
        )
        return results[0] if results else None

    # ------------------------------------------------------------------
    # hitl_events
    # ------------------------------------------------------------------

    def append_hitl_event(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return self._container("hitl_events").create_item(doc)

    def get_hitl_events(self, run_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.runId = @rid ORDER BY c.timestamp ASC"
        params = [{"name": "@rid", "value": run_id}]
        return list(
            self._container("hitl_events").query_items(
                query=query,
                parameters=params,
                partition_key=run_id,
            )
        )

    def get_hitl_events_by_gate(
        self, run_id: str, gate: str
    ) -> List[Dict[str, Any]]:
        query = (
            "SELECT * FROM c WHERE c.runId = @rid AND c.gate = @gate "
            "ORDER BY c.timestamp ASC"
        )
        params = [
            {"name": "@rid", "value": run_id},
            {"name": "@gate", "value": gate},
        ]
        return list(
            self._container("hitl_events").query_items(
                query=query,
                parameters=params,
                partition_key=run_id,
            )
        )

    # ------------------------------------------------------------------
    # schema_errors
    # ------------------------------------------------------------------

    def upsert_schema_error(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return self._container("schema_errors").upsert_item(doc)

    def get_schema_errors(self, run_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.runId = @rid ORDER BY c.timestamp ASC"
        params = [{"name": "@rid", "value": run_id}]
        return list(
            self._container("schema_errors").query_items(
                query=query,
                parameters=params,
                partition_key=run_id,
            )
        )

    # ------------------------------------------------------------------
    # sr_drafts
    # ------------------------------------------------------------------

    def upsert_sr_draft(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return self._container("sr_drafts").upsert_item(doc)

    def get_sr_draft(self, run_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.runId = @rid"
        params = [{"name": "@rid", "value": run_id}]
        results = list(
            self._container("sr_drafts").query_items(
                query=query,
                parameters=params,
                partition_key=run_id,
            )
        )
        return results[0] if results else None

    # ------------------------------------------------------------------
    # move_exceptions
    # ------------------------------------------------------------------

    def upsert_move_exception(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return self._container("move_exceptions").upsert_item(doc)

    def get_move_exceptions(self, run_id: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.runId = @rid ORDER BY c.timestamp ASC"
        params = [{"name": "@rid", "value": run_id}]
        return list(
            self._container("move_exceptions").query_items(
                query=query,
                parameters=params,
                partition_key=run_id,
            )
        )

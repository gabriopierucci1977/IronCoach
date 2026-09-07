"""Insert-only SQLite repository for immutable MAINTAIN_PLAN contracts."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .models import (ActualSession, ExecutionEvaluation, MatchingResult,
                     PrescriptionMapping, PrescriptionSnapshot)
from .schema import run_migrations
from .serialization import PAYLOAD_SCHEMA_VERSION, deserialize_contract, serialize_contract
from .validators import (validate_actual_session, validate_execution_evaluation,
                         validate_mapping, validate_matching_result, validate_prescription)


class MaintainPlanRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        run_migrations(self.database_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _insert(self, sql: str, values: tuple[Any, ...]) -> None:
        with self._connect() as connection:
            connection.execute(sql, values)

    @staticmethod
    def _require_valid(errors: tuple[str, ...]) -> None:
        if errors:
            raise ValueError("; ".join(errors))

    def _get(self, table: str, id_column: str, identifier: str,
             expected_type: type[Any]) -> tuple[sqlite3.Row, Any] | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"SELECT * FROM {table} WHERE {id_column} = ?", (identifier,)
            ).fetchone()
        if row is None:
            return None
        if row["payload_schema_version"] != PAYLOAD_SCHEMA_VERSION:
            raise ValueError("unsupported stored MAINTAIN_PLAN payload schema version")
        return row, deserialize_contract(row["payload_json"], expected_type)

    def create_prescription_snapshot(self, value: PrescriptionSnapshot) -> None:
        self._require_valid(validate_prescription(value))
        self._insert(
            "INSERT INTO maintain_plan_prescription_snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (value.prescription_snapshot_id, value.workout_id, value.decision_id,
             value.contract_version, PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_prescription_snapshot(self, identifier: str) -> PrescriptionSnapshot | None:
        stored = self._get("maintain_plan_prescription_snapshots", "prescription_snapshot_id",
                           identifier, PrescriptionSnapshot)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_prescription(value))
        if (row["prescription_snapshot_id"], row["workout_id"], row["decision_id"],
                row["contract_version"]) != (value.prescription_snapshot_id, value.workout_id,
                                             value.decision_id, value.contract_version):
            raise ValueError("stored prescription snapshot metadata does not match payload")
        return value

    def create_actual_session(self, value: ActualSession) -> None:
        self._require_valid(validate_actual_session(value))
        self._insert(
            "INSERT INTO maintain_plan_actual_sessions VALUES (?, ?, ?, ?, ?, ?)",
            (value.session_id, value.start.isoformat(),
             None if value.composition is None else value.composition.value,
             value.contract_version, PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_actual_session(self, identifier: str) -> ActualSession | None:
        stored = self._get("maintain_plan_actual_sessions", "session_id", identifier, ActualSession)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_actual_session(value))
        metadata = (value.session_id, value.start.isoformat(),
                    None if value.composition is None else value.composition.value,
                    value.contract_version)
        if (row["session_id"], row["start"], row["composition"],
                row["contract_version"]) != metadata:
            raise ValueError("stored actual session metadata does not match payload")
        return value

    def create_prescription_mapping(self, value: PrescriptionMapping) -> None:
        self._require_valid(validate_mapping(value))
        snapshot = self.get_prescription_snapshot(value.prescription_snapshot_ref)
        session = self.get_actual_session(value.actual_session_ref)
        if snapshot is None or session is None:
            raise ValueError("mapping must reference a persisted snapshot and actual session")
        self._validate_mapping_refs(value, snapshot, session)
        self._insert(
            "INSERT INTO maintain_plan_prescription_mappings VALUES (?, ?, ?, ?, ?, ?)",
            (value.mapping_id, value.prescription_snapshot_ref, value.actual_session_ref,
             value.resolution_method.value, PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_prescription_mapping(self, identifier: str) -> PrescriptionMapping | None:
        stored = self._get("maintain_plan_prescription_mappings", "mapping_id", identifier,
                           PrescriptionMapping)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_mapping(value))
        if (row["mapping_id"], row["prescription_snapshot_ref"], row["actual_session_ref"],
                row["resolution_method"]) != (value.mapping_id,
                                               value.prescription_snapshot_ref,
                                               value.actual_session_ref,
                                               value.resolution_method.value):
            raise ValueError("stored prescription mapping metadata does not match payload")
        snapshot = self.get_prescription_snapshot(value.prescription_snapshot_ref)
        session = self.get_actual_session(value.actual_session_ref)
        if snapshot is None or session is None:
            raise ValueError("stored prescription mapping has unresolved references")
        self._validate_mapping_refs(value, snapshot, session)
        return value

    @staticmethod
    def _validate_mapping_refs(value: PrescriptionMapping, snapshot: PrescriptionSnapshot,
                               session: ActualSession) -> None:
        planned_ids = {item.component_id for item in snapshot.components}
        observed_ids = {item.component_id for item in session.components}
        if any(item.planned_component_ref.component_id not in planned_ids or
               (item.observed_component_ref is not None and
                item.observed_component_ref.component_id not in observed_ids)
               for item in value.component_mappings):
            raise ValueError("mapping contains an unresolvable component reference")

    def create_matching_result(self, value: MatchingResult) -> None:
        self._require_valid(validate_matching_result(value))
        mapping_ref = None
        if value.prescription_mapping is not None:
            mapping_ref = value.prescription_mapping.mapping_id
            stored = self.get_prescription_mapping(mapping_ref)
            if stored != value.prescription_mapping:
                raise ValueError("matching result must reference the exact persisted mapping")
        self._insert(
            "INSERT INTO maintain_plan_matching_results VALUES (?, ?, ?, ?, ?, ?, ?)",
            (value.matching_result_id, value.status.value, mapping_ref, value.policy.policy_id,
             value.policy.policy_version, PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_matching_result(self, identifier: str) -> MatchingResult | None:
        stored = self._get("maintain_plan_matching_results", "matching_result_id", identifier,
                           MatchingResult)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_matching_result(value))
        mapping_ref = (None if value.prescription_mapping is None
                       else value.prescription_mapping.mapping_id)
        if (row["matching_result_id"], row["status"], row["prescription_mapping_ref"],
                row["policy_id"], row["policy_version"]) != (
                    value.matching_result_id, value.status.value, mapping_ref,
                    value.policy.policy_id, value.policy.policy_version):
            raise ValueError("stored matching result metadata does not match payload")
        if value.prescription_mapping is not None:
            persisted = self.get_prescription_mapping(mapping_ref)
            if persisted != value.prescription_mapping:
                raise ValueError("stored matching result does not contain the exact mapping")
        return value

    def create_execution_evaluation(self, value: ExecutionEvaluation) -> None:
        mapping = self.get_prescription_mapping(value.prescription_mapping_ref)
        if mapping is None or (mapping.prescription_snapshot_ref != value.prescription_snapshot_ref or
                               mapping.actual_session_ref != value.actual_session_ref):
            raise ValueError("execution evaluation must reference the exact persisted mapping")
        snapshot = self.get_prescription_snapshot(value.prescription_snapshot_ref)
        if snapshot is None:
            raise ValueError("execution evaluation must reference a persisted snapshot")
        self._require_valid(validate_execution_evaluation(value, mapping, snapshot))
        self._insert(
            "INSERT INTO maintain_plan_execution_evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (value.evaluation_id, value.prescription_mapping_ref,
             value.prescription_snapshot_ref, value.actual_session_ref,
             None if value.overall is None else value.overall.value,
             value.policy.policy_id, value.policy.policy_version,
             PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_execution_evaluation(self, identifier: str) -> ExecutionEvaluation | None:
        stored = self._get("maintain_plan_execution_evaluations", "evaluation_id", identifier,
                           ExecutionEvaluation)
        if stored is None:
            return None
        row, value = stored
        metadata = (value.evaluation_id, value.prescription_mapping_ref,
                    value.prescription_snapshot_ref, value.actual_session_ref,
                    None if value.overall is None else value.overall.value,
                    value.policy.policy_id, value.policy.policy_version)
        if (row["evaluation_id"], row["prescription_mapping_ref"],
                row["prescription_snapshot_ref"], row["actual_session_ref"], row["overall"],
                row["policy_id"], row["policy_version"]) != metadata:
            raise ValueError("stored execution evaluation metadata does not match payload")
        mapping = self.get_prescription_mapping(value.prescription_mapping_ref)
        snapshot = self.get_prescription_snapshot(value.prescription_snapshot_ref)
        if mapping is None or snapshot is None:
            raise ValueError("stored execution evaluation has unresolved references")
        self._require_valid(validate_execution_evaluation(value, mapping, snapshot))
        return value

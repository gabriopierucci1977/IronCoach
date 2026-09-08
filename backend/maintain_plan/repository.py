"""Insert-only SQLite repository for immutable MAINTAIN_PLAN contracts."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Mapping

from .models import (ActualSession, Confirmation, ConfirmationAnswerType, ExecutionEvaluation, FeedbackEvent, FeedbackEventLog,
                     FeedbackProjection, MatchingResult, PrescriptionMapping,
                     PrescriptionSnapshot, SourceConflictProjection,
                     SourceConflictImpactEvaluation, SourceConflictResolutionEvent,
                     SourceConflictResolutionLog)
from .lifecycle_service import (project_feedback, project_source_conflict,
                                structurally_equivalent, validate_feedback_payload,
                                validate_feedback_event, validate_feedback_log,
                                validate_resolution_event, validate_resolution_log,
                                validate_source_conflict_projection)
from .schema import run_migrations
from .serialization import PAYLOAD_SCHEMA_VERSION, deserialize_contract, serialize_contract
from .validators import (validate_actual_session, validate_execution_evaluation,
                         validate_confirmation, validate_mapping, validate_matching_result,
                         validate_mapping_ownership, validate_prescription,
                         validate_source_conflict_impact)


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
        errors = validate_mapping_ownership(value, snapshot, session)
        if errors:
            raise ValueError("; ".join(errors))
        planned_ids = {item.component_id for item in snapshot.components}
        observed_ids = {item.component_id for item in session.components}
        if any((item.planned_component_ref is not None and
                item.planned_component_ref.component_id not in planned_ids) or
               (item.observed_component_ref is not None and
                item.observed_component_ref.component_id not in observed_ids)
               for item in value.component_mappings):
            raise ValueError("mapping contains an unresolvable component reference")
        planned_blocks = {(component.component_id, block.block_id)
                          for component in snapshot.components for block in component.structure.blocks}
        observed_blocks = {(component.component_id, block.block_id)
                           for component in session.components for block in component.blocks}
        observed_repetitions = {(component.component_id, block.block_id, repetition.repetition_id)
                                for component in session.components for block in component.blocks
                                for repetition in block.repetitions}
        planned_repetitions = {
            (component.component_id, block.block_id, index)
            for component in snapshot.components for block in component.structure.blocks
            for index in range(block.planned_repetitions or 0)
        }
        if any(item.planned_block_ref and
               (item.planned_block_ref.component_id, item.planned_block_ref.block_id) not in planned_blocks
               or item.observed_block_ref and
               (item.observed_block_ref.component_id, item.observed_block_ref.block_id) not in observed_blocks
               for item in value.block_mappings):
            raise ValueError("mapping contains an unresolvable block reference")
        if any(item.planned_repetition_ref and
               (item.planned_repetition_ref.component_id, item.planned_repetition_ref.block_id,
                item.planned_repetition_ref.repetition_index) not in planned_repetitions
               or item.observed_repetition_ref and
               (item.observed_repetition_ref.component_id, item.observed_repetition_ref.block_id,
                item.observed_repetition_ref.repetition_id) not in observed_repetitions
               for item in value.repetition_mappings):
            raise ValueError("mapping contains an unresolvable repetition reference")
        planned_transitions = {item.transition_id for item in snapshot.transitions}
        observed_transitions = {item.transition_id for item in session.transitions}
        if any(item.planned_transition_ref and item.planned_transition_ref.transition_id not in planned_transitions
               or item.observed_transition_ref and item.observed_transition_ref.transition_id not in observed_transitions
               for item in value.transition_mappings):
            raise ValueError("mapping contains an unresolvable transition reference")

    def create_confirmation(self, value: Confirmation) -> None:
        self._require_valid(validate_confirmation(value))
        result = self.get_matching_result(value.matching_result_ref)
        if result is None or result.prescription_snapshot_ref != value.prescription_snapshot_ref:
            raise ValueError("confirmation must reference the exact persisted matching result")
        if result.candidate_set != value.candidate_session_refs:
            raise ValueError("confirmation candidate set differs from matching result")
        if value.declared_session_refs != result.declared_session_refs:
            raise ValueError("confirmation declared sessions differ from matching result")
        if value.selected_session_ref is not None:
            allowed = (value.declared_session_refs
                       if value.answer_type is ConfirmationAnswerType.MANUAL_ASSOCIATION
                       else value.candidate_session_refs)
            if value.selected_session_ref not in allowed:
                raise ValueError("confirmation selected session is outside allowed sessions")
            if self.get_actual_session(value.selected_session_ref) is None:
                raise ValueError("confirmation selected session is unresolved")
        self._insert(
            "INSERT INTO maintain_plan_confirmations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (value.confirmation_id, value.matching_result_ref,
             value.prescription_snapshot_ref, value.status.value,
             None if value.answer_type is None else value.answer_type.value,
             value.selected_session_ref, PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_confirmation(self, identifier: str) -> Confirmation | None:
        stored = self._get("maintain_plan_confirmations", "confirmation_id", identifier,
                           Confirmation)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_confirmation(value))
        metadata = (value.confirmation_id, value.matching_result_ref,
                    value.prescription_snapshot_ref, value.status.value,
                    None if value.answer_type is None else value.answer_type.value,
                    value.selected_session_ref)
        if (row["confirmation_id"], row["matching_result_ref"],
                row["prescription_snapshot_ref"], row["status"], row["answer_type"],
                row["selected_session_ref"]) != metadata:
            raise ValueError("stored confirmation metadata does not match payload")
        result = self.get_matching_result(value.matching_result_ref)
        if (result is None or
                result.prescription_snapshot_ref != value.prescription_snapshot_ref or
                result.candidate_set != value.candidate_session_refs or
                result.declared_session_refs != value.declared_session_refs):
            raise ValueError("stored confirmation references are incoherent")
        return value

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
        session = self.get_actual_session(value.actual_session_ref)
        if session is None:
            raise ValueError("execution evaluation must reference a persisted actual session")
        for ref in value.source_conflict_projection_refs:
            projection = self.get_source_conflict_projection(ref.projection_id)
            if projection is None or (projection.projection_version, projection.projection_hash,
                    projection.projection_hash_algorithm,
                    projection.projection_serialization_policy_id,
                    projection.projection_serialization_policy_version) != (
                    ref.projection_version, ref.projection_hash, ref.projection_hash_algorithm,
                    ref.projection_serialization_policy_id,
                    ref.projection_serialization_policy_version):
                raise ValueError("execution evaluation source-conflict projection reference is unresolved or divergent")
        for ref in value.source_conflict_impact_evaluation_refs:
            impact = self.get_source_conflict_impact_evaluation(ref.conflict_impact_evaluation_id)
            if impact is None or impact.evaluation_version != ref.evaluation_version:
                raise ValueError("execution evaluation conflict-impact reference is unresolved or divergent")
        self._require_valid(validate_execution_evaluation(value, mapping, snapshot, session))
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
        session = self.get_actual_session(value.actual_session_ref)
        if mapping is None or snapshot is None or session is None:
            raise ValueError("stored execution evaluation has unresolved references")
        for ref in value.source_conflict_projection_refs:
            projection = self.get_source_conflict_projection(ref.projection_id)
            if projection is None or (projection.projection_version, projection.projection_hash,
                    projection.projection_hash_algorithm,
                    projection.projection_serialization_policy_id,
                    projection.projection_serialization_policy_version) != (
                    ref.projection_version, ref.projection_hash, ref.projection_hash_algorithm,
                    ref.projection_serialization_policy_id,
                    ref.projection_serialization_policy_version):
                raise ValueError("stored execution evaluation has divergent source-conflict projection")
        for ref in value.source_conflict_impact_evaluation_refs:
            impact = self.get_source_conflict_impact_evaluation(ref.conflict_impact_evaluation_id)
            if impact is None or impact.evaluation_version != ref.evaluation_version:
                raise ValueError("stored execution evaluation has divergent conflict impact")
        self._require_valid(validate_execution_evaluation(value, mapping, snapshot, session))
        return value

    def create_source_conflict_impact_evaluation(self, value: SourceConflictImpactEvaluation) -> None:
        self._require_valid(validate_source_conflict_impact(value))
        if value.prescription_mapping_ref is None:
            raise ValueError("persisted conflict impact requires a canonical mapping")
        mapping = self.get_prescription_mapping(value.prescription_mapping_ref)
        session = self.get_actual_session(value.source_conflict_ref.session_id)
        if mapping is None or session is None or mapping.actual_session_ref != session.session_id:
            raise ValueError("conflict impact ownership is unresolved")
        conflicts = [item for item in session.source_conflicts
                     if item.get("conflict_id") == value.source_conflict_ref.conflict_id]
        if len(conflicts) != 1:
            raise ValueError("conflict impact source reference is ghost or duplicated")
        self._insert(
            "INSERT INTO maintain_plan_source_conflict_impact_evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (value.conflict_impact_evaluation_id, value.evaluation_version,
             value.source_conflict_ref.session_id, value.source_conflict_ref.conflict_id,
             value.prescription_mapping_ref, value.status.value, value.policy.policy_id,
             value.policy.policy_version, PAYLOAD_SCHEMA_VERSION, serialize_contract(value)))

    def get_source_conflict_impact_evaluation(self, identifier: str) -> SourceConflictImpactEvaluation | None:
        stored = self._get("maintain_plan_source_conflict_impact_evaluations",
                           "conflict_impact_evaluation_id", identifier,
                           SourceConflictImpactEvaluation)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_source_conflict_impact(value))
        metadata = (value.conflict_impact_evaluation_id, value.evaluation_version,
                    value.source_conflict_ref.session_id, value.source_conflict_ref.conflict_id,
                    value.prescription_mapping_ref, value.status.value, value.policy.policy_id,
                    value.policy.policy_version)
        if tuple(row[key] for key in ("conflict_impact_evaluation_id", "evaluation_version",
                "session_id", "conflict_id", "prescription_mapping_ref", "status",
                "policy_id", "policy_version")) != metadata:
            raise ValueError("stored source-conflict impact metadata does not match payload")
        mapping = self.get_prescription_mapping(value.prescription_mapping_ref)
        session = self.get_actual_session(value.source_conflict_ref.session_id)
        if mapping is None or session is None or mapping.actual_session_ref != session.session_id or sum(
                item.get("conflict_id") == value.source_conflict_ref.conflict_id
                for item in session.source_conflicts) != 1:
            raise ValueError("stored source-conflict impact has unresolved ownership")
        return value

    def create_feedback_log(self, value: FeedbackEventLog) -> None:
        self._require_valid(validate_feedback_log(value))
        session = self.get_actual_session(value.actual_session_ref.session_id)
        if session is None or session.athlete_feedback is None:
            raise ValueError("feedback log must resolve an actual-session feedback baseline")
        baseline = session.athlete_feedback
        self._require_valid(validate_feedback_payload(baseline))
        if baseline.get("feedback_id") != value.feedback_ref.feedback_id:
            raise ValueError("feedback log does not identify the persisted baseline")
        self._insert(
            "INSERT INTO maintain_plan_feedback_logs VALUES (?, ?, ?, ?, ?, ?)",
            (value.feedback_log_id, value.actual_session_ref.session_id,
             value.feedback_ref.feedback_id, value.schema_version,
             PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_feedback_log(self, identifier: str) -> FeedbackEventLog | None:
        stored = self._get("maintain_plan_feedback_logs", "feedback_log_id", identifier,
                           FeedbackEventLog)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_feedback_log(value))
        if (row["feedback_log_id"], row["session_id"], row["feedback_id"], row["schema_version"]) != (
                value.feedback_log_id, value.actual_session_ref.session_id,
                value.feedback_ref.feedback_id, value.schema_version):
            raise ValueError("stored feedback log metadata does not match payload")
        session = self.get_actual_session(value.actual_session_ref.session_id)
        if session is None or session.athlete_feedback is None or session.athlete_feedback.get(
                "feedback_id") != value.feedback_ref.feedback_id:
            raise ValueError("stored feedback log has an unresolved baseline")
        self._require_valid(validate_feedback_payload(session.athlete_feedback))
        return value

    def append_feedback_event(self, value: FeedbackEvent) -> None:
        log = self.get_feedback_log(value.feedback_log_ref.feedback_log_id)
        if log is None:
            raise ValueError("feedback event must reference a persisted log")
        session = self.get_actual_session(log.actual_session_ref.session_id)
        baseline = None if session is None else session.athlete_feedback
        self._require_valid(validate_feedback_payload(baseline))
        self._require_valid(validate_feedback_event(value, log, baseline))
        if (baseline is None or baseline.get("schema_version") != value.baseline_schema_version or
                baseline.get("payload_hash") != value.baseline_payload_hash):
            raise ValueError("feedback event baseline metadata does not match persisted baseline")
        prior_events = self.list_feedback_events(log.feedback_log_id)
        candidate = project_feedback(
            projection_id="append-validation", projection_version="append-validation",
            log=log, baseline=baseline, events=prior_events + (value,), provenance={})
        if candidate.status.value == "INVALID":
            raise ValueError("; ".join(candidate.warnings))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT feedback_event_id, event_sequence FROM maintain_plan_feedback_events "
                "WHERE feedback_log_id = ? ORDER BY event_sequence DESC LIMIT 1",
                (log.feedback_log_id,),
            ).fetchone()
            expected_sequence = 1 if previous is None else previous[1] + 1
            expected_previous = None if previous is None else previous[0]
            if value.event_sequence != expected_sequence or value.previous_event_id != expected_previous:
                raise ValueError("feedback event sequence or previous_event_id is incoherent")
            if value.event_type.value == "CAPTURED" and previous is not None:
                raise ValueError("feedback lifecycle permits exactly one initial CAPTURED")
            if value.event_type.value != "CAPTURED" and previous is None:
                raise ValueError("feedback lifecycle must start with CAPTURED")
            connection.execute(
                "INSERT INTO maintain_plan_feedback_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (value.feedback_event_id, log.feedback_log_id,
                 log.actual_session_ref.session_id, log.feedback_ref.feedback_id,
                 value.event_sequence, value.event_type.value, value.previous_event_id,
                 PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
            )

    def list_feedback_events(self, feedback_log_id: str) -> tuple[FeedbackEvent, ...]:
        log = self.get_feedback_log(feedback_log_id)
        if log is None:
            raise ValueError("feedback log is unavailable")
        session = self.get_actual_session(log.actual_session_ref.session_id)
        baseline = None if session is None else session.athlete_feedback
        self._require_valid(validate_feedback_payload(baseline))
        return tuple(self._list_payloads(
            "maintain_plan_feedback_events", "feedback_log_id", feedback_log_id,
            "event_sequence", FeedbackEvent,
            lambda row, value: self._validate_feedback_event_row(row, value, log, baseline)))

    @staticmethod
    def _validate_feedback_event_row(row, value, log, baseline):
        errors = validate_feedback_event(value, log, baseline)
        if errors:
            raise ValueError("; ".join(errors))
        if (row["feedback_event_id"], row["feedback_log_id"], row["session_id"],
                row["feedback_id"], row["event_sequence"], row["event_type"],
                row["previous_event_id"]) != (
                value.feedback_event_id, value.feedback_log_ref.feedback_log_id,
                value.actual_session_ref.session_id, value.feedback_ref.feedback_id,
                value.event_sequence, value.event_type.value, value.previous_event_id):
            raise ValueError("stored feedback event metadata does not match payload")

    def create_feedback_projection(self, value: FeedbackProjection) -> None:
        log = self.get_feedback_log(value.feedback_log_ref.feedback_log_id)
        if log is None or value.feedback_ref != log.feedback_ref or value.actual_session_ref != log.actual_session_ref:
            raise ValueError("feedback projection references are incoherent")
        session = self.get_actual_session(log.actual_session_ref.session_id)
        expected = project_feedback(
            projection_id=value.projection_id, projection_version=value.projection_version,
            log=log, baseline=None if session is None else session.athlete_feedback,
            events=tuple(event for event in self.list_feedback_events(log.feedback_log_id)
                         if value.last_applied_sequence is not None and
                         event.event_sequence <= value.last_applied_sequence),
            provenance=value.provenance)
        if expected != value:
            raise ValueError("feedback projection does not match the persisted stream")
        self._insert(
            "INSERT INTO maintain_plan_feedback_projections VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (value.projection_id, value.projection_version, log.feedback_log_id,
             log.actual_session_ref.session_id, log.feedback_ref.feedback_id, value.status.value,
             PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_feedback_projection(self, identifier: str) -> FeedbackProjection | None:
        stored = self._get("maintain_plan_feedback_projections", "projection_id", identifier,
                           FeedbackProjection)
        if stored is None:
            return None
        row, value = stored
        if (row["projection_id"], row["projection_version"], row["feedback_log_id"],
                row["session_id"], row["feedback_id"], row["status"]) != (
                value.projection_id, value.projection_version,
                value.feedback_log_ref.feedback_log_id, value.actual_session_ref.session_id,
                value.feedback_ref.feedback_id, value.status.value):
            raise ValueError("stored feedback projection metadata does not match payload")
        if self.get_feedback_log(value.feedback_log_ref.feedback_log_id) is None:
            raise ValueError("stored feedback projection has an unresolved log")
        log = self.get_feedback_log(value.feedback_log_ref.feedback_log_id)
        session = self.get_actual_session(value.actual_session_ref.session_id)
        expected = project_feedback(
            projection_id=value.projection_id, projection_version=value.projection_version,
            log=log, baseline=None if session is None else session.athlete_feedback,
            events=tuple(event for event in self.list_feedback_events(log.feedback_log_id)
                         if value.last_applied_sequence is not None and
                         event.event_sequence <= value.last_applied_sequence),
            provenance=value.provenance)
        if expected != value:
            raise ValueError("stored feedback projection does not match its stream")
        return value

    def create_source_conflict(self, session_id: str, value: Mapping[str, Any]) -> None:
        session = self.get_actual_session(session_id)
        matches = (() if session is None else tuple(
            item for item in session.source_conflicts if structurally_equivalent(item, value)))
        if len(matches) != 1:
            raise ValueError("source conflict must resolve exactly in the persisted session")
        canonical = matches[0]
        if (canonical.get("session_id", session_id) != session_id or
                canonical.get("schema_version") != "maintain-plan-source-conflict/1.0.0-draft"):
            raise ValueError("source conflict schema version is unsupported")
        self._insert(
            "INSERT INTO maintain_plan_source_conflicts VALUES (?, ?, ?, ?, ?)",
            (canonical["conflict_id"], session_id, canonical["schema_version"],
             PAYLOAD_SCHEMA_VERSION, serialize_contract(canonical)),
        )

    def get_source_conflict(self, session_id: str, conflict_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM maintain_plan_source_conflicts WHERE session_id = ? AND conflict_id = ?",
                (session_id, conflict_id)).fetchone()
        if row is None:
            return None
        value = deserialize_contract(row["payload_json"], dict)
        if (row["payload_schema_version"] != PAYLOAD_SCHEMA_VERSION or
                row["conflict_id"] != value.get("conflict_id") or
                row["schema_version"] != value.get("schema_version")):
            raise ValueError("stored source conflict metadata does not match payload")
        session = self.get_actual_session(session_id)
        matches = (() if session is None else tuple(
            item for item in session.source_conflicts if structurally_equivalent(item, value)))
        if len(matches) != 1 or value.get("session_id", session_id) != session_id:
            raise ValueError("stored source conflict does not resolve exactly in its session")
        return value

    def create_resolution_log(self, value: SourceConflictResolutionLog) -> None:
        self._require_valid(validate_resolution_log(value))
        if self.get_source_conflict(value.actual_session_ref.session_id,
                                    value.conflict_ref.conflict_id) is None:
            raise ValueError("resolution log must reference a persisted source conflict")
        self._insert(
            "INSERT INTO maintain_plan_resolution_logs VALUES (?, ?, ?, ?, ?, ?)",
            (value.resolution_log_id, value.conflict_ref.conflict_id,
             value.actual_session_ref.session_id, value.schema_version,
             PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_resolution_log(self, identifier: str) -> SourceConflictResolutionLog | None:
        stored = self._get("maintain_plan_resolution_logs", "resolution_log_id", identifier,
                           SourceConflictResolutionLog)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_resolution_log(value))
        if (row["resolution_log_id"], row["conflict_id"], row["session_id"], row["schema_version"]) != (
                value.resolution_log_id, value.conflict_ref.conflict_id,
                value.actual_session_ref.session_id, value.schema_version):
            raise ValueError("stored resolution log metadata does not match payload")
        if self.get_source_conflict(value.actual_session_ref.session_id,
                                    value.conflict_ref.conflict_id) is None:
            raise ValueError("stored resolution log has an unresolved conflict")
        return value

    def append_resolution_event(self, value: SourceConflictResolutionEvent) -> None:
        log = self.get_resolution_log(value.resolution_log_id)
        if log is None:
            raise ValueError("resolution event must reference a persisted log")
        self._require_valid(validate_resolution_event(value, log))
        conflict = self.get_source_conflict(log.actual_session_ref.session_id,
                                            log.conflict_ref.conflict_id)
        prior_events = self.list_resolution_events(log.resolution_log_id)
        candidate = project_source_conflict(
            projection_id="append-validation", projection_version="append-validation",
            log=log, source_conflict=conflict, events=prior_events + (value,),
            provenance={}, computed_at=value.occurred_at)
        if candidate.status.value == "INVALID":
            raise ValueError("; ".join(candidate.warnings))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT event_id, event_sequence FROM maintain_plan_resolution_events "
                "WHERE resolution_log_id = ? ORDER BY event_sequence DESC LIMIT 1",
                (log.resolution_log_id,),).fetchone()
            expected_sequence = 1 if previous is None else previous[1] + 1
            expected_previous = None if previous is None else previous[0]
            if value.event_sequence != expected_sequence or value.previous_event_id != expected_previous:
                raise ValueError("resolution event sequence or previous_event_id is incoherent")
            connection.execute(
                "INSERT INTO maintain_plan_resolution_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (value.event_id, value.resolution_log_id, value.source_conflict_id,
                 value.actual_session_ref.session_id, value.event_sequence,
                 value.event_type.value, value.previous_event_id, PAYLOAD_SCHEMA_VERSION,
                 serialize_contract(value)),
            )

    def list_resolution_events(self, resolution_log_id: str) -> tuple[SourceConflictResolutionEvent, ...]:
        log = self.get_resolution_log(resolution_log_id)
        if log is None:
            raise ValueError("resolution log is unavailable")
        return tuple(self._list_payloads(
            "maintain_plan_resolution_events", "resolution_log_id", resolution_log_id,
            "event_sequence", SourceConflictResolutionEvent,
            lambda row, value: self._validate_resolution_event_row(row, value, log)))

    @staticmethod
    def _validate_resolution_event_row(row, value, log):
        errors = validate_resolution_event(value, log)
        if errors:
            raise ValueError("; ".join(errors))
        if (row["event_id"], row["resolution_log_id"], row["conflict_id"], row["session_id"],
                row["event_sequence"], row["event_type"], row["previous_event_id"]) != (
                value.event_id, value.resolution_log_id, value.source_conflict_id,
                value.actual_session_ref.session_id, value.event_sequence,
                value.event_type.value, value.previous_event_id):
            raise ValueError("stored resolution event metadata does not match payload")

    def create_source_conflict_projection(self, value: SourceConflictProjection) -> None:
        self._require_valid(validate_source_conflict_projection(value))
        log = self.get_resolution_log(value.resolution_log_ref.resolution_log_id)
        if log is None or (value.resolution_log_ref.source_conflict_id != log.conflict_ref.conflict_id or
                           value.resolution_log_ref.session_id != log.actual_session_ref.session_id or
                           value.source_conflict_id != log.conflict_ref.conflict_id or
                           value.actual_session_ref != log.actual_session_ref):
            raise ValueError("source conflict projection references are incoherent")
        expected = project_source_conflict(
            projection_id=value.projection_id, projection_version=value.projection_version,
            log=log, source_conflict=self.get_source_conflict(
                value.actual_session_ref.session_id, value.source_conflict_id),
            events=tuple(event for event in self.list_resolution_events(log.resolution_log_id)
                         if value.through_event_sequence is not None and
                         event.event_sequence <= value.through_event_sequence),
            provenance=value.provenance, computed_at=value.computed_at)
        if expected != value:
            raise ValueError("source conflict projection does not match the persisted stream")
        self._insert(
            "INSERT INTO maintain_plan_source_conflict_projections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (value.projection_id, value.projection_version, log.resolution_log_id,
             value.source_conflict_id, value.actual_session_ref.session_id, value.status.value,
             value.projection_hash, PAYLOAD_SCHEMA_VERSION, serialize_contract(value)),
        )

    def get_source_conflict_projection(self, identifier: str) -> SourceConflictProjection | None:
        stored = self._get("maintain_plan_source_conflict_projections", "projection_id", identifier,
                           SourceConflictProjection)
        if stored is None:
            return None
        row, value = stored
        self._require_valid(validate_source_conflict_projection(value))
        if (row["projection_id"], row["projection_version"], row["resolution_log_id"],
                row["conflict_id"], row["session_id"], row["status"], row["projection_hash"]) != (
                value.projection_id, value.projection_version,
                value.resolution_log_ref.resolution_log_id, value.source_conflict_id,
                value.actual_session_ref.session_id, value.status.value, value.projection_hash):
            raise ValueError("stored source conflict projection metadata does not match payload")
        if self.get_resolution_log(value.resolution_log_ref.resolution_log_id) is None:
            raise ValueError("stored source conflict projection has an unresolved log")
        log = self.get_resolution_log(value.resolution_log_ref.resolution_log_id)
        expected = project_source_conflict(
            projection_id=value.projection_id, projection_version=value.projection_version,
            log=log, source_conflict=self.get_source_conflict(
                value.actual_session_ref.session_id, value.source_conflict_id),
            events=tuple(event for event in self.list_resolution_events(log.resolution_log_id)
                         if value.through_event_sequence is not None and
                         event.event_sequence <= value.through_event_sequence),
            provenance=value.provenance, computed_at=value.computed_at)
        if expected != value:
            raise ValueError("stored source conflict projection does not match its stream")
        return value

    def _list_payloads(self, table: str, where_column: str, identifier: str,
                       order_column: str, expected_type: type[Any], validator):
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE {where_column} = ? ORDER BY {order_column}",
                (identifier,)).fetchall()
        values = []
        for row in rows:
            if row["payload_schema_version"] != PAYLOAD_SCHEMA_VERSION:
                raise ValueError("unsupported stored MAINTAIN_PLAN payload schema version")
            value = deserialize_contract(row["payload_json"], expected_type)
            validator(row, value)
            values.append(value)
        return values

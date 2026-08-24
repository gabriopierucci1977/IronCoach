"""
IronCoach Decision Memory Repository

Persistenza SQLite dei DecisionEpisode.

Responsabilità:
- inizializzare il database Decision Memory;
- creare nuovi episodi;
- leggere episodi per episode_id;
- aggiornare il ciclo di vita di episodi esistenti;
- serializzare e ricostruire i campi strutturati JSON.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from backend.decision_memory.schema import initialize_database
from backend.models.decision_episode import DecisionEpisode


PathLike = Union[str, Path]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


class DecisionMemoryRepository:

    def __init__(
        self,
        database_path: PathLike,
    ):
        self.database_path = Path(
            database_path
        )

        initialize_database(
            self.database_path
        )

    def create(
        self,
        episode: DecisionEpisode,
    ) -> None:
        """
        Persiste un nuovo DecisionEpisode.

        episode_id è la chiave primaria.
        decision_id, quando presente, è univoco.
        """

        record = self._episode_to_record(
            episode
        )

        connection = sqlite3.connect(
            self.database_path
        )

        try:
            connection.execute(
                """
                INSERT INTO decision_episodes (
                    episode_id,
                    athlete_id,
                    decision_id,
                    decision_timestamp,
                    status,
                    schema_version,
                    decision_action,
                    strategy,
                    rule_id,
                    primary_intent,
                    decision_confidence,
                    supporting_intents_json,
                    pre_decision_state_json,
                    athlete_state_json,
                    planned_workout_json,
                    recommended_workout_json,
                    actual_activity_json,
                    actual_activity_id,
                    actual_activity_source,
                    adherence_status,
                    adherence_evidence_json,
                    adherence_evaluated_at,
                    outcome_24h_status,
                    outcome_24h_evidence_json,
                    outcome_24h_evaluated_at,
                    outcome_72h_status,
                    outcome_72h_evidence_json,
                    outcome_72h_evaluated_at,
                    outcome_7d_status,
                    outcome_7d_evidence_json,
                    outcome_7d_evaluated_at,
                    overall_outcome_status,
                    overall_outcome_confidence,
                    overall_outcome_evidence_json,
                    overall_outcome_evaluated_at,
                    decision_engine_version,
                    adherence_evaluator_version,
                    outcome_evaluator_version,
                    airtable_decision_record_id,
                    created_at,
                    updated_at
                )
                VALUES (
                    :episode_id,
                    :athlete_id,
                    :decision_id,
                    :decision_timestamp,
                    :status,
                    :schema_version,
                    :decision_action,
                    :strategy,
                    :rule_id,
                    :primary_intent,
                    :decision_confidence,
                    :supporting_intents_json,
                    :pre_decision_state_json,
                    :athlete_state_json,
                    :planned_workout_json,
                    :recommended_workout_json,
                    :actual_activity_json,
                    :actual_activity_id,
                    :actual_activity_source,
                    :adherence_status,
                    :adherence_evidence_json,
                    :adherence_evaluated_at,
                    :outcome_24h_status,
                    :outcome_24h_evidence_json,
                    :outcome_24h_evaluated_at,
                    :outcome_72h_status,
                    :outcome_72h_evidence_json,
                    :outcome_72h_evaluated_at,
                    :outcome_7d_status,
                    :outcome_7d_evidence_json,
                    :outcome_7d_evaluated_at,
                    :overall_outcome_status,
                    :overall_outcome_confidence,
                    :overall_outcome_evidence_json,
                    :overall_outcome_evaluated_at,
                    :decision_engine_version,
                    :adherence_evaluator_version,
                    :outcome_evaluator_version,
                    :airtable_decision_record_id,
                    :created_at,
                    :updated_at
                )
                """,
                record,
            )

            connection.commit()

        finally:
            connection.close()

    def get_by_episode_id(
        self,
        episode_id: str,
    ) -> Optional[DecisionEpisode]:
        """
        Restituisce il DecisionEpisode richiesto oppure None
        quando episode_id non è presente.
        """

        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = sqlite3.Row

        try:
            row = connection.execute(
                """
                SELECT *
                FROM decision_episodes
                WHERE episode_id = ?
                """,
                (
                    episode_id,
                ),
            ).fetchone()

        finally:
            connection.close()

        if row is None:
            return None

        return self._row_to_episode(
            row
        )

    def update(
        self,
        episode: DecisionEpisode,
    ) -> None:
        """
        Aggiorna lo stato evolutivo di un DecisionEpisode esistente.

        I dati identitari e la decisione originale non vengono riscritti.
        Vengono aggiornati solo i campi che maturano dopo la decisione.
        """

        episode.updated_at = _utc_now()

        record = self._episode_to_record(
            episode
        )

        connection = sqlite3.connect(
            self.database_path
        )

        try:
            cursor = connection.execute(
                """
                UPDATE decision_episodes
                SET
                    status = :status,
                    actual_activity_json = :actual_activity_json,
                    actual_activity_id = :actual_activity_id,
                    actual_activity_source = :actual_activity_source,
                    adherence_status = :adherence_status,
                    adherence_evidence_json = :adherence_evidence_json,
                    adherence_evaluated_at = :adherence_evaluated_at,
                    outcome_24h_status = :outcome_24h_status,
                    outcome_24h_evidence_json = :outcome_24h_evidence_json,
                    outcome_24h_evaluated_at = :outcome_24h_evaluated_at,
                    outcome_72h_status = :outcome_72h_status,
                    outcome_72h_evidence_json = :outcome_72h_evidence_json,
                    outcome_72h_evaluated_at = :outcome_72h_evaluated_at,
                    outcome_7d_status = :outcome_7d_status,
                    outcome_7d_evidence_json = :outcome_7d_evidence_json,
                    outcome_7d_evaluated_at = :outcome_7d_evaluated_at,
                    overall_outcome_status = :overall_outcome_status,
                    overall_outcome_confidence = :overall_outcome_confidence,
                    overall_outcome_evidence_json = :overall_outcome_evidence_json,
                    overall_outcome_evaluated_at = :overall_outcome_evaluated_at,
                    adherence_evaluator_version = :adherence_evaluator_version,
                    outcome_evaluator_version = :outcome_evaluator_version,
                    airtable_decision_record_id = :airtable_decision_record_id,
                    updated_at = :updated_at
                WHERE episode_id = :episode_id
                """,
                record,
            )

            if cursor.rowcount == 0:
                raise KeyError(
                    f"DecisionEpisode non trovato: {episode.episode_id}"
                )

            connection.commit()

        finally:
            connection.close()

    def _episode_to_record(
        self,
        episode: DecisionEpisode,
    ) -> Dict[str, Any]:

        return {
            "episode_id": episode.episode_id,
            "athlete_id": episode.athlete_id,
            "decision_id": episode.decision_id,
            "decision_timestamp": episode.decision_timestamp,
            "status": episode.status,
            "schema_version": episode.schema_version,
            "decision_action": episode.decision_action,
            "strategy": episode.strategy,
            "rule_id": episode.rule_id,
            "primary_intent": episode.primary_intent,
            "decision_confidence": episode.decision_confidence,
            "supporting_intents_json": self._dump_json(
                episode.supporting_intents
            ),
            "pre_decision_state_json": self._dump_json(
                episode.pre_decision_state
            ),
            "athlete_state_json": self._dump_json(
                episode.athlete_state
            ),
            "planned_workout_json": self._dump_optional_json(
                episode.planned_workout
            ),
            "recommended_workout_json": self._dump_optional_json(
                episode.recommended_workout
            ),
            "actual_activity_json": self._dump_optional_json(
                episode.actual_activity
            ),
            "actual_activity_id": episode.actual_activity_id,
            "actual_activity_source": episode.actual_activity_source,
            "adherence_status": episode.adherence_status,
            "adherence_evidence_json": self._dump_json(
                episode.adherence_evidence
            ),
            "adherence_evaluated_at": episode.adherence_evaluated_at,
            "outcome_24h_status": episode.outcome_24h_status,
            "outcome_24h_evidence_json": self._dump_json(
                episode.outcome_24h_evidence
            ),
            "outcome_24h_evaluated_at": episode.outcome_24h_evaluated_at,
            "outcome_72h_status": episode.outcome_72h_status,
            "outcome_72h_evidence_json": self._dump_json(
                episode.outcome_72h_evidence
            ),
            "outcome_72h_evaluated_at": episode.outcome_72h_evaluated_at,
            "outcome_7d_status": episode.outcome_7d_status,
            "outcome_7d_evidence_json": self._dump_json(
                episode.outcome_7d_evidence
            ),
            "outcome_7d_evaluated_at": episode.outcome_7d_evaluated_at,
            "overall_outcome_status": episode.overall_outcome_status,
            "overall_outcome_confidence": (
                episode.overall_outcome_confidence
            ),
            "overall_outcome_evidence_json": self._dump_json(
                episode.overall_outcome_evidence
            ),
            "overall_outcome_evaluated_at": (
                episode.overall_outcome_evaluated_at
            ),
            "decision_engine_version": episode.decision_engine_version,
            "adherence_evaluator_version": (
                episode.adherence_evaluator_version
            ),
            "outcome_evaluator_version": episode.outcome_evaluator_version,
            "airtable_decision_record_id": (
                episode.airtable_decision_record_id
            ),
            "created_at": episode.created_at,
            "updated_at": episode.updated_at,
        }

    def _row_to_episode(
        self,
        row: sqlite3.Row,
    ) -> DecisionEpisode:

        return DecisionEpisode(
            athlete_id=row["athlete_id"],
            decision_timestamp=row["decision_timestamp"],
            decision_action=row["decision_action"],
            rule_id=row["rule_id"],
            primary_intent=row["primary_intent"],
            pre_decision_state=self._load_json(
                row["pre_decision_state_json"],
                {},
            ),
            athlete_state=self._load_json(
                row["athlete_state_json"],
                {},
            ),
            episode_id=row["episode_id"],
            decision_id=row["decision_id"],
            status=row["status"],
            schema_version=row["schema_version"],
            strategy=row["strategy"],
            decision_confidence=row["decision_confidence"],
            supporting_intents=self._load_json(
                row["supporting_intents_json"],
                [],
            ),
            planned_workout=self._load_optional_json(
                row["planned_workout_json"]
            ),
            recommended_workout=self._load_optional_json(
                row["recommended_workout_json"]
            ),
            actual_activity=self._load_optional_json(
                row["actual_activity_json"]
            ),
            actual_activity_id=row["actual_activity_id"],
            actual_activity_source=row["actual_activity_source"],
            adherence_status=row["adherence_status"],
            adherence_evidence=self._load_json(
                row["adherence_evidence_json"],
                {},
            ),
            adherence_evaluated_at=row["adherence_evaluated_at"],
            outcome_24h_status=row["outcome_24h_status"],
            outcome_24h_evidence=self._load_json(
                row["outcome_24h_evidence_json"],
                {},
            ),
            outcome_24h_evaluated_at=row["outcome_24h_evaluated_at"],
            outcome_72h_status=row["outcome_72h_status"],
            outcome_72h_evidence=self._load_json(
                row["outcome_72h_evidence_json"],
                {},
            ),
            outcome_72h_evaluated_at=row["outcome_72h_evaluated_at"],
            outcome_7d_status=row["outcome_7d_status"],
            outcome_7d_evidence=self._load_json(
                row["outcome_7d_evidence_json"],
                {},
            ),
            outcome_7d_evaluated_at=row["outcome_7d_evaluated_at"],
            overall_outcome_status=row["overall_outcome_status"],
            overall_outcome_confidence=row["overall_outcome_confidence"],
            overall_outcome_evidence=self._load_json(
                row["overall_outcome_evidence_json"],
                {},
            ),
            overall_outcome_evaluated_at=(
                row["overall_outcome_evaluated_at"]
            ),
            decision_engine_version=row["decision_engine_version"],
            adherence_evaluator_version=(
                row["adherence_evaluator_version"]
            ),
            outcome_evaluator_version=row["outcome_evaluator_version"],
            airtable_decision_record_id=(
                row["airtable_decision_record_id"]
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _dump_json(
        value: Any,
    ) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

    def _dump_optional_json(
        self,
        value: Any,
    ) -> Optional[str]:
        if value is None:
            return None

        return self._dump_json(
            value
        )

    @staticmethod
    def _load_json(
        value: Optional[str],
        default: Any,
    ) -> Any:
        if value is None:
            return default

        return json.loads(
            value
        )

    def _load_optional_json(
        self,
        value: Optional[str],
    ) -> Any:
        if value is None:
            return None

        return self._load_json(
            value,
            None,
        )
"""
IronCoach Decision Memory SQLite Schema

Definisce l'inizializzazione del database locale
usato come source of truth della Decision Memory.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union


PathLike = Union[str, Path]


def initialize_database(
    database_path: PathLike,
) -> None:
    """
    Crea il database Decision Memory e lo schema
    decision_episodes se non esistono già.
    """

    resolved_path = Path(
        database_path
    )

    resolved_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        resolved_path
    )

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_episodes (
                episode_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                decision_id TEXT UNIQUE,
                decision_timestamp TEXT NOT NULL,

                status TEXT NOT NULL
                    CHECK (
                        status IN (
                            'OPEN',
                            'WAITING_FOR_ACTIVITY',
                            'WAITING_FOR_OUTCOME',
                            'COMPLETE',
                            'INCOMPLETE'
                        )
                    ),

                schema_version TEXT NOT NULL,

                decision_action TEXT NOT NULL
                    CHECK (
                        decision_action IN (
                            'CONFERMA',
                            'ADATTA',
                            'RECUPERA'
                        )
                    ),

                strategy TEXT,
                rule_id TEXT NOT NULL,

                primary_intent TEXT NOT NULL
                    CHECK (
                        primary_intent IN (
                            'PROTECT_INJURY',
                            'RESTORE_RECOVERY',
                            'REDUCE_LOAD',
                            'RESTORE_FUELING',
                            'PROTECT_PERFORMANCE',
                            'MAINTAIN_PLAN',
                            'MANAGE_UNCERTAINTY'
                        )
                    ),

                decision_confidence INTEGER,
                supporting_intents_json TEXT NOT NULL,

                pre_decision_state_json TEXT NOT NULL,
                athlete_state_json TEXT NOT NULL,

                planned_workout_json TEXT,
                recommended_workout_json TEXT,
                actual_activity_json TEXT,
                actual_activity_id TEXT,
                actual_activity_source TEXT,

                adherence_status TEXT
                    CHECK (
                        adherence_status IS NULL
                        OR adherence_status IN (
                            'FOLLOWED',
                            'PARTIALLY_FOLLOWED',
                            'NOT_FOLLOWED',
                            'UNKNOWN'
                        )
                    ),

                adherence_evidence_json TEXT NOT NULL,
                adherence_evaluated_at TEXT,

                outcome_24h_status TEXT
                    CHECK (
                        outcome_24h_status IS NULL
                        OR outcome_24h_status IN (
                            'POSITIVE',
                            'NEUTRAL',
                            'NEGATIVE',
                            'INSUFFICIENT_DATA'
                        )
                    ),

                outcome_24h_evidence_json TEXT NOT NULL,
                outcome_24h_evaluated_at TEXT,

                outcome_72h_status TEXT
                    CHECK (
                        outcome_72h_status IS NULL
                        OR outcome_72h_status IN (
                            'POSITIVE',
                            'NEUTRAL',
                            'NEGATIVE',
                            'INSUFFICIENT_DATA'
                        )
                    ),

                outcome_72h_evidence_json TEXT NOT NULL,
                outcome_72h_evaluated_at TEXT,

                outcome_7d_status TEXT
                    CHECK (
                        outcome_7d_status IS NULL
                        OR outcome_7d_status IN (
                            'POSITIVE',
                            'NEUTRAL',
                            'NEGATIVE',
                            'INSUFFICIENT_DATA'
                        )
                    ),

                outcome_7d_evidence_json TEXT NOT NULL,
                outcome_7d_evaluated_at TEXT,

                overall_outcome_status TEXT
                    CHECK (
                        overall_outcome_status IS NULL
                        OR overall_outcome_status IN (
                            'POSITIVE',
                            'NEUTRAL',
                            'NEGATIVE',
                            'INSUFFICIENT_DATA'
                        )
                    ),

                overall_outcome_confidence INTEGER,
                overall_outcome_evidence_json TEXT NOT NULL,
                overall_outcome_evaluated_at TEXT,

                decision_engine_version TEXT,
                adherence_evaluator_version TEXT,
                outcome_evaluator_version TEXT,

                airtable_decision_record_id TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_decision_episodes_athlete_timestamp
            ON decision_episodes (
                athlete_id,
                decision_timestamp
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_decision_episodes_athlete_intent
            ON decision_episodes (
                athlete_id,
                primary_intent
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_decision_episodes_athlete_outcome
            ON decision_episodes (
                athlete_id,
                overall_outcome_status
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_decision_episodes_status
            ON decision_episodes (
                status
            )
            """
        )

        connection.commit()

    finally:
        connection.close()
"""Isolated, additive SQLite migrations for draft MAINTAIN_PLAN data."""

from __future__ import annotations

import sqlite3
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


SCHEMA_VERSION = 6


@dataclass(frozen=True)
class Migration:
    version: int
    checksum: str
    apply: Callable[[sqlite3.Connection], None]


_MIGRATION_1_SQL = """
        CREATE TABLE maintain_plan_prescription_snapshots (
            prescription_snapshot_id TEXT PRIMARY KEY,
            workout_id TEXT NOT NULL,
            decision_id TEXT NOT NULL,
            contract_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX idx_mp_snapshots_decision ON maintain_plan_prescription_snapshots(decision_id);

        CREATE TABLE maintain_plan_actual_sessions (
            session_id TEXT PRIMARY KEY,
            start TEXT NOT NULL,
            composition TEXT CHECK (composition IS NULL OR composition IN ('single', 'brick', 'multisport')),
            contract_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX idx_mp_sessions_start ON maintain_plan_actual_sessions(start);

        CREATE TABLE maintain_plan_prescription_mappings (
            mapping_id TEXT PRIMARY KEY,
            prescription_snapshot_ref TEXT NOT NULL REFERENCES maintain_plan_prescription_snapshots(prescription_snapshot_id),
            actual_session_ref TEXT NOT NULL REFERENCES maintain_plan_actual_sessions(session_id),
            resolution_method TEXT NOT NULL CHECK (resolution_method IN ('AUTOMATIC', 'ATHLETE_CONFIRMATION')),
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (mapping_id, prescription_snapshot_ref, actual_session_ref)
        );

        CREATE TABLE maintain_plan_matching_results (
            matching_result_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('MATCHED', 'CONFIRMATION_REQUIRED', 'NOT_EVALUABLE')),
            prescription_mapping_ref TEXT REFERENCES maintain_plan_prescription_mappings(mapping_id),
            policy_id TEXT,
            policy_version TEXT,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            CHECK ((status = 'MATCHED' AND prescription_mapping_ref IS NOT NULL)
                OR (status IN ('CONFIRMATION_REQUIRED', 'NOT_EVALUABLE')
                    AND prescription_mapping_ref IS NULL))
        );
        CREATE INDEX idx_mp_matching_status ON maintain_plan_matching_results(status);

        CREATE TABLE maintain_plan_execution_evaluations (
            evaluation_id TEXT PRIMARY KEY,
            prescription_mapping_ref TEXT NOT NULL REFERENCES maintain_plan_prescription_mappings(mapping_id),
            prescription_snapshot_ref TEXT NOT NULL REFERENCES maintain_plan_prescription_snapshots(prescription_snapshot_id),
            actual_session_ref TEXT NOT NULL REFERENCES maintain_plan_actual_sessions(session_id),
            overall TEXT CHECK (overall IS NULL OR overall IN
                ('IN_LINE', 'PARTIALLY_IN_LINE', 'DIFFERENT', 'INSUFFICIENT_DATA')),
            policy_id TEXT,
            policy_version TEXT,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (prescription_mapping_ref, prescription_snapshot_ref, actual_session_ref)
                REFERENCES maintain_plan_prescription_mappings
                    (mapping_id, prescription_snapshot_ref, actual_session_ref)
        );
        """


def _migration_1(connection: sqlite3.Connection) -> None:
    # executescript commits implicitly; individual statements preserve the
    # transaction owned by the runner.
    for statement in _MIGRATION_1_SQL.split(";"):
        if statement.strip():
            connection.execute(statement)


MIGRATIONS = (Migration(
    1,
    hashlib.sha256(_MIGRATION_1_SQL.encode("utf-8")).hexdigest(),
    _migration_1,
),)


_MIGRATION_2_SQL = """
        CREATE TABLE maintain_plan_feedback_logs (
            feedback_log_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES maintain_plan_actual_sessions(session_id),
            feedback_id TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (feedback_log_id, session_id, feedback_id)
        );
        CREATE INDEX idx_mp_feedback_logs_session ON maintain_plan_feedback_logs(session_id);

        CREATE TABLE maintain_plan_feedback_events (
            feedback_event_id TEXT PRIMARY KEY,
            feedback_log_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            feedback_id TEXT NOT NULL,
            event_sequence INTEGER NOT NULL CHECK (event_sequence > 0),
            event_type TEXT NOT NULL CHECK (event_type IN ('CAPTURED', 'CORRECTED', 'DELETED')),
            previous_event_id TEXT REFERENCES maintain_plan_feedback_events(feedback_event_id),
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (feedback_log_id, event_sequence),
            FOREIGN KEY (feedback_log_id, session_id, feedback_id)
                REFERENCES maintain_plan_feedback_logs(feedback_log_id, session_id, feedback_id)
        );
        CREATE INDEX idx_mp_feedback_events_session ON maintain_plan_feedback_events(session_id);
        CREATE INDEX idx_mp_feedback_events_log ON maintain_plan_feedback_events(feedback_log_id);

        CREATE TABLE maintain_plan_feedback_projections (
            projection_id TEXT PRIMARY KEY,
            projection_version TEXT NOT NULL,
            feedback_log_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            feedback_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'DELETED', 'INVALID', 'INSUFFICIENT_DATA')),
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (feedback_log_id, projection_version),
            FOREIGN KEY (feedback_log_id, session_id, feedback_id)
                REFERENCES maintain_plan_feedback_logs(feedback_log_id, session_id, feedback_id)
        );
        CREATE INDEX idx_mp_feedback_projections_session ON maintain_plan_feedback_projections(session_id);
        CREATE INDEX idx_mp_feedback_projections_status ON maintain_plan_feedback_projections(status);
        CREATE INDEX idx_mp_feedback_projections_version ON maintain_plan_feedback_projections(feedback_log_id, projection_version);

        CREATE TABLE maintain_plan_source_conflicts (
            conflict_id TEXT NOT NULL,
            session_id TEXT NOT NULL REFERENCES maintain_plan_actual_sessions(session_id),
            schema_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (session_id, conflict_id)
        );
        CREATE INDEX idx_mp_source_conflicts_conflict ON maintain_plan_source_conflicts(conflict_id);
        CREATE INDEX idx_mp_source_conflicts_session ON maintain_plan_source_conflicts(session_id);

        CREATE TABLE maintain_plan_resolution_logs (
            resolution_log_id TEXT PRIMARY KEY,
            conflict_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (resolution_log_id, conflict_id, session_id),
            FOREIGN KEY (session_id, conflict_id)
                REFERENCES maintain_plan_source_conflicts(session_id, conflict_id)
        );
        CREATE INDEX idx_mp_resolution_logs_conflict ON maintain_plan_resolution_logs(conflict_id);
        CREATE INDEX idx_mp_resolution_logs_session ON maintain_plan_resolution_logs(session_id);

        CREATE TABLE maintain_plan_resolution_events (
            event_id TEXT PRIMARY KEY,
            resolution_log_id TEXT NOT NULL,
            conflict_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            event_sequence INTEGER NOT NULL CHECK (event_sequence > 0),
            event_type TEXT NOT NULL CHECK (event_type IN ('RESOLVED', 'UNKNOWN_ANSWER', 'RESOLUTION_WITHDRAWN')),
            previous_event_id TEXT REFERENCES maintain_plan_resolution_events(event_id),
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (resolution_log_id, event_sequence),
            FOREIGN KEY (resolution_log_id, conflict_id, session_id)
                REFERENCES maintain_plan_resolution_logs(resolution_log_id, conflict_id, session_id)
        );
        CREATE INDEX idx_mp_resolution_events_session ON maintain_plan_resolution_events(session_id);
        CREATE INDEX idx_mp_resolution_events_conflict ON maintain_plan_resolution_events(conflict_id);
        CREATE INDEX idx_mp_resolution_events_log ON maintain_plan_resolution_events(resolution_log_id);

        CREATE TABLE maintain_plan_source_conflict_projections (
            projection_id TEXT PRIMARY KEY,
            projection_version TEXT NOT NULL,
            resolution_log_id TEXT NOT NULL,
            conflict_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('UNRESOLVED', 'RESOLVED', 'DONT_KNOW', 'INVALID')),
            projection_hash TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (resolution_log_id, projection_version),
            FOREIGN KEY (resolution_log_id, conflict_id, session_id)
                REFERENCES maintain_plan_resolution_logs(resolution_log_id, conflict_id, session_id)
        );
        CREATE INDEX idx_mp_conflict_projections_session ON maintain_plan_source_conflict_projections(session_id);
        CREATE INDEX idx_mp_conflict_projections_conflict ON maintain_plan_source_conflict_projections(conflict_id);
        CREATE INDEX idx_mp_conflict_projections_status ON maintain_plan_source_conflict_projections(status);
        CREATE INDEX idx_mp_conflict_projections_version ON maintain_plan_source_conflict_projections(resolution_log_id, projection_version);
        """


def _migration_2(connection: sqlite3.Connection) -> None:
    for statement in _MIGRATION_2_SQL.split(";"):
        if statement.strip():
            connection.execute(statement)


MIGRATIONS = MIGRATIONS + (Migration(
    2,
    hashlib.sha256(_MIGRATION_2_SQL.encode("utf-8")).hexdigest(),
    _migration_2,
),)



_MIGRATION_3_SQL = """
        CREATE TABLE maintain_plan_confirmations (
            confirmation_id TEXT PRIMARY KEY,
            matching_result_ref TEXT NOT NULL REFERENCES maintain_plan_matching_results(matching_result_id),
            prescription_snapshot_ref TEXT NOT NULL REFERENCES maintain_plan_prescription_snapshots(prescription_snapshot_id),
            status TEXT NOT NULL CHECK (status IN ('NOT_REQUIRED', 'REQUIRED', 'ANSWERED', 'UNKNOWN_ANSWER', 'SUPERSEDED')),
            answer_type TEXT CHECK (answer_type IS NULL OR answer_type IN
                ('SELECT_CANDIDATE', 'NOT_PERFORMED', 'NOT_SYNCHRONIZED', 'MANUAL_ASSOCIATION', 'DONT_KNOW')),
            selected_session_ref TEXT REFERENCES maintain_plan_actual_sessions(session_id),
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX idx_mp_confirmations_result ON maintain_plan_confirmations(matching_result_ref);
        CREATE INDEX idx_mp_confirmations_snapshot ON maintain_plan_confirmations(prescription_snapshot_ref);
        """


def _migration_3(connection: sqlite3.Connection) -> None:
    for statement in _MIGRATION_3_SQL.split(";"):
        if statement.strip():
            connection.execute(statement)


MIGRATIONS = MIGRATIONS + (Migration(
    3,
    hashlib.sha256(_MIGRATION_3_SQL.encode("utf-8")).hexdigest(),
    _migration_3,
),)


_CONFIRMATION_STATE_IS_VALID_SQL = """
        COALESCE(CASE
            WHEN status IN ('REQUIRED', 'NOT_REQUIRED')
                THEN answer_type IS NULL AND selected_session_ref IS NULL
            WHEN status = 'UNKNOWN_ANSWER'
                THEN answer_type = 'DONT_KNOW' AND selected_session_ref IS NULL
            WHEN status = 'ANSWERED' AND answer_type IN ('NOT_PERFORMED', 'NOT_SYNCHRONIZED')
                THEN selected_session_ref IS NULL
            WHEN status = 'ANSWERED' AND answer_type IN ('SELECT_CANDIDATE', 'MANUAL_ASSOCIATION')
                THEN selected_session_ref IS NOT NULL
            WHEN status = 'SUPERSEDED' THEN 1
            ELSE 0
        END, 0)
        """
_CONFIRMATION_TRIGGER_STATE_IS_VALID_SQL = (
    _CONFIRMATION_STATE_IS_VALID_SQL
    .replace("selected_session_ref", "NEW.selected_session_ref")
    .replace("answer_type", "NEW.answer_type")
    .replace("status", "NEW.status")
)

_MIGRATION_4_STATEMENTS = (f"""
        CREATE TRIGGER maintain_plan_confirmations_validate_insert
        BEFORE INSERT ON maintain_plan_confirmations
        WHEN NOT ({_CONFIRMATION_TRIGGER_STATE_IS_VALID_SQL})
        BEGIN
            SELECT RAISE(ABORT, 'invalid maintain_plan confirmation state');
        END
        """, f"""
        CREATE TRIGGER maintain_plan_confirmations_validate_update
        BEFORE UPDATE ON maintain_plan_confirmations
        WHEN NOT ({_CONFIRMATION_TRIGGER_STATE_IS_VALID_SQL})
        BEGIN
            SELECT RAISE(ABORT, 'invalid maintain_plan confirmation state');
        END
        """)
_MIGRATION_4_SQL = ";\n".join(_MIGRATION_4_STATEMENTS)


def _migration_4(connection: sqlite3.Connection) -> None:
    invalid = connection.execute(
        f"SELECT confirmation_id FROM maintain_plan_confirmations "
        f"WHERE NOT ({_CONFIRMATION_STATE_IS_VALID_SQL}) LIMIT 1"
    ).fetchone()
    if invalid is not None:
        raise RuntimeError(
            "cannot apply MAINTAIN_PLAN migration 4: invalid existing confirmation "
            f"{invalid[0]}"
        )
    for statement in _MIGRATION_4_STATEMENTS:
        connection.execute(statement)


MIGRATIONS = MIGRATIONS + (Migration(
    4,
    hashlib.sha256(_MIGRATION_4_SQL.encode("utf-8")).hexdigest(),
    _migration_4,
),)

_MIGRATION_5_SQL = """
        CREATE TABLE maintain_plan_source_conflict_impact_evaluations (
            conflict_impact_evaluation_id TEXT PRIMARY KEY,
            evaluation_version TEXT NOT NULL,
            session_id TEXT NOT NULL,
            conflict_id TEXT NOT NULL,
            prescription_mapping_ref TEXT NOT NULL REFERENCES maintain_plan_prescription_mappings(mapping_id),
            status TEXT NOT NULL CHECK (status IN ('EVALUATED', 'UNRESOLVED')),
            policy_id TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (session_id, conflict_id, evaluation_version),
            FOREIGN KEY (session_id, conflict_id)
                REFERENCES maintain_plan_source_conflicts(session_id, conflict_id)
        );
        CREATE INDEX idx_mp_conflict_impacts_session
            ON maintain_plan_source_conflict_impact_evaluations(session_id);
        """


def _migration_5(connection: sqlite3.Connection) -> None:
    for statement in _MIGRATION_5_SQL.split(";"):
        if statement.strip():
            connection.execute(statement)


MIGRATIONS = MIGRATIONS + (Migration(
    5, hashlib.sha256(_MIGRATION_5_SQL.encode("utf-8")).hexdigest(), _migration_5,
),)


_MIGRATION_6_SQL = """
        CREATE TABLE maintain_plan_source_conflict_impact_evaluations_v6 (
            conflict_impact_evaluation_id TEXT PRIMARY KEY,
            evaluation_version TEXT NOT NULL,
            session_id TEXT NOT NULL,
            conflict_id TEXT NOT NULL,
            prescription_mapping_ref TEXT REFERENCES maintain_plan_prescription_mappings(mapping_id),
            status TEXT NOT NULL CHECK (status IN ('EVALUATED', 'UNRESOLVED')),
            policy_id TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            payload_schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (session_id, conflict_id, evaluation_version),
            FOREIGN KEY (session_id, conflict_id)
                REFERENCES maintain_plan_source_conflicts(session_id, conflict_id)
        );
        INSERT INTO maintain_plan_source_conflict_impact_evaluations_v6
            SELECT * FROM maintain_plan_source_conflict_impact_evaluations;
        DROP TABLE maintain_plan_source_conflict_impact_evaluations;
        ALTER TABLE maintain_plan_source_conflict_impact_evaluations_v6
            RENAME TO maintain_plan_source_conflict_impact_evaluations;
        CREATE INDEX idx_mp_conflict_impacts_session
            ON maintain_plan_source_conflict_impact_evaluations(session_id);
        """


def _migration_6(connection: sqlite3.Connection) -> None:
    before = connection.execute(
        "SELECT * FROM maintain_plan_source_conflict_impact_evaluations ORDER BY conflict_impact_evaluation_id"
    ).fetchall()
    for statement in _MIGRATION_6_SQL.split(";"):
        if statement.strip():
            connection.execute(statement)
    after = connection.execute(
        "SELECT * FROM maintain_plan_source_conflict_impact_evaluations ORDER BY conflict_impact_evaluation_id"
    ).fetchall()
    if before != after:
        raise RuntimeError("MAINTAIN_PLAN migration 6 did not preserve impact rows byte-for-byte")


MIGRATIONS = MIGRATIONS + (Migration(
    6, hashlib.sha256(_MIGRATION_6_SQL.encode("utf-8")).hexdigest(), _migration_6,
),)


def run_migrations(database_path: str | Path, migrations: Iterable[Migration] = MIGRATIONS) -> None:
    """Apply each migration exactly once and atomically, without touching legacy tables."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS maintain_plan_schema_migrations ("
            "version INTEGER PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        connection.commit()
        applied = dict(connection.execute(
            "SELECT version, checksum FROM maintain_plan_schema_migrations"
        ))
        for migration in sorted(migrations, key=lambda item: item.version):
            if migration.version in applied:
                if applied[migration.version] != migration.checksum:
                    raise RuntimeError(
                        f"MAINTAIN_PLAN migration {migration.version} checksum mismatch"
                    )
                continue
            try:
                connection.execute("BEGIN IMMEDIATE")
                migration.apply(connection)
                connection.execute(
                    "INSERT INTO maintain_plan_schema_migrations"
                    "(version, checksum, applied_at) VALUES (?, ?, ?)",
                    (migration.version, migration.checksum,
                     datetime.now(timezone.utc).isoformat()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    finally:
        connection.close()
